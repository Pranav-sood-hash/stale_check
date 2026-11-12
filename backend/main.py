import os
import time
import uuid
import json
import asyncio
import threading
from typing import Optional
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ConfigDict
import logging
import sys

# Ensure backend directory and project root are in sys.path for direct file execution/import
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

try:
    from backend.graph import app_graph, local_answer
except ImportError:
    try:
        # pyrefly: ignore[missing-import]
        from graph import app_graph, local_answer
    except ImportError:
        from .graph import app_graph, local_answer

logger = logging.getLogger("stalecheck")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

api = FastAPI(title="StaleCheck API")
app = api  # Alias for ASGI / serverless runtimes expecting 'app'

RATE_LIMIT = 20
WINDOW_SECONDS = 60
rate_limits: dict[str, list[float]] = defaultdict(list)

@api.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        valid_timestamps = [t for t in rate_limits[client_ip] if now - t < WINDOW_SECONDS]
        if len(valid_timestamps) >= RATE_LIMIT:
            return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})
        valid_timestamps.append(now)
        rate_limits[client_ip] = valid_timestamps
    return await call_next(request)

allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
origins = [o.strip() for o in allowed_origins_raw.split(",")] if allowed_origins_raw != "*" else ["*"]

api.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class In(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = Field(..., min_length=3, max_length=6000)

class TraceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node: str
    ms: int

class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    url: str = ""
    date: Optional[str] = None
    snippet: str = ""

class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    title: str = ""
    text: str = ""
    category: str = "other"
    verdict: str = "Fresh"
    score: int = 0
    current_fact: str = ""
    reason: str = ""
    sources: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    cached: bool = False

class Result(BaseModel):
    model_config = ConfigDict(extra="ignore")
    answer: str
    overall: Optional[int]
    cache_hits: int = 0
    rewritten: str = ""
    stable_facts: list[str] = Field(default_factory=list)
    trace: list[TraceItem] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)

def build(answer: str, state: dict) -> Result:
    claims_raw = state.get("results") or state.get("claims") or []
    claims = []
    for c in claims_raw:
        if isinstance(c, dict):
            claims.append(Claim(**c))
        elif isinstance(c, Claim):
            claims.append(c)
    if claims:
        overall = round(sum(c.score for c in claims) / len(claims))
    else:
        overall = state.get("overall", None)

    cached_val = state.get("cached", 0)
    if isinstance(cached_val, list):
        cache_hits = len(cached_val)
    elif isinstance(cached_val, int):
        cache_hits = cached_val
    else:
        cache_hits = sum(1 for c in claims if c.cached)

    rewritten = state.get("rewritten", "") or answer
    stable_facts = state.get("stable_facts", [])
    if not isinstance(stable_facts, list):
        stable_facts = []
    trace_raw = state.get("trace", [])
    trace = [TraceItem(**t) if isinstance(t, dict) else t for t in trace_raw]
    return Result(
        answer=answer,
        overall=overall,
        cache_hits=cache_hits,
        rewritten=rewritten,
        stable_facts=stable_facts,
        trace=trace,
        claims=claims,
    )

def execute_graph_sync(text: str, event_queue: Optional[asyncio.Queue] = None, loop: Optional[asyncio.AbstractEventLoop] = None) -> Result:
    last_time = time.perf_counter()
    accumulated_state = {}
    node_traces = []

    if hasattr(app_graph, "stream"):
        stream_iter = app_graph.stream({"text": text, "answer": text}, stream_mode="updates")
        for update in stream_iter:
            now = time.perf_counter()
            elapsed_ms = int((now - last_time) * 1000)
            last_time = now
            for node_name, node_state in update.items():
                if isinstance(node_state, dict):
                    accumulated_state.update(node_state)
                trace_entry = {"node": node_name, "ms": elapsed_ms}
                node_traces.append(trace_entry)
                if event_queue and loop:
                    loop.call_soon_threadsafe(event_queue.put_nowait, ("node", trace_entry))
    else:
        state = app_graph.invoke({"text": text, "answer": text})
        if isinstance(state, dict):
            accumulated_state.update(state)
        now = time.perf_counter()
        elapsed_ms = int((now - last_time) * 1000)
        trace_entry = {"node": "graph", "ms": elapsed_ms}
        node_traces.append(trace_entry)
        if event_queue and loop:
            loop.call_soon_threadsafe(event_queue.put_nowait, ("node", trace_entry))

    if "trace" not in accumulated_state or not accumulated_state["trace"]:
        accumulated_state["trace"] = node_traces

    return build(text, accumulated_state)

@api.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = errors[0].get("msg", "Bad input") if errors else "Bad input"
    return JSONResponse(status_code=422, content={"error": msg})

@api.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})

@api.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return JSONResponse(status_code=504, content={"error": "Pipeline timed out"})
    return JSONResponse(status_code=502, content={"error": "Upstream service failure"})

@api.get("/api/health")
async def health():
    keys = ["TAVILY_API_KEY", "BIFROST_KEY", "BIFROST_URL", "BIFROST_API_KEY", "OPENAI_API_KEY", "ALLOWED_ORIGINS"]
    return {
        "status": "ok",
        "env": {k: bool(os.getenv(k)) for k in keys}
    }

@api.post("/api/check", response_model=Result)
async def check(body: In, request: Request):
    req_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(execute_graph_sync, body.text),
            timeout=90.0
        )
        total_ms = int((time.time() - start_time) * 1000)
        logger.info(f"id={req_id} mode=check claims={len(result.claims)} ms={total_ms}")
        return result
    except asyncio.TimeoutError:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=check error=timeout ms={total_ms}")
        raise HTTPException(status_code=504, detail="Pipeline timed out")
    except HTTPException:
        raise
    except Exception as exc:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=check error={str(exc)} ms={total_ms}")
        raise HTTPException(status_code=502, detail="Upstream service failure")

@api.post("/api/ask", response_model=Result)
async def ask(body: In, request: Request):
    req_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    try:
        answer = await asyncio.wait_for(
            asyncio.to_thread(local_answer, body.text),
            timeout=90.0
        )
    except asyncio.TimeoutError:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=ask error=timeout ms={total_ms}")
        raise HTTPException(status_code=504, detail="Pipeline timed out")
    except HTTPException:
        raise
    except Exception as exc:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=ask error={str(exc)} ms={total_ms}")
        raise HTTPException(status_code=502, detail="Upstream service failure")

    try:
        remaining_timeout = max(1.0, 90.0 - (time.time() - start_time))
        result = await asyncio.wait_for(
            asyncio.to_thread(execute_graph_sync, answer),
            timeout=remaining_timeout
        )
        total_ms = int((time.time() - start_time) * 1000)
        logger.info(f"id={req_id} mode=ask claims={len(result.claims)} ms={total_ms}")
        return result
    except asyncio.TimeoutError:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=ask error=timeout ms={total_ms}")
        raise HTTPException(status_code=504, detail="Pipeline timed out")
    except HTTPException:
        raise
    except Exception as exc:
        total_ms = int((time.time() - start_time) * 1000)
        logger.error(f"id={req_id} mode=ask error={str(exc)} ms={total_ms}")
        raise HTTPException(status_code=502, detail="Upstream service failure")

async def sse_generator(text: str, is_ask: bool, req_id: str, mode: str):
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    start_time = time.time()

    def worker():
        try:
            if is_ask:
                ans = local_answer(text)
            else:
                ans = text
            result = execute_graph_sync(ans, queue, loop)
            loop.call_soon_threadsafe(queue.put_nowait, ("done", result.model_dump()))
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": "Upstream service failure"}))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("end", None))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        try:
            remaining = max(0.1, 90.0 - (time.time() - start_time))
            event_type, payload = await asyncio.wait_for(queue.get(), timeout=remaining)
        except asyncio.TimeoutError:
            total_ms = int((time.time() - start_time) * 1000)
            logger.error(f"id={req_id} mode={mode} error=timeout ms={total_ms}")
            yield f"event: error\ndata: {json.dumps({'message': 'Pipeline timed out'})}\n\n"
            break

        if event_type == "end":
            break
        elif event_type == "node":
            yield f"event: node\ndata: {json.dumps(payload)}\n\n"
        elif event_type == "done":
            total_ms = int((time.time() - start_time) * 1000)
            claim_count = len(payload.get("claims", []))
            logger.info(f"id={req_id} mode={mode} claims={claim_count} ms={total_ms}")
            yield f"event: done\ndata: {json.dumps(payload)}\n\n"
        elif event_type == "error":
            total_ms = int((time.time() - start_time) * 1000)
            logger.error(f"id={req_id} mode={mode} error={payload.get('message')} ms={total_ms}")
            yield f"event: error\ndata: {json.dumps(payload)}\n\n"

@api.post("/api/check/stream")
async def check_stream(body: In, request: Request):
    req_id = str(uuid.uuid4())[:8]
    return StreamingResponse(
        sse_generator(body.text, is_ask=False, req_id=req_id, mode="check_stream"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

@api.post("/api/ask/stream")
async def ask_stream(body: In, request: Request):
    req_id = str(uuid.uuid4())[:8]
    return StreamingResponse(
        sse_generator(body.text, is_ask=True, req_id=req_id, mode="ask_stream"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

landing_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "landing"))
if not os.path.exists(os.path.join(landing_path, "index.html")):
    alt_landing = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "landing"))
    if os.path.exists(os.path.join(alt_landing, "index.html")):
        landing_path = alt_landing

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

@api.get("/landing")
@api.get("/landing/")
async def serve_landing_page():
    landing_file = os.path.join(landing_path, "index.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
    return FileResponse(os.path.join(frontend_path, "index.html"))

@api.get("/app")
@api.get("/app/")
async def serve_main_app():
    return FileResponse(os.path.join(frontend_path, "index.html"))

@api.get("/")
async def serve_root_page(request: Request):
    if request.query_params.get("app") == "1":
        return FileResponse(os.path.join(frontend_path, "index.html"))
    landing_file = os.path.join(landing_path, "index.html")
    if os.path.exists(landing_file):
        return FileResponse(landing_file)
    return FileResponse(os.path.join(frontend_path, "index.html"))

@api.get("/hero-bg.mp4")
@api.get("/landing/hero-bg.mp4")
async def serve_hero_bg_video():
    video_file = os.path.join(landing_path, "hero-bg.mp4")
    if os.path.exists(video_file):
        return FileResponse(video_file, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")

@api.get("/poster.jpg")
@api.get("/landing/poster.jpg")
async def serve_hero_poster():
    poster_file = os.path.join(landing_path, "poster.jpg")
    if os.path.exists(poster_file):
        return FileResponse(poster_file, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail="Poster not found")

if os.path.exists(frontend_path):
    api.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")

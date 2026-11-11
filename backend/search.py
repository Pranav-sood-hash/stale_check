import os
import re
import logging
import httpx

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

try:
    from backend import memory
except ImportError:
    import memory

logger = logging.getLogger("stalecheck.search")

def _normalize_key(text: str) -> str:
    return re.sub(r"\W+", " ", text).strip().lower()

def fetch_evidence(claim: dict) -> tuple[list[dict], bool]:
    query = claim.get("query") or claim.get("text") or ""
    if not query.strip():
        return ([], False)
    
    cache_key = _normalize_key(query)
    cached = memory.get(cache_key)
    if cached is not None:
        return (cached, True)

    category = claim.get("category", "other").lower()
    api_key = os.getenv("TAVILY_API_KEY")

    if api_key:
        try:
            if TavilyClient is not None:
                client = TavilyClient(api_key=api_key)
                search_kwargs = {
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": False,
                }
                if category in ("pricing", "version", "leadership"):
                    search_kwargs["topic"] = "news"
                resp = client.search(**search_kwargs)
                raw_results = resp.get("results", [])
            else:
                payload = {
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": False,
                }
                if category in ("pricing", "version", "leadership"):
                    payload["topic"] = "news"
                resp = httpx.post(
                    "https://api.tavily.com/search",
                    json=payload,
                    timeout=8.0
                )
                if resp.status_code == 200:
                    raw_results = resp.json().get("results", [])
                else:
                    logger.warning(f"Tavily search returned status {resp.status_code}")
                    raw_results = []

            results = []
            for item in raw_results:
                results.append({
                    "title": item.get("title") or "Source",
                    "url": item.get("url") or "",
                    "content": (item.get("content") or "")[:500],
                    "date": item.get("published_date") or None,
                })
            
            if results:
                memory.put(cache_key, results, category=category)
            return (results, False)
        except Exception as exc:
            logger.error(f"Tavily search error: {exc}")

    return ([], False)

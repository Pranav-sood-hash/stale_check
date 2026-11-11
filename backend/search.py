import os
import re
import logging
import httpx
try:
    import memory
except ImportError:
    from backend import memory

logger = logging.getLogger("stalecheck.search")

def _normalize_key(text: str) -> str:
    return re.sub(r"\W+", " ", text).strip().lower()

def fetch_evidence(claim: dict) -> tuple[list[dict], bool]:
    query = claim.get("query") or claim.get("text") or ""
    cache_key = _normalize_key(query)
    
    cached = memory.get(cache_key)
    if cached is not None:
        return (cached, True)

    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 5,
                    "include_answer": False
                },
                timeout=8.0
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", []):
                    results.append({
                        "title": item.get("title") or "Source",
                        "url": item.get("url") or "",
                        "content": item.get("content") or "",
                        "date": item.get("published_date") or None
                    })
                memory.set(cache_key, results)
                return (results, False)
            else:
                logger.warning(f"Tavily search returned status {resp.status_code}")
        except Exception as exc:
            logger.error(f"Tavily search error: {exc}")

    # No live evidence is available; never present sample data as a source.
    return ([], False)

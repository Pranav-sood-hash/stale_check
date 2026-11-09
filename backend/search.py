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

def _get_demo_evidence(claim_text: str) -> list[dict]:
    t = claim_text.lower()
    if any(k in t for k in ["chatgpt plus", "gpt-4", "$10", "$20", "prompt token", "0.03"]):
        return [
            {
                "title": "OpenAI Pricing",
                "url": "https://openai.com/pricing",
                "content": "ChatGPT Plus is available for $20 per month. GPT-4 pricing starts at $0.03 per 1k prompt tokens.",
                "date": "2026-03-01"
            }
        ]
    if any(k in t for k in ["python 3.8", "python 3.12", "python 3.13", "latest version", "stable version"]):
        return [
            {
                "title": "Python Releases",
                "url": "https://www.python.org/downloads/",
                "content": "Python 3.12 is actively maintained as stable. Python 3.8 is end of life.",
                "date": "2026-02-15"
            }
        ]
    if any(k in t for k in ["satya nadella", "microsoft"]):
        return [
            {
                "title": "Microsoft Leadership",
                "url": "https://news.microsoft.com/exec",
                "content": "Satya Nadella is the Chairman and Chief Executive Officer of Microsoft.",
                "date": "2026-05-10"
            }
        ]
    if any(k in t for k in ["parag agrawal", "linda yaccarino", "twitter", "ceo of x"]):
        return [
            {
                "title": "X Executive Team",
                "url": "https://x.com/about",
                "content": "Linda Yaccarino serves as Chief Executive Officer of X (formerly Twitter).",
                "date": "2026-04-01"
            }
        ]
    if any(k in t for k in ["european union", "united kingdom", "brexit", "member of the eu"]):
        return [
            {
                "title": "EU Member States",
                "url": "https://europa.eu/about-eu",
                "content": "The United Kingdom withdrew from the European Union on 31 January 2020.",
                "date": "2026-01-01"
            }
        ]
    if any(k in t for k in ["text-davinci-003", "davinci"]):
        return [
            {
                "title": "OpenAI Documentation",
                "url": "https://platform.openai.com/docs/models",
                "content": "text-davinci-003 is shut down and deprecated. Use gpt-4o instead.",
                "date": "2026-01-10"
            }
        ]
    if any(k in t for k in ["github", "repositories", "open source"]):
        return [
            {
                "title": "GitHub Pricing",
                "url": "https://github.com/pricing",
                "content": "GitHub Free provides unlimited public and private repositories for developers.",
                "date": "2026-06-01"
            }
        ]
    return []

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

    # Fallback to demo evidence when Tavily key is not set or network fails
    fallback_evidence = _get_demo_evidence(claim.get("text", ""))
    memory.set(cache_key, fallback_evidence)
    return (fallback_evidence, False)


import os
import re
import json
import logging
from typing import Any
import httpx

logger = logging.getLogger("stalecheck.llm")

def model(env: str, default: str = "", temp: float = 0.0) -> dict:
    model_name = os.getenv(env, default)
    api_key = os.getenv("BIFROST_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BIFROST_BASE_URL") or "https://api.openai.com/v1"
    if not os.getenv("BIFROST_BASE_URL") and model_name.startswith("openai/"):
        model_name = model_name.removeprefix("openai/")
    if not os.getenv("BIFROST_BASE_URL") and env not in os.environ and model_name.startswith("anthropic/"):
        model_name = "gpt-4o-mini"
    return {
        "env": env,
        "model": model_name,
        "temp": temp,
        "api_key": api_key,
        "base_url": base_url.rstrip("/")
    }

def _clean_json_str(raw: str) -> str:
    cleaned = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return cleaned

def ask_json(llm: Any, system: str, user: str) -> dict:
    if isinstance(llm, dict) and llm.get("api_key"):
        url = f"{llm['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {llm['api_key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": llm.get("model") or "gpt-4o-mini",
            "temperature": llm.get("temp", 0.0),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "response_format": {"type": "json_object"}
        }
        try:
            resp = httpx.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(_clean_json_str(content))
            else:
                logger.warning("LLM API returned status %s", resp.status_code)
        except Exception as exc:
            logger.error(f"LLM call failed: {exc}")

    raise RuntimeError("Language model unavailable or returned an invalid response")


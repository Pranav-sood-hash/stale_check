import os
import re
import json
import logging
from typing import Any
import httpx

logger = logging.getLogger("stalecheck.llm")

def model(env: str, default: str = "", temp: float = 0.0) -> dict:
    model_name = os.getenv(env, default)
    api_key = os.getenv("BIFROST_KEY") or os.getenv("BIFROST_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("BIFROST_URL") or os.getenv("BIFROST_BASE_URL")
    
    is_direct_openai = False
    if not base_url:
        base_url = "https://api.openai.com/v1"
        is_direct_openai = True
    elif "openai.com" in base_url:
        is_direct_openai = True

    if is_direct_openai:
        if model_name.startswith("openai/"):
            model_name = model_name.removeprefix("openai/")
        elif model_name.startswith("anthropic/") or model_name.startswith("ollama/"):
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
    else:
        # Extract the outer JSON object or array if surrounded by chatter
        obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
        if obj_match:
            cleaned = obj_match.group(1).strip()
    return cleaned

def ask_json(llm: Any, system: str, user: str) -> dict:
    if not isinstance(llm, dict) or not llm.get("api_key"):
        return {}

    url = f"{llm['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {llm['api_key']}",
        "Content-Type": "application/json"
    }
    base_payload = {
        "model": llm.get("model") or "gpt-4o-mini",
        "temperature": llm.get("temp", 0.0),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ]
    }

    # First try with json_object format
    payload = dict(base_payload)
    payload["response_format"] = {"type": "json_object"}

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=25.0)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(_clean_json_str(content))
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        else:
            # Retry once without response_format if rejected
            resp2 = httpx.post(url, headers=headers, json=base_payload, timeout=25.0)
            if resp2.status_code == 200:
                data2 = resp2.json()
                content2 = data2["choices"][0]["message"]["content"]
                parsed2 = json.loads(_clean_json_str(content2))
                if isinstance(parsed2, dict):
                    return parsed2
            logger.warning("LLM API error status: %s", resp.status_code)
    except Exception as exc:
        logger.error(f"LLM call failed: {exc}")

    return {}

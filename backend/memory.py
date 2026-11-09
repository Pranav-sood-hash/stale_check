import time
from typing import Optional

_CACHE: dict[str, tuple[list[dict], float]] = {}
CACHE_TTL = 3600

def get(key: str) -> Optional[list[dict]]:
    if key in _CACHE:
        val, ts = _CACHE[key]
        if time.time() - ts < CACHE_TTL:
            return val
        del _CACHE[key]
    return None

def set(key: str, value: list[dict]) -> None:
    _CACHE[key] = (value, time.time())

def clear() -> None:
    _CACHE.clear()


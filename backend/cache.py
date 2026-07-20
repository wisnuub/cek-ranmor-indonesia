"""Simple in-memory TTL cache. Keyed by (plate, nik or '')."""
import asyncio
import time
from typing import Any, Optional

_store: dict[str, tuple[Any, float]] = {}
_lock = asyncio.Lock()

DEFAULT_TTL = 3600  # 1 hour — tax data doesn't change often


async def get(key: str) -> Optional[Any]:
    async with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del _store[key]
            return None
        return value


async def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    async with _lock:
        _store[key] = (value, time.time() + ttl)


async def invalidate(key: str) -> None:
    async with _lock:
        _store.pop(key, None)


def make_key(plate: str, nik: Optional[str]) -> str:
    return f"{plate.upper().replace(' ', '')}:{nik or ''}"

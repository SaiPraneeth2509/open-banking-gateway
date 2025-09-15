from __future__ import annotations
from typing import Optional
from redis.asyncio import from_url, Redis
from app.core.config import settings

_client: Optional[Redis] = None

def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,  # store/read JSON strings
        )
    return _client

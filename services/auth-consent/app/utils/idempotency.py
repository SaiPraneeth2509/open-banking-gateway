from __future__ import annotations
import json
from typing import Any, Dict, Optional
from app.cache.redis_client import get_redis

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60  # 24h
_LOCK_TTL_SECONDS = 60                  # short lock to avoid races

def _key(tpp_client_id: str, idem_key: str) -> str:
    return f"idem:{tpp_client_id}:{idem_key}"

async def read_entry(tpp_client_id: str, idem_key: str) -> Optional[Dict[str, Any]]:
    raw = await get_redis().get(_key(tpp_client_id, idem_key))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

async def try_lock(tpp_client_id: str, idem_key: str, body_sha: str) -> bool:
    # SET NX to claim the key briefly while we create the consent
    value = json.dumps({"state": "LOCK", "body_sha256": body_sha})
    return await get_redis().set(_key(tpp_client_id, idem_key), value, nx=True, ex=_LOCK_TTL_SECONDS)

async def store_final(tpp_client_id: str, idem_key: str, body_sha: str,
                      response_dict: Dict[str, Any], status_code: int, headers: Dict[str, str]) -> None:
    value = json.dumps({
        "state": "FINAL",
        "body_sha256": body_sha,
        "response": response_dict,
        "status_code": status_code,
        "headers": headers,
    })
    await get_redis().set(_key(tpp_client_id, idem_key), value, ex=IDEMPOTENCY_TTL_SECONDS)
from __future__ import annotations
import uuid
from typing import Optional
from contextvars import ContextVar

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

def set_correlation_id(value: Optional[str]) -> str:
    if not value:
        value = str(uuid.uuid4())
    _correlation_id.set(value)
    return value

def get_correlation_id(default: Optional[str] = None) -> Optional[str]:
    return _correlation_id.get() or default

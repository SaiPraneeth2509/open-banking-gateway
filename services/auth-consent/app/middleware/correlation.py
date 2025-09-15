from __future__ import annotations
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.correlation import set_correlation_id, get_correlation_id

class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Ingest or mint X-Request-ID
        inbound = request.headers.get("X-Request-ID")
        cid = set_correlation_id(inbound)

        # Make available to route handlers
        request.state.correlation_id = cid

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            # (Optional) you can log here or in a separate logging middleware
        # Ensure header on every response
        response.headers["X-Request-ID"] = get_correlation_id(cid) or cid
        response.headers.setdefault("Cache-Control", "no-store")
        return response

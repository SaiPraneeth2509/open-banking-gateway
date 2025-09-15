from __future__ import annotations

import time
from typing import Iterable

from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Metric objects (singletons)
# Business counters
consents_created_total = Counter(
    "consents_created_total",
    "Total number of consents successfully created"
)
consents_revoked_total = Counter(
    "consents_revoked_total",
    "Total number of consents successfully revoked"
)
consents_status_poll_total = Counter(
    "consents_status_poll_total",
    "Total number of consent status polls"
)

# Request latency histogram (seconds), labeled by route template and status code
request_latency_seconds = Histogram(
    "request_latency_seconds",
    "HTTP request latency in seconds",
    labelnames=("route", "status_code"),
)

# Public helpers to increment business metrics
def inc_consents_created() -> None:
    consents_created_total.inc()

def inc_consents_revoked() -> None:
    consents_revoked_total.inc()

def inc_consents_status_poll() -> None:
    consents_status_poll_total.inc()

# Middleware for request timing
class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_routes: Iterable[str] | None = None):
        super().__init__(app)
        self.exclude_routes = set(exclude_routes or [])

    async def dispatch(self, request: Request, call_next):
        # Skip by raw path if configured (avoid measuring /metrics and /health)
        raw_path = request.url.path
        if raw_path in self.exclude_routes:
            return await call_next(request)

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
            status_code = str(response.status_code)
        except Exception:
            # Count exceptions as 500 for latency observation, then re-raise
            status_code = "500"
            duration = time.perf_counter() - start
            route_tmpl = self._resolve_route_template(request)
            request_latency_seconds.labels(route=route_tmpl, status_code=status_code).observe(duration)
            raise

        duration = time.perf_counter() - start
        route_tmpl = self._resolve_route_template(request)
        request_latency_seconds.labels(route=route_tmpl, status_code=status_code).observe(duration)
        return response

    @staticmethod
    def _resolve_route_template(request: Request) -> str:
        # Prefer the route path template (low-cardinality), fallback to raw path when unknown (404)
        route = request.scope.get("route")
        if route and getattr(route, "path", None):
            return route.path
        return request.url.path  # fallback (rare)

# /metrics router
router = APIRouter()

@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint():
    data = generate_latest()  # Prometheus exposition text
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

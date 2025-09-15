from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging 
from app.api.routers import ( health, consents_create, consents_status, consents_get, consents_revoke, consents_callback, consents_authorize)
from app.db.init_db import init_db
from app.housekeeping.expiry import ExpirySweeper
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.errors import (
    http_exception_handler,
    validation_exception_handler,
    unhandled_exception_handler,
)
from app.middleware.correlation import CorrelationMiddleware 
from app.core.metrics import router as metrics_router, MetricsMiddleware


app = FastAPI(title=settings.APP_NAME, version="0.1.0")
setup_logging()

_sweeper: ExpirySweeper | None = None

@app.on_event("startup")
async def on_startup():
    if not settings.USE_ALEMBIC:
        init_db() 
    global _sweeper
    if settings.EXPIRY_SWEEP_ENABLED:
        _sweeper = ExpirySweeper(interval_seconds=settings.EXPIRY_SWEEP_SECONDS)
        await _sweeper.start()

@app.on_event("shutdown")
async def on_shutdown():
    global _sweeper
    if _sweeper:
        await _sweeper.stop()
        _sweeper = None

# Middleware: install correlation header propagation (adds X-Request-ID)
app.add_middleware(CorrelationMiddleware)
# Middleware: metrics timing AFTER correlation (so we can enrich later if needed)
app.add_middleware(MetricsMiddleware, exclude_routes=settings.METRICS_EXCLUDE_ROUTES)

# Exception handlers (uniform error JSON)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Routers
app.include_router(health.router)
app.include_router(consents_create.router)
app.include_router(consents_status.router)
app.include_router(consents_get.router)
app.include_router(consents_revoke.router)
app.include_router(consents_authorize.router) 
app.include_router(consents_callback.router) 

# Conditionally expose /metrics
if settings.METRICS_ENABLED:
    app.include_router(metrics_router)

# Root
@app.get("/")
def root():
    return {"service": settings.APP_NAME, "env": settings.APP_ENV}

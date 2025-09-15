from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import status as http
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.correlation import get_correlation_id

# Map our short string details → human messages (expand as needed)
_MESSAGES = {
    "invalid_token": "The access token is invalid.",
    "token_expired": "The access token has expired.",
    "invalid_audience": "The token audience is not accepted.",
    "invalid_issuer": "The token issuer is not accepted.",
    "forbidden": "You do not have permission to perform this action.",
    "not_found": "The requested resource was not found.",
    "idempotency_conflict": "The Idempotency-Key conflicts with a prior request.",
    "invalid_state": "The resource is not in a valid state for this operation.",
    "missing Idempotency-Key": "Idempotency-Key header is required.",
}

def _normalize_detail(detail: Any) -> str:
    if isinstance(detail, dict) and "detail" in detail:
        return str(detail["detail"])
    return str(detail)

def _build_error(code: str, status_code: int, message: Optional[str] = None) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "http_status": status_code,
            "message": message or _MESSAGES.get(code, code),
            "correlation_id": get_correlation_id(),
        }
    }

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = _normalize_detail(exc.detail)
    payload = _build_error(code, exc.status_code)
    return JSONResponse(status_code=exc.status_code, content=payload)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    payload = {
        "error": {
            "code": "validation_error",
            "http_status": http.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "One or more fields failed validation.",
            "correlation_id": get_correlation_id(),
            "details": exc.errors(),
        }
    }
    return JSONResponse(status_code=http.HTTP_422_UNPROCESSABLE_ENTITY, content=payload)

async def unhandled_exception_handler(request: Request, exc: Exception):
    # Avoid leaking internals; logs will carry the stacktrace
    payload = _build_error("server_error", http.HTTP_500_INTERNAL_SERVER_ERROR, "An unexpected error occurred.")
    return JSONResponse(status_code=http.HTTP_500_INTERNAL_SERVER_ERROR, content=payload)

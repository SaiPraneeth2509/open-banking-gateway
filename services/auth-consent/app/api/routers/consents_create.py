from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from app.api.schemas.consents import ConsentCreateRequest, ConsentCreateResponse
from app.security.jwt import get_current_client
from app.services.consent_service import create_consent
from sqlalchemy.orm import Session
from app.db.deps import get_db

router = APIRouter(prefix="/consents", tags=["consents"])

COMMON_HEADERS = {
    "X-Request-ID": {
        "description": "Correlation ID for tracing.",
        "schema": {"type": "string", "format": "uuid"},
    },
}

CREATE_RESPONSES = {
    201: {"description": "Created", "headers": {**COMMON_HEADERS, "Location": {"description": "Resource path", "schema": {"type": "string"}}}},
    200: {"description": "Idempotent replay", "headers": {**COMMON_HEADERS, "Idempotency-Replayed": {"description": "True if replayed", "schema": {"type": "boolean"}}}},
    409: {"description": "Conflict (idempotency)", "headers": COMMON_HEADERS},
}

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a consent",
    response_model=ConsentCreateResponse,
    responses=CREATE_RESPONSES,
)
async def create_consent_endpoint(
    request: Request,
    payload: ConsentCreateRequest,
    response: Response, 
    client=Depends(get_current_client),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    # Require Idempotency-Key; we will enforce semantics when DB/Redis added
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing Idempotency-Key")

    correlation_id: UUID = UUID(x_request_id) if x_request_id else uuid4()

    resp, is_replay, replay_headers = await create_consent(
        payload=payload,
        tpp_client_id=client["tpp_client_id"],
        base_url=str(request.base_url),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        db=db,
        client_ip=(request.client.host if request.client else None),
        tenant_id=client.get("tenant_id"),
    )
     # Propagate headers (stable across replays)
    response.headers["X-Request-ID"] = replay_headers.get("X-Request-ID", str(correlation_id))
    response.headers["Location"] = replay_headers.get("Location", resp.links.self)

    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["Idempotency-Replayed"] = "true"
    else:
        response.status_code = status.HTTP_201_CREATED

    return resp

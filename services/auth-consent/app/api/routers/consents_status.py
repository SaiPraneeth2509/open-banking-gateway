from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.security.jwt import get_current_client
from app.repositories.consents import get_by_id
from app.api.schemas.consents import ConsentStatusResponse
from app.core.metrics import inc_consents_status_poll

router = APIRouter(prefix="/consents", tags=["consents"])

@router.get("/{consent_id}/status", response_model=ConsentStatusResponse, summary="Get consent status")
async def get_consent_status(
    consent_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    client = Depends(get_current_client),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    # correlation id handling
    correlation_id = UUID(x_request_id) if x_request_id else uuid4()
    response.headers["X-Request-ID"] = str(correlation_id)

    inc_consents_status_poll()

    obj = get_by_id(db, consent_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # ownership enforcement (TPP and tenant)
    if obj.tpp_client_id != client["tpp_client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    tenant_id = client.get("tenant_id")
    if tenant_id is not None and obj.tenant_id is not None and obj.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return ConsentStatusResponse(
        id=obj.id,
        status=obj.status,          
        expires_at=obj.expires_at,
        correlation_id=correlation_id,
    )

from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.security.jwt import get_current_client
from app.repositories.consents import get_by_id, update_status_if_allowed
from app.api.schemas.consents import ConsentStatusResponse
from app.core.metrics import inc_consents_revoked 

router = APIRouter(prefix="/consents", tags=["consents"])

@router.post("/{consent_id}/revoke", response_model=ConsentStatusResponse, summary="Revoke a consent")
async def revoke_consent(
    consent_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    client = Depends(get_current_client),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    # Correlation ID
    correlation_id = UUID(x_request_id) if x_request_id else uuid4()
    response.headers["X-Request-ID"] = str(correlation_id)

    # Load + ownership checks
    obj = get_by_id(db, consent_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    if obj.tpp_client_id != client["tpp_client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    tenant_id = client.get("tenant_id")
    if tenant_id is not None and obj.tenant_id is not None and obj.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    # Idempotent: already revoked -> OK
    if obj.status == "REVOKED":
        return ConsentStatusResponse(
            id=obj.id, status=obj.status, expires_at=obj.expires_at, correlation_id=correlation_id
        )

    # Allowed transitions
    updated = update_status_if_allowed(
        db,
        consent_id=consent_id,
        allowed_from=("PENDING_SCA", "GRANTED"),
        new_status="REVOKED",
    )

    if not updated:
        # Shouldn’t happen (we just fetched it), but guard anyway
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    if updated.status != "REVOKED":
        # Tried to revoke from a disallowed state (EXPIRED/REJECTED)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid_state")

    # Count a successful revoke exactly once
    inc_consents_revoked()
    
    return ConsentStatusResponse(
        id=updated.id,
        status=updated.status,
        expires_at=updated.expires_at,
        correlation_id=correlation_id,
    )

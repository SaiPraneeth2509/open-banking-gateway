from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.security.jwt import get_current_client
from app.repositories.consents import get_by_id, set_sca_id_if_pending
from app.api.schemas.consents import ConsentAuthorizeResponse, NextAction
from app.services.sca_service import generate_sca_id, build_authorize_url, build_deny_url

router = APIRouter(prefix="/consents", tags=["consents"])

@router.post("/{consent_id}/authorize", response_model=ConsentAuthorizeResponse, summary="Start SCA (stub)")
async def start_sca(
    consent_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    client = Depends(get_current_client),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    correlation_id = UUID(x_request_id) if x_request_id else uuid4()
    response.headers["X-Request-ID"] = str(correlation_id)

    obj = get_by_id(db, consent_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Ownership: TPP + (optional) tenant
    if obj.tpp_client_id != client["tpp_client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    tenant_id = client.get("tenant_id")
    if tenant_id is not None and obj.tenant_id is not None and obj.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    # Only PENDING_SCA can start SCA; idempotent if sca_id already exists
    if obj.status != "PENDING_SCA":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid_state")

    sca_id = obj.sca_id or generate_sca_id()
    updated = set_sca_id_if_pending(db, consent_id=consent_id, sca_id=sca_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Build an authorize URL that simulates the provider redirect into our callback
    auth_url = build_authorize_url(str(request.base_url), consent_id, updated.sca_id or sca_id)
    deny_url = build_deny_url(str(request.base_url), consent_id, updated.sca_id or sca_id)

    return ConsentAuthorizeResponse(
        id=updated.id,
        status=updated.status,  # still PENDING_SCA
        sca_id=updated.sca_id or sca_id,
        next_action=NextAction(authorize_url=auth_url),
        deny_url=deny_url,
        correlation_id=correlation_id,
    )

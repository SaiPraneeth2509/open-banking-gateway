# app/api/routers/consents_callback.py
from __future__ import annotations
from uuid import UUID, uuid4
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.repositories.consents import get_by_id, update_status_if_allowed

router = APIRouter(prefix="/consents", tags=["consents"])

@router.get("/{consent_id}/authorize/callback", summary="SCA callback (stub) – redirects to client")
async def authorize_callback(
    consent_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    state: str = Query(..., description="SCA state id that must match stored sca_id"),
    result: Literal["approved", "denied"] = Query(...),  # <-- replace pattern with Literal
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    # Correlation ID
    correlation_id = UUID(x_request_id) if x_request_id else uuid4()
    response.headers["X-Request-ID"] = str(correlation_id)

    obj = get_by_id(db, consent_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Validate state param matches stored sca_id
    if not obj.sca_id or state != obj.sca_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_state")

    requested_status = "GRANTED" if result == "approved" else "REJECTED"

    if obj.status == "PENDING_SCA":
        updated = update_status_if_allowed(
            db,
            consent_id=consent_id,
            allowed_from=("PENDING_SCA",),
            new_status=requested_status,
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
        final_status = updated.status
        redirect_success_url = updated.redirect_success_url
        redirect_failure_url = updated.redirect_failure_url
    elif obj.status in ("GRANTED", "REJECTED"):
        # Idempotent replay: only allow same outcome
        if (obj.status == "GRANTED" and requested_status == "GRANTED") or (
            obj.status == "REJECTED" and requested_status == "REJECTED"
        ):
            final_status = obj.status
            redirect_success_url = obj.redirect_success_url
            redirect_failure_url = obj.redirect_failure_url
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid_state")
    else:
        # EXPIRED or REVOKED cannot be changed via callback
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="invalid_state")

    # Redirect based on ACTUAL final status
    redirect_to = redirect_success_url if final_status == "GRANTED" else redirect_failure_url
    return RedirectResponse(url=redirect_to, status_code=302)

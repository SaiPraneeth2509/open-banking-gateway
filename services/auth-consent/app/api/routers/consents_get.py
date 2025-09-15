from __future__ import annotations
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.security.jwt import get_current_client
from app.repositories.consents import get_by_id
from app.api.schemas.consents import (
    ConsentReadResponse, RedirectURLs, AccountsScope, ConsentLinks, ProviderRefs
)

router = APIRouter(prefix="/consents", tags=["consents"])

@router.get("/{consent_id}", response_model=ConsentReadResponse, summary="Get consent detail")
async def get_consent_detail(
    consent_id: UUID,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    client = Depends(get_current_client),
    x_request_id: str | None = Header(None, alias="X-Request-ID"),
):
    # Correlation ID: echo or generate, and return as a header
    correlation_id = UUID(x_request_id) if x_request_id else uuid4()
    response.headers["X-Request-ID"] = str(correlation_id)

    obj = get_by_id(db, consent_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")

    # Ownership enforcement (TPP + tenant)
    if obj.tpp_client_id != client["tpp_client_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    tenant_id = client.get("tenant_id")
    if tenant_id is not None and obj.tenant_id is not None and obj.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    # Rebuild nested schema pieces from stored columns
    redirect_urls = RedirectURLs(
        success_url=obj.redirect_success_url,
        failure_url=obj.redirect_failure_url,
    )

    accounts = None
    if obj.accounts_scope:
        accounts = AccountsScope(**obj.accounts_scope)

    provider_refs = None
    if obj.sca_id:
        provider_refs = ProviderRefs(sca_id=obj.sca_id)

    links = ConsentLinks(
        self=f"/consents/{obj.id}",
        status=f"/consents/{obj.id}/status",
        revoke=f"/consents/{obj.id}/revoke",
    )

    return ConsentReadResponse(
        id=obj.id,
        status=obj.status,
        type=obj.type,  # stored as string "AIS" and matches enum value
        permissions=obj.permissions,
        expires_at=obj.expires_at,
        recurring=obj.recurring,
        redirect_urls=redirect_urls,
        accounts=accounts,
        provider_refs=provider_refs,
        links=links,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        correlation_id=correlation_id,
    )

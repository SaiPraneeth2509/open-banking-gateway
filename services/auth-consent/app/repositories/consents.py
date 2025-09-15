from typing import Optional, Iterable
from uuid import UUID
from datetime import datetime
from sqlalchemy import update, func
from sqlalchemy.orm import Session
from app.models.consent import Consent
from app.api.schemas.consents import ConsentCreateRequest

def create(
    db: Session,
    *,
    consent_id: UUID,
    tpp_client_id: str,
    payload: ConsentCreateRequest,
    expires_at: datetime,
    status: str,
    client_ip: Optional[str],
    tenant_id: Optional[str],
) -> Consent:
    obj = Consent(
        id=consent_id,
        tenant_id=tenant_id, 
        tpp_client_id=tpp_client_id,
        type=payload.type.value,
        permissions=[p.value for p in payload.permissions],
        status=status,
        recurring=payload.recurring,
        expires_at=expires_at,
        redirect_success_url=str(payload.redirect_urls.success_url),
        redirect_failure_url=str(payload.redirect_urls.failure_url),
        accounts_scope=(payload.accounts.model_dump() if payload.accounts else None),
        created_by_ip=client_ip,
        extra_metadata=payload.metadata or None,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_by_id(db: Session, consent_id: UUID) -> Optional[Consent]:
    return db.get(Consent, consent_id)

def update_status_if_allowed(
    db: Session,
    *,
    consent_id: UUID,
    allowed_from: Iterable[str],
    new_status: str,
) -> Optional[Consent]:
    obj = db.get(Consent, consent_id)
    if not obj:
        return None
    if obj.status in allowed_from:
        obj.status = new_status
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

def set_sca_id_if_pending(db: Session, *, consent_id: UUID, sca_id: str) -> Optional[Consent]:
    obj = db.get(Consent, consent_id)
    if not obj:
        return None
    if obj.status == "PENDING_SCA":
        # Idempotent: keep existing sca_id if already set
        if obj.sca_id and obj.sca_id != sca_id:
            # Keep the existing one; caller should reuse it
            pass
        else:
            obj.sca_id = obj.sca_id or sca_id
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj


def expire_due(db: Session) -> int:
    """
    Mark due consents as EXPIRED. Returns affected row count.
    States allowed to expire: PENDING_SCA, GRANTED.
    """
    stmt = (
        update(Consent)
        .where(Consent.status.in_(("PENDING_SCA", "GRANTED")))
        .where(Consent.expires_at <= func.now())
        .values(status="EXPIRED")
        .execution_options(synchronize_session=False)
    )
    res = db.execute(stmt)
    db.commit()
    return int(res.rowcount or 0)
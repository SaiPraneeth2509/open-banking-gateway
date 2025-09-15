import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, func, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from app.db.base import Base

class Consent(Base):
    __tablename__ = "consents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Text, nullable=True)

    tpp_client_id = Column(Text, nullable=False, index=True)
    psu_id = Column(Text, nullable=True)

    type = Column(String(16), nullable=False)               # e.g., "AIS"
    permissions = Column(JSONB, nullable=False)             # ["accounts:read", ...]
    status = Column(String(20), nullable=False, index=True) # PENDING_SCA, GRANTED, ...
    recurring = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)

    redirect_success_url = Column(Text, nullable=False)
    redirect_failure_url = Column(Text, nullable=False)
    accounts_scope = Column(JSONB, nullable=True)           # { ids: [], currency: ... }
    sca_id = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    created_by_ip = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=True)     # column named "metadata"
    version = Column(Integer, nullable=False, default=1)

# Quick indices for common filters:
Index("idx_consents_tenant", Consent.tenant_id)
Index("idx_consents_created_at", Consent.created_at)

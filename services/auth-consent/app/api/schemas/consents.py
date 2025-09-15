from __future__ import annotations
from enum import Enum
from typing import List, Optional, Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, AnyHttpUrl, field_validator

class ConsentType(str, Enum):
    AIS = "AIS"

class Permission(str, Enum):
    ACCOUNTS_READ = "accounts:read"
    BALANCES_READ = "balances:read"
    TRANSACTIONS_READ = "transactions:read"

class RedirectURLs(BaseModel):
    success_url: AnyHttpUrl
    failure_url: AnyHttpUrl

    @field_validator("success_url", "failure_url")
    @classmethod
    def https_or_local(cls, v: AnyHttpUrl) -> AnyHttpUrl:
        # Allow https URLs, or http for localhost during dev
        if v.scheme == "https" or v.host in {"localhost", "127.0.0.1"}:
            return v
        raise ValueError("redirect URLs must be https (or localhost for dev)")

class AccountsScope(BaseModel):
    ids: List[str] = []
    currency: Optional[str] = None

class ConsentCreateRequest(BaseModel):
    type: ConsentType = Field(default=ConsentType.AIS)
    permissions: List[Permission] = Field(min_length=1)
    expiration_at: Optional[datetime] = None
    recurring: bool = True
    accounts: Optional[AccountsScope] = None
    redirect_urls: RedirectURLs
    metadata: Optional[dict] = None

class NextAction(BaseModel):
    type: Literal["SCA_REDIRECT"] = "SCA_REDIRECT"
    authorize_url: AnyHttpUrl

class ConsentLinks(BaseModel):
    self: str
    status: str
    revoke: str

class ConsentCreateResponse(BaseModel):
    id: UUID
    status: Literal["PENDING_SCA"]
    type: ConsentType
    permissions: List[Permission]
    expires_at: datetime
    next_action: NextAction
    links: ConsentLinks
    correlation_id: UUID

class ConsentStatusResponse(BaseModel):
    id: UUID
    status: Literal["PENDING_SCA", "GRANTED", "REJECTED", "EXPIRED", "REVOKED"]
    expires_at: datetime
    correlation_id: UUID


class ProviderRefs(BaseModel):
    sca_id: Optional[str] = None

class ConsentReadResponse(BaseModel):
    id: UUID
    status: Literal["PENDING_SCA", "GRANTED", "REJECTED", "EXPIRED", "REVOKED"]
    type: ConsentType
    permissions: List[Permission]
    expires_at: datetime
    recurring: bool
    redirect_urls: RedirectURLs
    accounts: Optional[AccountsScope] = None
    provider_refs: Optional[ProviderRefs] = None
    links: ConsentLinks
    created_at: datetime
    updated_at: datetime
    correlation_id: UUID
    
class ConsentAuthorizeResponse(BaseModel):
    id: UUID
    status: Literal["PENDING_SCA"]
    sca_id: str
    next_action: NextAction
    deny_url: Optional[AnyHttpUrl] = None
    correlation_id: UUID
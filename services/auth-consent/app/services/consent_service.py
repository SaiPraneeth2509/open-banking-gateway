# app/services/consent_service.py
from __future__ import annotations

import logging
from uuid import uuid4, UUID
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional

from pydantic import AnyHttpUrl
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.consents import create as repo_create
from app.api.schemas.consents import (
    ConsentCreateRequest,
    ConsentCreateResponse,
    NextAction,
    ConsentLinks,
)
from app.utils.hashutils import canonical_sha256
from app.utils.idempotency import read_entry, try_lock, store_final
from app.core.metrics import (
    inc_consents_created,
    inc_consents_revoked,
    inc_consents_status_poll,
)

MAX_EXPIRY_DAYS = 90


def _default_expiry(now: datetime) -> datetime:
    return now + timedelta(days=MAX_EXPIRY_DAYS)


def _clamp_expiry(requested: datetime, now: datetime) -> datetime:
    max_allowed = now + timedelta(days=MAX_EXPIRY_DAYS)
    return min(requested, max_allowed)


async def create_consent(
    payload: ConsentCreateRequest,
    tpp_client_id: str,
    base_url: str,
    correlation_id: UUID,
    idempotency_key: str,
    db: Session,
    client_ip: str | None,
    tenant_id: Optional[str],
) -> Tuple[ConsentCreateResponse, bool, Dict[str, str]]:
    """
    Create a consent with idempotency semantics.

    Returns:
        (response_model, is_replay, stable_headers)
        - is_replay=True -> caller should return HTTP 200 and include Idempotency-Replayed: true
        - is_replay=False -> caller should return HTTP 201
    """
    # ---- Idempotency: compute body hash and check Redis ----
    body_dict = payload.model_dump(mode="json")
    body_sha = canonical_sha256(body_dict)

    existing = None
    try:
        existing = await read_entry(tpp_client_id, idempotency_key)
    except Exception as e:
        logging.warning(
            "Idempotency read failed (continuing without strict idempotency): %s", e
        )

    if existing:
        if existing.get("body_sha256") == body_sha:
            stored = existing.get("response")
            if stored:
                stored_headers = existing.get("headers", {})
                return ConsentCreateResponse(**stored), True, stored_headers
        # same key, different body -> conflict
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="idempotency_conflict"
        )

    # Try to acquire a short lock to avoid races
    locked = False
    try:
        locked = await try_lock(tpp_client_id, idempotency_key, body_sha)
    except Exception as e:
        logging.warning("Idempotency lock failed (continuing): %s", e)

    if not locked:
        # Someone else may be creating it right now; re-check
        try:
            existing = await read_entry(tpp_client_id, idempotency_key)
        except Exception:
            existing = None
        if (
            existing
            and existing.get("body_sha256") == body_sha
            and existing.get("response")
        ):
            return (
                ConsentCreateResponse(**existing["response"]),
                True,
                existing.get("headers", {}),
            )
        # If different body appears with same key, it will 409 on the caller’s retry

    # ---- Create consent (DB) ----
    now = datetime.now(timezone.utc)
    expires_at = (
        _default_expiry(now)
        if payload.expiration_at is None
        else _clamp_expiry(payload.expiration_at, now)
    )

    consent_id = uuid4()

    repo_create(
        db,
        consent_id=consent_id,
        tpp_client_id=tpp_client_id,
        payload=payload,
        expires_at=expires_at,
        status="PENDING_SCA",
        client_ip=client_ip,
        tenant_id=tenant_id,  # persist tenant for multi-tenant routing/metering
    )

    #Metrics: count successful creation exactly once (not on idempotent replays)
    inc_consents_created()

    # Build absolute URLs based on service base_url (e.g., http://localhost:8000/)
    base = base_url.rstrip("/")
    authorize_url: AnyHttpUrl = f"{base}/consents/{consent_id}/authorize"

    links = ConsentLinks(
        self=f"/consents/{consent_id}",
        status=f"/consents/{consent_id}/status",
        revoke=f"/consents/{consent_id}/revoke",
    )

    resp = ConsentCreateResponse(
        id=consent_id,
        status="PENDING_SCA",
        type=payload.type,
        permissions=payload.permissions,
        expires_at=expires_at,
        next_action=NextAction(authorize_url=authorize_url),
        links=links,
        correlation_id=correlation_id,
    )

    # Stable headers (also stored for byte-for-byte consistent replays)
    stable_headers = {
        "X-Request-ID": str(correlation_id),
        "Location": links.self,
    }

    # Store final response so exact replays can return 200 + same headers/body
    try:
        await store_final(
            tpp_client_id,
            idempotency_key,
            body_sha,
            response_dict=resp.model_dump(mode="json"),
            status_code=201,
            headers=stable_headers,
        )
    except Exception as e:
        logging.warning("Idempotency store failed (continuing): %s", e)

    return resp, False, stable_headers

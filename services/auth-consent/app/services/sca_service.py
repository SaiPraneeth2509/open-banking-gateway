from __future__ import annotations
from uuid import uuid4, UUID
from typing import Tuple
from pydantic import AnyHttpUrl


def generate_sca_id() -> str:
    return uuid4().hex

def build_callback_url(base_url: str, consent_id: UUID, sca_id: str, result: str) -> AnyHttpUrl:
    base = base_url.rstrip("/")
    return f"{base}/consents/{consent_id}/authorize/callback?state={sca_id}&result={result}"

def build_authorize_url(base_url: str, consent_id: UUID, sca_id: str) -> AnyHttpUrl:
    return build_callback_url(base_url, consent_id, sca_id, "approved")

def build_deny_url(base_url: str, consent_id: UUID, sca_id: str) -> AnyHttpUrl:
    return build_callback_url(base_url, consent_id, sca_id, "denied")
from __future__ import annotations
import time
from typing import Any, Dict, Optional, Set
import httpx
import jwt
from fastapi import Header, HTTPException, status
from app.core.config import settings

# Required role(s) to call /consents (pick either one)
REQUIRED_ROLES: Set[str] = {"tpp", "consents:create"}
_KID_CACHE: Dict[str, Dict[str, Any]] = {}  
_KID_TTL = 300  # 5 minutes

# Simple in-process caches (per container)
_OIDC_CONF: Optional[Dict[str, Any]] = None
_OIDC_CONF_EXP: float = 0.0
_JWKS_URI: Optional[str] = None

async def _get_oidc_conf() -> Dict[str, Any]:
    global _OIDC_CONF, _OIDC_CONF_EXP, _JWKS_URI
    now = time.time()
    if _OIDC_CONF and now < _OIDC_CONF_EXP:
        return _OIDC_CONF
    url = settings.KEYCLOAK_WELLKNOWN_URL or f"{settings.KEYCLOAK_ISSUER.rstrip('/')}/.well-known/openid-configuration"
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="oidc_config_unavailable")
        conf = r.json()
    _OIDC_CONF = conf
    _JWKS_URI = conf.get("jwks_uri")
    # refresh every 5 minutes
    _OIDC_CONF_EXP = now + 300
    return conf

def _require_roles(payload: Dict[str, Any]) -> None:
    roles: Set[str] = set()
    # Realm roles
    realm = payload.get("realm_access", {}) or {}
    roles.update(realm.get("roles", []) or [])
    # Client roles (resource_access)
    ra = payload.get("resource_access", {}) or {}
    # Collect roles for the audience client, authorized party, and any client
    aud = payload.get("aud")
    if isinstance(aud, list):
        for a in aud:
            roles.update((ra.get(a, {}) or {}).get("roles", []) or [])
    elif isinstance(aud, str):
        roles.update((ra.get(aud, {}) or {}).get("roles", []) or [])
    azp = payload.get("azp")
    if isinstance(azp, str):
        roles.update((ra.get(azp, {}) or {}).get("roles", []) or [])
    # Check required roles
    if roles.isdisjoint(REQUIRED_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_permissions")


async def _get_signing_key(token: str):
    from jwt import PyJWKClient, get_unverified_header
    hdr = get_unverified_header(token)
    kid = hdr.get("kid")

    now = time.time()
    if kid and kid in _KID_CACHE and _KID_CACHE[kid]["exp"] > now:
        return _KID_CACHE[kid]["key"]

    conf = await _get_oidc_conf()
    jwks_uri = conf.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="jwks_unavailable")

    jwk_client = PyJWKClient(jwks_uri)
    key = jwk_client.get_signing_key_from_jwt(token).key

    # cache by kid
    if kid:
        _KID_CACHE[kid] = {"key": key, "exp": now + _KID_TTL}
    return key

async def get_current_client(Authorization: Optional[str] = Header(None)):
    # Optional development bypass
    if settings.SKIP_JWT:
        return {"tpp_client_id": "dev-bypass", "roles": ["tpp"]}

    if not Authorization or not Authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    token = Authorization.split(" ", 1)[1]

    try:
        key = await _get_signing_key(token)
        payload = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=settings.KEYCLOAK_AUDIENCE,  # must match client audience
            issuer=settings.KEYCLOAK_ISSUER,     # must match iss claim
            options={"require": ["exp", "iat"]},
        )
        _require_roles(payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_audience")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_issuer")
    except jwt.PyJWTError:
        # covers signature errors, decode errors, invalid claims, etc.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    except httpx.HTTPError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="jwks_fetch_failed")

    # Pull a stable client id; azp is best, fall back to client_id/aud
    tpp_client_id = payload.get("azp") or (payload.get("client_id") if isinstance(payload.get("client_id"), str) else None)
    if not tpp_client_id:
        aud = payload.get("aud")
        if isinstance(aud, str):
            tpp_client_id = aud
        elif isinstance(aud, list) and aud:
            tpp_client_id = aud[0]
    if not tpp_client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="client_id_missing")

    return {
        "tpp_client_id": tpp_client_id,
        "roles": payload.get("realm_access", {}).get("roles", []),
        "sub": payload.get("sub"),
        "tenant_id": payload.get("tenant_id"),
        "raw": payload,
    }

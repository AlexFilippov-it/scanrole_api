from typing import Dict, Optional

import hashlib
import httpx
from fastapi import Header, HTTPException, status

from cache import TTLCache
from config import get_settings


_introspection_cache = TTLCache(ttl_seconds=60)


def _error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise _error("UNAUTHORIZED", "Missing token", status.HTTP_401_UNAUTHORIZED)
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise _error("UNAUTHORIZED", "Invalid token format", status.HTTP_401_UNAUTHORIZED)
    return parts[1]


async def introspect_token(token: str) -> Dict:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    cache_key = f"token:{token[:12]}:{digest}"
    cached = _introspection_cache.get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()
    if not settings.wp_introspect_url or not settings.wp_introspect_secret:
        raise _error("SERVER_ERROR", "Introspection not configured", status.HTTP_500_INTERNAL_SERVER_ERROR)

    payload = {"token": token}
    headers = {"X-ScanRole-Introspect-Secret": settings.wp_introspect_secret}

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(settings.wp_introspect_url, json=payload, headers=headers)

    if response.status_code >= 500:
        raise _error("SERVER_ERROR", "Introspection failed", status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = response.json()
    _introspection_cache.set(cache_key, data)
    return data


async def require_scope(
    required_scope: str,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Dict:
    token = _extract_bearer(authorization)
    data = await introspect_token(token)
    if not data.get("active"):
        raise _error("UNAUTHORIZED", "Invalid or expired token", status.HTTP_401_UNAUTHORIZED)
    scopes = data.get("scopes") or []
    if required_scope not in scopes:
        raise _error("FORBIDDEN", "Missing required scope", status.HTTP_403_FORBIDDEN)
    return data


async def require_role_explorer(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> Dict:
    return await require_scope("read:role_explorer", authorization)

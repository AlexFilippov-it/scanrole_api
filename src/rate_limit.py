import hashlib
import ipaddress
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class RateLimitStatus:
    allowed: bool
    remaining: int
    reset_ts: int
    retry_after: int


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._data = {}
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._data.clear()

    def hit(self, key: str, limit: int, window_seconds: int) -> RateLimitStatus:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if entry is None or now >= entry["reset"]:
                entry = {"count": 0, "reset": now + window_seconds}
            if entry["count"] >= limit:
                retry_after = max(0, int(entry["reset"] - now))
                return RateLimitStatus(
                    allowed=False,
                    remaining=0,
                    reset_ts=int(entry["reset"]),
                    retry_after=retry_after,
                )
            entry["count"] += 1
            self._data[key] = entry
            remaining = max(0, limit - entry["count"])
            return RateLimitStatus(
                allowed=True,
                remaining=remaining,
                reset_ts=int(entry["reset"]),
                retry_after=0,
            )


def _is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_global


def _first_public_ip(candidates: list[str]) -> Optional[str]:
    for raw in candidates:
        ip = raw.strip()
        if _is_public_ip(ip):
            return ip
    return None


def extract_client_ip(request, trust_proxy: bool) -> str:
    if trust_proxy:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip and _is_public_ip(cf_ip):
            return cf_ip
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",")]
            public_ip = _first_public_ip(parts)
            if public_ip:
                return public_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def extract_token_identifier(authorization: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not authorization:
        return None, None
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None, None
    token = parts[1]
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    token_key = f"token:{digest}"
    token_prefix = token[:8]
    return token_key, token_prefix

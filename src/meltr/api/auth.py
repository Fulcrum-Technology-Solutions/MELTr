"""API key authentication for the management API."""

from __future__ import annotations

import hmac
import ipaddress
import os

from fastapi import HTTPException, Request, status

from meltr.core.config import Config


def resolve_api_key(config: Config) -> str | None:
    env = (os.getenv("MELTR_API_KEY") or "").strip()
    if env:
        return env
    key = (config.api.auth.key or "").strip() if config.api.auth.key else ""
    return key or None


def auth_required(config: Config) -> bool:
    if config.api.auth.enabled:
        return True
    return resolve_api_key(config) is not None


def is_loopback_bind(host: str) -> bool:
    """Return True when the API listen address is loopback-only."""
    value = (host or "").strip().lower()
    if not value:
        return False
    if value in {"127.0.0.1", "localhost", "::1"}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def is_local_request(request: Request) -> bool:
    """Return True when the client connected from loopback.

    Uses the TCP peer address (request.client.host), never X-Forwarded-For.
    """
    if request.client is None:
        return False
    host = (request.client.host or "").strip()
    if not host:
        return False
    if host == "localhost":
        return True
    if host.startswith("::ffff:"):
        host = host.rsplit(":", 1)[-1]
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


async def require_api_key(request: Request) -> None:
    server = request.app.state.server
    config: Config = server.config
    if not auth_required(config):
        return
    if config.api.auth.exempt_loopback and is_local_request(request):
        return
    expected = resolve_api_key(config)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API auth enabled but no API key configured",
        )
    auth = request.headers.get("Authorization", "")
    token = ""
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

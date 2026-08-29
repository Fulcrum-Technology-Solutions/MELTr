"""API key authentication for the management API."""

from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import HTTPException, Request, status

from meltr.core.config import Config


def resolve_api_key(config: Config) -> Optional[str]:
    env = (os.getenv("MELTR_API_KEY") or os.getenv("LOGFORGE_API_KEY") or "").strip()
    if env:
        return env
    key = (config.api.auth.key or "").strip() if config.api.auth.key else ""
    return key or None


def auth_required(config: Config) -> bool:
    if config.api.auth.enabled:
        return True
    return resolve_api_key(config) is not None


async def require_api_key(request: Request) -> None:
    server = request.app.state.server
    config: Config = server.config
    if not auth_required(config):
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

"""Tests for API key authentication helpers."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from meltr.api.auth import auth_required, require_api_key, resolve_api_key
from meltr.core.config import AuthConfig, create_default_config


@pytest.fixture(autouse=True)
def _meltr_home(tmp_path, monkeypatch):
    """Isolate MELTR_HOME so create_default_config does not touch /opt/meltr."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))


def test_auth_required_false_when_no_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    assert auth_required(cfg) is False


def test_auth_required_true_when_env_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "secret")
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    assert auth_required(cfg) is True
    assert resolve_api_key(cfg) == "secret"


def test_auth_required_true_when_enabled_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=True, key=None)
    assert auth_required(cfg) is True


def test_resolve_api_key_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key="config-key")
    assert resolve_api_key(cfg) == "config-key"


def test_resolve_api_key_meltr_env_precedence(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "meltr-key")
    monkeypatch.setenv("LOGFORGE_API_KEY", "logforge-key")
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key="config-key")
    assert resolve_api_key(cfg) == "meltr-key"


def test_resolve_api_key_logforge_env_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.setenv("LOGFORGE_API_KEY", "logforge-key")
    cfg = create_default_config(tmp_path)
    assert resolve_api_key(cfg) == "logforge-key"


def test_resolve_api_key_strips_whitespace(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "  secret  ")
    cfg = create_default_config(tmp_path)
    assert resolve_api_key(cfg) == "secret"


def _make_request(config, headers=None):
    app = MagicMock()
    server = MagicMock()
    server.config = config
    app.state.server = server
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "app": app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_require_api_key_skips_when_auth_not_required(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    await require_api_key(_make_request(cfg))


@pytest.mark.asyncio
async def test_require_api_key_401_missing_token(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "secret")
    cfg = create_default_config(tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(_make_request(cfg))
    assert exc_info.value.status_code == 401
    assert exc_info.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.asyncio
async def test_require_api_key_401_invalid_token(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "secret")
    cfg = create_default_config(tmp_path)
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(_make_request(cfg, {"Authorization": "Bearer wrong"}))
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_api_key_accepts_valid_bearer(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "secret")
    cfg = create_default_config(tmp_path)
    await require_api_key(_make_request(cfg, {"Authorization": "Bearer secret"}))


@pytest.mark.asyncio
async def test_require_api_key_503_when_enabled_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=True, key=None)
    with pytest.raises(HTTPException) as exc_info:
        await require_api_key(_make_request(cfg, {"Authorization": "Bearer anything"}))
    assert exc_info.value.status_code == 503

"""Tests for template preview API and CLI."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from meltr.api.server import APIServer
from meltr.core.config import AuthConfig, create_default_config
from meltr.entities.registry import EntityRegistry
from meltr.templates.cache import TemplateCache
from meltr.templates.loader import TemplateLoader

FIXTURES = Path(__file__).parent / "fixtures" / "templates"
TEMPLATE_ID = "testvendor/testproduct/events/preview"


@pytest.fixture
def preview_client(tmp_path, monkeypatch) -> TestClient:
    """APIServer TestClient with fixture template and entity registry."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("LOGFORGE_API_KEY", raising=False)

    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    cfg.templates.local_path = str(FIXTURES)
    cfg.templates.default_path = str(FIXTURES)
    cfg.templates.custom_path = str(FIXTURES / "custom")

    loader = TemplateLoader(cfg)
    cache = TemplateCache(loader, ttl=3600)
    registry = EntityRegistry(cfg)

    server = APIServer(cfg)
    server.app.state.registry = registry
    server.app.state.template_cache = cache
    return TestClient(server.app)


@pytest.fixture
def auth_preview_client(preview_client, monkeypatch) -> TestClient:
    monkeypatch.setenv("MELTR_API_KEY", "preview-secret")
    return preview_client


def test_preview_route_missing_returns_404(preview_client: TestClient) -> None:
    response = preview_client.post(
        "/api/templates/unknown/vendor/ds/t/preview",
        json={"count": 1},
    )
    assert response.status_code == 404


def test_preview_returns_rendered_events(preview_client: TestClient) -> None:
    response = preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["template_id"] == TEMPLATE_ID
    assert data["count"] == 2
    assert len(data["events"]) == 2
    for event in data["events"]:
        parsed = json.loads(event.strip())
        assert parsed["message"] == "preview test"
        assert "org" in parsed


def test_preview_default_count_one(preview_client: TestClient) -> None:
    response = preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert len(response.json()["events"]) == 1


def test_preview_count_validation(preview_client: TestClient) -> None:
    too_many = preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 21},
    )
    assert too_many.status_code == 422

    too_few = preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 0},
    )
    assert too_few.status_code == 422


def test_preview_requires_auth_when_key_set(auth_preview_client: TestClient) -> None:
    response = auth_preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 1},
    )
    assert response.status_code == 401


def test_preview_with_bearer_auth(auth_preview_client: TestClient) -> None:
    response = auth_preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 1},
        headers={"Authorization": "Bearer preview-secret"},
    )
    assert response.status_code == 200


def test_preview_does_not_start_generators(preview_client: TestClient) -> None:
    """Preview must not touch the engine or start generators."""
    response = preview_client.post(
        f"/api/templates/{TEMPLATE_ID}/preview",
        json={"count": 1},
    )
    assert response.status_code == 200
    assert (
        not hasattr(preview_client.app.state, "engine") or preview_client.app.state.engine is None
    )


def test_cli_preview_calls_api(tmp_path, monkeypatch) -> None:
    from typer.testing import CliRunner

    from meltr.cli.templates import app as templates_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    mock_response = type(
        "Resp",
        (),
        {
            "status_code": 200,
            "json": lambda self: {
                "template_id": TEMPLATE_ID,
                "count": 1,
                "events": ['{"message": "preview test"}'],
            },
        },
    )()

    with patch("meltr.cli.api_client.get_api_client") as mock_get_client:
        mock_client = mock_get_client.return_value
        mock_client.post.return_value = mock_response

        runner = CliRunner()
        result = runner.invoke(
            templates_app,
            ["preview", TEMPLATE_ID, "--count", "1"],
        )

    assert result.exit_code == 0
    mock_client.require_service_running.assert_called_once()
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert TEMPLATE_ID in call_args[0][0]
    assert call_args[1]["json"] == {"count": 1}

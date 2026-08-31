"""Tests for community update detection API and CLI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from meltr.api.server import APIServer
from meltr.community.client import CommunityAPIError
from meltr.community.updates import get_remote_collection_version
from meltr.core.config import AuthConfig, create_default_config
from meltr.entities.registry import EntityRegistry
from meltr.templates.cache import TemplateCache
from meltr.templates.loader import TemplateLoader

FIXTURES = Path(__file__).parent / "fixtures" / "templates"
TEMPLATE_ID = "testvendor/testproduct/events/preview"
VENDOR_ID = "testvendor"
PRODUCT_ID = "testproduct"


def _write_installed_product(base: Path, version: str = "1.0.0") -> Path:
    """Create default/testvendor/testproduct with collection.json and one template."""
    product_dir = base / "default" / VENDOR_ID / PRODUCT_ID
    events_dir = product_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    (product_dir / "collection.json").write_text(
        json.dumps({"version": version, "templates": ["events/preview"]}),
        encoding="utf-8",
    )
    (events_dir / "preview.j2").write_text(
        '{{ {"message": "preview test", "org": "acme"} | tojson }}\n',
        encoding="utf-8",
    )
    (events_dir / "preview.meta.yaml").write_text(
        "vendor: testvendor\n"
        "product: testproduct\n"
        "data_source: events\n"
        "description: Preview fixture template for tests\n"
        "format: JSON\n"
        "is_generator: true\n",
        encoding="utf-8",
    )
    return base


@pytest.fixture
def updates_client(tmp_path, monkeypatch) -> TestClient:
    """APIServer TestClient with installed product fixture."""
    templates_root = _write_installed_product(tmp_path / "templates", version="1.0.0")

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    monkeypatch.delenv("MELTR_API_KEY", raising=False)

    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    cfg.templates.local_path = str(templates_root)
    cfg.templates.default_path = str(templates_root / "default")
    cfg.templates.custom_path = str(templates_root / "custom")

    loader = TemplateLoader(cfg)
    cache = TemplateCache(loader, ttl=3600)
    registry = EntityRegistry(cfg)

    server = APIServer(cfg)
    server.app.state.registry = registry
    server.app.state.template_cache = cache
    return TestClient(server.app)


def _mock_client_newer_remote() -> MagicMock:
    client = MagicMock()
    client.get_product_detail.return_value = {"collection_version": "2.0.0", "product": PRODUCT_ID}
    return client


def test_community_updates_returns_stale_packages(updates_client: TestClient) -> None:
    with patch(
        "meltr.api.endpoints.community.CommunityAPIClient",
        return_value=_mock_client_newer_remote(),
    ):
        response = updates_client.get("/api/community/updates")

    assert response.status_code == 200
    data = response.json()
    assert len(data["updates"]) == 1
    update = data["updates"][0]
    assert update["vendor_id"] == VENDOR_ID
    assert update["product_id"] == PRODUCT_ID
    assert update["local_version"] == "1.0.0"
    assert update["remote_version"] == "2.0.0"


def test_community_updates_empty_when_up_to_date(updates_client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.return_value = {"collection_version": "1.0.0"}

    with patch(
        "meltr.api.endpoints.community.CommunityAPIClient",
        return_value=mock_client,
    ):
        response = updates_client.get("/api/community/updates")

    assert response.status_code == 200
    assert response.json()["updates"] == []


def test_community_updates_api_error_returns_502(updates_client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    with patch(
        "meltr.api.endpoints.community.CommunityAPIClient",
        return_value=mock_client,
    ):
        response = updates_client.get("/api/community/updates")

    assert response.status_code == 502


def test_get_remote_collection_version_soft_fail_returns_none() -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    result = get_remote_collection_version(mock_client, VENDOR_ID, PRODUCT_ID, soft_fail=True)

    assert result is None


def test_get_remote_collection_version_propagates_api_error_by_default() -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    with pytest.raises(CommunityAPIError, match="registry unavailable"):
        get_remote_collection_version(mock_client, VENDOR_ID, PRODUCT_ID)


def test_list_templates_registry_down_soft_fails(updates_client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    with patch(
        "meltr.api.endpoints.templates.CommunityAPIClient",
        return_value=mock_client,
    ):
        response = updates_client.get("/api/templates")

    assert response.status_code == 200
    templates = response.json()["templates"]
    match = [t for t in templates if t["id"] == TEMPLATE_ID]
    assert len(match) == 1
    assert match[0]["version"] == "1.0.0"
    assert match[0]["remote_version"] is None


def test_get_template_registry_down_soft_fails(updates_client: TestClient) -> None:
    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    with patch(
        "meltr.api.endpoints.templates.CommunityAPIClient",
        return_value=mock_client,
    ):
        response = updates_client.get(f"/api/templates/{TEMPLATE_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"
    assert data["remote_version"] is None


def test_list_templates_includes_version_fields(updates_client: TestClient) -> None:
    with patch(
        "meltr.api.endpoints.templates.CommunityAPIClient",
        return_value=_mock_client_newer_remote(),
    ):
        response = updates_client.get("/api/templates")

    assert response.status_code == 200
    templates = response.json()["templates"]
    match = [t for t in templates if t["id"] == TEMPLATE_ID]
    assert len(match) == 1
    row = match[0]
    assert row["version"] == "1.0.0"
    assert row["remote_version"] == "2.0.0"


def test_get_template_includes_version_fields(updates_client: TestClient) -> None:
    with patch(
        "meltr.api.endpoints.templates.CommunityAPIClient",
        return_value=_mock_client_newer_remote(),
    ):
        response = updates_client.get(f"/api/templates/{TEMPLATE_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"
    assert data["remote_version"] == "2.0.0"


def test_cli_check_updates_prints_stale_list(tmp_path, monkeypatch) -> None:
    from meltr.cli.templates import app as templates_app

    _write_installed_product(tmp_path / "templates", version="1.0.0")
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    with patch(
        "meltr.cli.templates.CommunityAPIClient",
        return_value=_mock_client_newer_remote(),
    ):
        runner = CliRunner()
        result = runner.invoke(templates_app, ["check-updates"])

    assert result.exit_code == 0
    assert "1 update(s) available" in result.output
    assert f"{VENDOR_ID}/{PRODUCT_ID}" in result.output


def test_cli_check_updates_exit_zero_when_none(tmp_path, monkeypatch) -> None:
    from meltr.cli.templates import app as templates_app

    _write_installed_product(tmp_path / "templates", version="1.0.0")
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    mock_client = MagicMock()
    mock_client.get_product_detail.return_value = {"collection_version": "1.0.0"}

    with patch(
        "meltr.cli.templates.CommunityAPIClient",
        return_value=mock_client,
    ):
        runner = CliRunner()
        result = runner.invoke(templates_app, ["check-updates"])

    assert result.exit_code == 0
    assert "All installed packages are up to date" in result.output


def test_cli_check_updates_api_error_nonzero_exit(tmp_path, monkeypatch) -> None:
    from meltr.cli.templates import app as templates_app

    _write_installed_product(tmp_path / "templates", version="1.0.0")
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    mock_client = MagicMock()
    mock_client.get_product_detail.side_effect = CommunityAPIError("registry unavailable")

    with patch(
        "meltr.cli.templates.CommunityAPIClient",
        return_value=mock_client,
    ):
        runner = CliRunner()
        result = runner.invoke(templates_app, ["check-updates"])

    assert result.exit_code == 1
    assert "registry unavailable" in result.output

"""Extended Phase 6 coverage: storage, filters, path resolver, service, API client."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
import typer
import yaml
from typer.testing import CliRunner

from meltr.cli.api_client import APIClient, _get_default_api_url, get_api_client
from meltr.community.package import backup_vendor_directory
from meltr.community.version import (
    compare_versions,
    format_version_status,
    is_update_available,
)
from meltr.core.config import create_default_config, save_config
from meltr.entities.storage import EntityStorage
from meltr.entities.validator import validate_entities
from meltr.outputs.path_resolver import (
    PathTemplateContext,
    resolve_path_template,
    sanitize_filename_component,
    validate_path_template,
)
from meltr.templates.filters import (
    add_seconds,
    format_datetime,
    iso8601,
    now,
    random_choice,
    random_int,
    register_filters,
    subtract_seconds,
    unix_timestamp,
)
from meltr.templates.metadata import parse_metadata

SAMPLE_ENTITIES = Path(__file__).parent.parent / "src" / "meltr" / "data" / "entities.sample.yaml"
PREVIEW_META = Path(__file__).parent / "fixtures" / "templates" / "testvendor" / "testproduct" / "events" / "preview.meta.yaml"


# --- version ---


def test_compare_versions_ordering():
    assert compare_versions("1.0.0", "1.0.1") == -1
    assert compare_versions("2.0.0", "1.9.9") == 1
    assert compare_versions("v1.2", "1.2.0") == 0
    assert is_update_available("1.0.0", "1.1.0") is True
    assert format_version_status("1.0.0", "1.1.0") == "1.0.0 → 1.1.0 (update available)"
    assert format_version_status("2.0.0", "1.0.0") == "2.0.0 (local is newer than remote 1.0.0)"
    assert format_version_status("1.0.0", "1.0.0") == "1.0.0 (up to date)"
    assert "unknown" in format_version_status("1.0.0", None)


def test_compare_versions_invalid_raises():
    with pytest.raises(ValueError, match="Invalid version"):
        compare_versions("not-a-version", "1.0.0")


# --- entity storage ---


def test_entity_storage_load_save_round_trip(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    shutil.copy(SAMPLE_ENTITIES, entities_path)
    storage = EntityStorage(
        entities_path=entities_path,
        auto_save=False,
        backup_enabled=True,
        backup_count=2,
    )
    data = storage.load(strict=False)
    assert data["organization"]["name"] == "Acme Corporation"
    data["organization"]["name"] = "Updated Corp"
    storage.save(data)
    reloaded = storage.load(strict=False)
    assert reloaded["organization"]["name"] == "Updated Corp"


def test_entity_storage_missing_file_raises(tmp_path):
    storage = EntityStorage(entities_path=tmp_path / "missing.yaml", auto_save=False)
    with pytest.raises(FileNotFoundError):
        storage.load()


def test_entity_storage_invalid_yaml_raises(tmp_path):
    bad = tmp_path / "entities.yaml"
    bad.write_text(": [invalid", encoding="utf-8")
    storage = EntityStorage(entities_path=bad, auto_save=False)
    with pytest.raises(ValueError, match="Invalid YAML"):
        storage.load(strict=False)


def test_validate_entities_sample_file():
    with SAMPLE_ENTITIES.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    validate_entities(data)


# --- path resolver ---


def test_sanitize_filename_component():
    assert sanitize_filename_component('bad/name?') == "bad_name_"
    assert sanitize_filename_component("  ok  ") == "ok"


def test_path_template_context_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    ctx = PathTemplateContext(
        generator_name="gen1",
        output_name="file-out",
        template_metadata={"vendor": "v", "product": "p", "data_source": "d"},
        organization_name="Acme",
        timezone="UTC",
    )
    variables = ctx.get_variables()
    assert variables["generator"] == "gen1"
    assert variables["vendor"] == "v"
    assert variables["organization_name"] == "Acme"


def test_resolve_path_template_with_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    ctx = PathTemplateContext("gen1", "out", {"vendor": "okta"}, timezone="UTC")
    resolved = resolve_path_template("{vendor}/{generator}.log", ctx)
    assert "okta" in str(resolved)
    assert str(resolved).endswith("gen1.log")


def test_validate_path_template_warnings():
    ok, warnings = validate_path_template("")
    assert ok is False
    ok, warnings = validate_path_template("../escape/{gen}.log")
    assert warnings
    ok, warnings = validate_path_template("x" * 600)
    assert any("long" in w for w in warnings)


# --- template filters ---


def test_template_filter_now_and_arithmetic():
    wrapper = now("UTC")
    assert (wrapper + 60)._dt > wrapper._dt
    assert (wrapper - 30)._dt < wrapper._dt


def test_template_filter_format_datetime():
    dt = datetime(2026, 8, 29, 15, 30, 0)
    assert format_datetime(dt, "%Y-%m-%d") == "2026-08-29"
    assert iso8601(dt).startswith("2026-08-29")
    assert unix_timestamp(dt) > 0
    assert add_seconds(dt, 10).year == 2026
    assert subtract_seconds(dt, 10).year == 2026


def test_template_filter_random_helpers():
    assert 1 <= random_int(1, 3) <= 3
    assert random_choice(["a", "b"]) in ("a", "b")


def test_parse_metadata_fixture():
    meta = parse_metadata(PREVIEW_META)
    assert meta.vendor == "testvendor"
    assert meta.is_generator is True


# --- API client ---


def test_api_client_sets_bearer_header(monkeypatch):
    monkeypatch.setenv("MELTR_API_KEY", "cli-key")
    client = APIClient(api_url="http://127.0.0.1:9999")
    assert client.session.headers["Authorization"] == "Bearer cli-key"


def test_api_client_check_health_ok():
    client = APIClient(api_url="http://127.0.0.1:8080")
    resp = MagicMock(status_code=200)
    client.session.get = MagicMock(return_value=resp)
    ok, err = client.check_health()
    assert ok is True
    assert err is None


def test_api_client_check_health_connection_refused():
    client = APIClient(api_url="http://127.0.0.1:8080")
    client.session.get = MagicMock(
        side_effect=requests.exceptions.ConnectionError("Connection refused")
    )
    ok, err = client.check_health()
    assert ok is False
    assert "refused" in err.lower()


def test_api_client_require_service_running_exits():
    client = APIClient(api_url="http://127.0.0.1:8080")
    client.check_health = MagicMock(return_value=(False, "down"))
    with pytest.raises(typer.Exit):
        client.require_service_running()


def test_get_default_api_url_from_env(monkeypatch):
    monkeypatch.setenv("MELTR_API_URL", "http://custom:9000")
    assert _get_default_api_url() == "http://custom:9000"


def test_get_default_api_url_from_config(tmp_path, monkeypatch):
    monkeypatch.delenv("MELTR_API_URL", raising=False)
    monkeypatch.delenv("LOGFORGE_API_URL", raising=False)
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    cfg.api.port = 9090
    save_config(cfg, tmp_path / "config.yaml")
    assert _get_default_api_url() == "http://127.0.0.1:9090"


def test_get_api_client_factory():
    client = get_api_client(api_url="http://127.0.0.1:8080", api_key="k")
    assert client.api_url == "http://127.0.0.1:8080"
    assert client.api_key == "k"


# --- package backup ---


def test_backup_vendor_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    vendor_dir = tmp_path / "templates" / "default" / "acme"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "vendor.yaml").write_text("vendor: acme\n", encoding="utf-8")
    backup = backup_vendor_directory(vendor_dir, "acme", backup_count=3)
    assert backup.exists()
    assert (backup / "vendor.yaml").is_file()


# --- service ---


def test_logforge_service_init(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")

    from meltr.service import LogForgeService

    service = LogForgeService(config_path=tmp_path / "config.yaml")
    assert service.engine is not None
    assert service.registry is not None
    service.engine.shutdown()
    service.registry.close()


def test_logforge_service_start_stop_mocked(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")

    from meltr.service import LogForgeService

    service = LogForgeService(config_path=tmp_path / "config.yaml")
    service.api_server.start = MagicMock()
    service.api_server.is_running = MagicMock(return_value=True)
    service.api_server.stop = MagicMock()

    service.start()
    service.api_server.start.assert_called_once()
    service.stop()
    service.registry.close()


# --- CLI generators ---


def test_cli_generators_start_stop_status(tmp_path, monkeypatch):
    from meltr.cli.generators import app as generators_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    class Resp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class Client:
        def require_service_running(self):
            return None

        def get(self, path):
            if path.endswith("/gen-a"):
                return Resp(
                    {
                        "name": "gen-a",
                        "state": "RUNNING",
                        "template": "v/p/d/e",
                        "enabled": True,
                        "timezone": "UTC",
                        "frequency": {"base_rate": 1.0, "current_rate": 1.0},
                        "outputs": ["file-out"],
                        "statistics": {
                            "events_generated": 5,
                            "errors": 0,
                            "uptime": 120,
                        },
                    }
                )
            return Resp({"generators": []})

        def post(self, path, json=None):
            return Resp({"message": "ok", "state": "RUNNING"})

    with patch("meltr.cli.generators.get_api_client", return_value=Client()):
        runner = CliRunner()
        assert runner.invoke(generators_app, ["start", "gen-a"]).exit_code == 0
        assert runner.invoke(generators_app, ["stop", "gen-a"]).exit_code == 0
        assert runner.invoke(generators_app, ["status", "gen-a"]).exit_code == 0


# --- HTTP batch mode ---


def test_http_batch_mode_initialize_starts_timer():
    from meltr.outputs.http import HTTPOutputHandler

    handler = HTTPOutputHandler(
        name="batch",
        url="https://example.invalid/events",
        streaming=False,
        batch_interval=60,
    )
    handler.initialize()
    assert handler._batch_timer is not None
    handler.close()


def test_http_get_statistics_keys():
    from meltr.outputs.http import HTTPOutputHandler

    handler = HTTPOutputHandler(name="h", url="https://example.invalid/x")
    stats = handler.get_statistics()
    assert "events_sent" in stats
    assert "events_failed" in stats


# --- register all filters smoke ---


def test_register_filters_smoke():
    from jinja2 import Environment

    env = Environment()  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    register_filters(env)
    rendered = env.from_string("{{ random_int(1, 10) }}").render()
    assert rendered.isdigit()

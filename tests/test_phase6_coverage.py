"""Targeted tests for Phase 6 coverage (auth, schedule, pipeline, preview, community, outputs)."""

from __future__ import annotations

import gzip
import json
import tarfile
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
import requests
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from meltr.community.client import (
    CommunityAPIClient,
    CommunityAPIError,
    CommunityAPINotFoundError,
    CommunityAPIRateLimitError,
)
from meltr.community.package import (
    PackageError,
    PackageValidationError,
    extract_forge_package,
    validate_package_structure,
)
from meltr.core.config import (
    AuthConfig,
    FrequencyConfig,
    FrequencyVariation,
    OutputDefinition,
    create_default_config,
    save_config,
)
from meltr.core.frequency import (
    _parse_time,
    calculate_rate,
    calculate_rate_from_template_metadata,
)
from meltr.core.pidfile import (
    cmdline_suggests_logforge,
    read_service_pid,
    remove_service_pidfile,
    write_service_pidfile,
)
from meltr.core.schedule import ScheduleConfig, evaluate_schedule
from meltr.outputs.http import HTTPOutputHandler
from meltr.outputs.syslog import SyslogOutputHandler
from meltr.templates.filters import DateTimeWrapper, register_filters
from meltr.templates.metadata import TemplateMetadata


# --- frequency ---


def test_calculate_rate_no_variation():
    cfg = FrequencyConfig(base_rate=2.5, variation=None)
    assert calculate_rate(cfg) == 2.5


def test_calculate_rate_with_matching_variation():
    cfg = FrequencyConfig(
        base_rate=1.0,
        variation=[
            FrequencyVariation(days=[1, 2, 3, 4, 5], time="00:00-23:59", multiplier=2.0),
        ],
    )
    with mock.patch("meltr.core.frequency.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 8, 28, 12, 0)  # Friday
        assert calculate_rate(cfg) == 2.0


def test_calculate_rate_parse_time_invalid():
    assert _parse_time("bad") == time(0, 0)


def test_calculate_rate_from_template_metadata_defaults():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
    )
    assert calculate_rate_from_template_metadata(meta) == 1.0


def test_calculate_rate_from_template_metadata_zero_frequency():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
        base_frequency=-1,
    )
    assert calculate_rate_from_template_metadata(meta) == 0.0


def test_calculate_rate_from_template_metadata_business_hours():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
        base_frequency=3600,
        time_patterns=["business_hours"],
        business_hours_multiplier=2.0,
    )
    friday_noon = datetime(2026, 8, 28, 12, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("meltr.core.frequency.datetime") as mock_dt:
        mock_dt.now.return_value = friday_noon
        rate = calculate_rate_from_template_metadata(meta, timezone="UTC")
    assert rate == pytest.approx(2.0)


def test_calculate_rate_from_template_metadata_weekend():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
        base_frequency=3600,
        time_patterns=["weekend"],
        weekend_multiplier=0.5,
    )
    saturday = datetime(2026, 8, 29, 12, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("meltr.core.frequency.datetime") as mock_dt:
        mock_dt.now.return_value = saturday
        rate = calculate_rate_from_template_metadata(meta, timezone="UTC")
    assert rate == pytest.approx(0.5)


def test_calculate_rate_from_template_metadata_night_hours():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
        base_frequency=3600,
        time_patterns=["night_hours"],
        night_hours_multiplier=0.25,
    )
    friday_night = datetime(2026, 8, 28, 22, 0, tzinfo=ZoneInfo("UTC"))
    with mock.patch("meltr.core.frequency.datetime") as mock_dt:
        mock_dt.now.return_value = friday_night
        rate = calculate_rate_from_template_metadata(meta, timezone="UTC")
    assert rate == pytest.approx(0.25)


def test_calculate_rate_from_template_invalid_timezone_falls_back():
    meta = TemplateMetadata(
        vendor="v",
        product="p",
        data_source="d",
        description="x",
        format="JSON",
        is_generator=True,
        base_frequency=3600,
    )
    rate = calculate_rate_from_template_metadata(meta, timezone="Not/A/Zone")
    assert rate == pytest.approx(1.0)


# --- pidfile ---


def test_pidfile_round_trip(tmp_path):
    path = write_service_pidfile(4242, home=tmp_path)
    assert path.is_file()
    assert read_service_pid(home=tmp_path) == 4242
    remove_service_pidfile(home=tmp_path)
    assert read_service_pid(home=tmp_path) is None


def test_read_service_pid_invalid_content(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.paths import get_pidfile_path

    pid_path = get_pidfile_path(tmp_path)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text("not-a-pid", encoding="ascii")
    assert read_service_pid(home=tmp_path) is None


def test_cmdline_suggests_logforge_non_linux():
    with patch("meltr.core.pidfile.sys.platform", "darwin"):
        assert cmdline_suggests_logforge(1) is True


def test_cmdline_suggests_logforge_linux_missing_proc():
    with patch("meltr.core.pidfile.sys.platform", "linux"):
        with patch("meltr.core.pidfile.Path") as path_cls:
            path_cls.return_value.read_bytes.side_effect = FileNotFoundError()
            assert cmdline_suggests_logforge(99) is False


# --- schedule edge cases ---


def test_schedule_invalid_timezone_falls_back_to_utc():
    schedule = ScheduleConfig(
        mode="window",
        days=["fri"],
        time="09:00-17:00",
        timezone="Invalid/Zone",
    )
    now = datetime(2026, 8, 28, 10, 0, tzinfo=ZoneInfo("UTC"))
    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=now)
    assert decision.emit is True


def test_schedule_duration_unparseable_never_completes_burst():
    schedule = ScheduleConfig(mode="burst", duration="not-a-duration", count=None)
    started = datetime(2026, 8, 29, 0, 0, tzinfo=ZoneInfo("UTC"))
    now = started + timedelta(hours=24)
    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)
    assert decision.emit is True


def test_schedule_unknown_mode_defaults_emit():
    schedule = ScheduleConfig(mode="continuous")
    schedule.mode = "legacy"  # type: ignore[assignment]
    now = datetime(2026, 8, 29, 0, 0, tzinfo=ZoneInfo("UTC"))
    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=now)
    assert decision.emit is True


# --- HTTP metadata + headers ---


def test_http_wrap_event_with_metadata():
    handler = HTTPOutputHandler(name="hec", url="https://example.invalid/hec")
    handler.include_metadata = True
    handler.generator_name = "lab::0"
    handler.timezone = "UTC"
    handler.template_metadata = {
        "template_id": "v/p/d/e",
        "vendor": "v",
        "product": "p",
        "data_source": "d",
    }
    wrapped = handler._wrap_event_with_metadata({"msg": "hi"})
    assert wrapped["event"] == {"msg": "hi"}
    assert wrapped["logforge_metadata"]["generator"] == "lab::0"
    assert wrapped["logforge_metadata"]["template_id"] == "v/p/d/e"


def test_http_sanitize_header_values():
    handler = HTTPOutputHandler(name="h", url="https://example.invalid/x")
    assert handler._sanitize_header_value("Authorization", "Bearer secret") == "Bearer ***"
    assert handler._sanitize_header_value("Authorization", "Splunk hec") == "Splunk ***"
    assert handler._sanitize_header_value("Authorization", "Basic abc") == "Basic ***"
    assert handler._sanitize_header_value("Authorization", "custom") == "***"
    assert handler._sanitize_header_value("X-API-Key", "key") == "***"
    assert handler._sanitize_header_value("Content-Type", "application/json") == "application/json"


def test_http_truncate_response_body():
    handler = HTTPOutputHandler(name="h", url="https://example.invalid/x")
    assert handler._truncate_response_body("short") == "short"
    long_body = "x" * 300
    assert handler._truncate_response_body(long_body).endswith("...")
    assert len(handler._truncate_response_body(long_body)) == 203


def test_http_send_single_event_with_metadata(monkeypatch):
    handler = HTTPOutputHandler(name="h", url="https://example.invalid/hec", streaming=True)
    handler.include_metadata = True
    handler.generator_name = "gen"
    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"ok"

        def raise_for_status(self):
            return None

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("meltr.outputs.http.requests.request", fake_request)
    handler._send_single_event('{"event":"data"}')
    assert "logforge_metadata" in captured["json"]
    assert captured["json"]["event"]["event"] == "data"


def test_http_substitute_env_vars(monkeypatch):
    monkeypatch.setenv("HEC_TOKEN", "from-env")
    handler = HTTPOutputHandler(
        name="h",
        url="https://example.invalid/x",
        headers={"Authorization": "Splunk ${HEC_TOKEN}"},
    )
    assert handler._substituted_headers["Authorization"] == "Splunk from-env"


def test_http_from_config_include_metadata():
    definition = OutputDefinition(
        name="cribl",
        type="http",
        url="https://cribl.example/hec",
        include_metadata=True,
    )
    handler = HTTPOutputHandler.from_config(definition)
    assert handler.include_metadata is True


def test_http_from_config_missing_url_raises():
    definition = OutputDefinition(name="bad", type="http", url=None)
    with pytest.raises(ValueError, match="requires 'url'"):
        HTTPOutputHandler.from_config(definition)


# --- syslog ---


def test_syslog_handler_rfc5424_message():
    handler = SyslogOutputHandler(
        name="sys",
        host="127.0.0.1",
        port=514,
        protocol="udp",
        format="rfc5424",
    )
    msg = handler._format_rfc5424("test event")
    assert msg.startswith("<")
    assert "test event" in msg


def test_syslog_handler_rfc3164_message():
    handler = SyslogOutputHandler(
        name="sys",
        host="127.0.0.1",
        format="rfc3164",
    )
    msg = handler._format_rfc3164("legacy event")
    assert "legacy event" in msg


def test_syslog_invalid_facility_raises():
    with pytest.raises(ValueError, match="Invalid syslog facility"):
        SyslogOutputHandler(name="s", host="h", facility="invalid")


def test_syslog_from_config():
    definition = OutputDefinition(
        name="sys",
        type="syslog",
        host="syslog.local",
        port=5514,
        protocol="tcp",
        facility="local1",
        severity="warning",
    )
    handler = SyslogOutputHandler.from_config(definition)
    assert handler.host == "syslog.local"
    assert handler.port == 5514


# --- community client ---


def _mock_response(status_code=200, json_data=None, content=b'{"ok":true}', headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = headers or {}
    resp.json.return_value = json_data if json_data is not None else {"ok": True}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def test_community_client_get_health():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(return_value=_mock_response(json_data={"status": "ok"}))
    assert client.get_health()["status"] == "ok"


def test_community_client_not_found():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(return_value=_mock_response(status_code=404))
    with pytest.raises(CommunityAPINotFoundError):
        client.get_vendors()


def test_community_client_rate_limit():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(
        return_value=_mock_response(status_code=429, headers={"Retry-After": "30"})
    )
    with pytest.raises(CommunityAPIRateLimitError, match="Retry after 30"):
        client.get_vendors()


def test_community_client_timeout():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(side_effect=requests.exceptions.Timeout("slow"))
    with pytest.raises(CommunityAPIError, match="timeout"):
        client.get_vendors()


def test_community_client_connection_error():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(side_effect=requests.exceptions.ConnectionError("down"))
    with pytest.raises(CommunityAPIError, match="Connection error"):
        client.get_product_detail("v", "p")


def test_community_client_search_templates_params():
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")
    client.session.request = MagicMock(return_value=_mock_response(json_data={"vendors": []}))
    client.search_templates(query="okta", vendor_id="okta", page_size=200)
    params = client.session.request.call_args.kwargs["params"]
    assert params["q"] == "okta"
    assert params["vendor_id"] == "okta"
    assert params["page_size"] == 100


def test_community_client_download_vendor_package(tmp_path):
    client = CommunityAPIClient(base_url="https://registry.test/api/v1")

    class FakeStreamResponse:
        status_code = 200
        headers = {"Content-Length": "5"}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=8192):
            yield b"hello"

    client.session.get = MagicMock(return_value=FakeStreamResponse())
    out = tmp_path / "pkg.forge"
    result = client.download_vendor_package("acme", out)
    assert result == out
    assert out.read_bytes() == b"hello"


def test_community_client_wait_for_rate_limit():
    client = CommunityAPIClient()
    with patch("meltr.community.client.time.sleep") as sleep_mock:
        client.wait_for_rate_limit(5)
        sleep_mock.assert_called_once_with(5)


# --- package extract ---


def _make_forge_package(tmp_path: Path, vendor_id: str = "testvendor") -> Path:
    vendor_dir = tmp_path / "build" / vendor_id
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "vendor.yaml").write_text("vendor: testvendor\n", encoding="utf-8")
    pkg = tmp_path / "test.forge"
    with tarfile.open(pkg, "w:gz") as tar:
        tar.add(vendor_dir, arcname=vendor_id)
    return pkg


def test_extract_forge_package_success(tmp_path):
    pkg = _make_forge_package(tmp_path)
    extract_to = tmp_path / "extract"
    vendor_dir = extract_forge_package(pkg, extract_to)
    assert vendor_dir.name == "testvendor"
    assert (vendor_dir / "vendor.yaml").is_file()


def test_extract_forge_package_missing_file(tmp_path):
    with pytest.raises(PackageError, match="not found"):
        extract_forge_package(tmp_path / "missing.forge", tmp_path / "out")


def test_extract_forge_package_empty_archive(tmp_path):
    pkg = tmp_path / "empty.forge"
    with tarfile.open(pkg, "w:gz"):
        pass
    with pytest.raises(PackageError, match="empty"):
        extract_forge_package(pkg, tmp_path / "out")


def test_validate_package_structure(tmp_path):
    vendor_dir = tmp_path / "vendor"
    vendor_dir.mkdir()
    (vendor_dir / "vendor.yaml").write_text("vendor: v\n", encoding="utf-8")
    product = vendor_dir / "product"
    product.mkdir()
    (product / "product.meta.yaml").write_text("product: product\n", encoding="utf-8")
    assert validate_package_structure(vendor_dir) is True


# --- CLI: pipelines, generators, config ---


def _mock_api_client(responses: dict):
    class Resp:
        def __init__(self, status_code=200, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError()

        def json(self):
            return self._payload

    class Client:
        def require_service_running(self):
            return None

        def get(self, path):
            return Resp(**responses.get(("GET", path), {"payload": {}}))

        def post(self, path, json=None):
            return Resp(**responses.get(("POST", path), {"payload": {}}))

    return Client()


def test_cli_pipelines_list(tmp_path, monkeypatch):
    from meltr.cli.pipelines import app as pipelines_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    payload = {
        "pipelines": [
            {
                "name": "lab",
                "state": "STOPPED",
                "streams": [{"name": "lab::0"}],
                "enabled": True,
            }
        ]
    }
    with patch("meltr.cli.pipelines.get_api_client", return_value=_mock_api_client({("GET", "/api/pipelines"): {"payload": payload}})):
        result = CliRunner().invoke(pipelines_app, ["list"])
    assert result.exit_code == 0
    assert "lab" in result.output


def test_cli_pipelines_start_stop_status(tmp_path, monkeypatch):
    from meltr.cli.pipelines import app as pipelines_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    start_payload = {"message": "Pipeline started", "state": "RUNNING"}
    stop_payload = {"message": "Pipeline stopped", "state": "STOPPED"}
    detail_payload = {
        "name": "lab",
        "state": "RUNNING",
        "enabled": True,
        "outputs": ["file-out"],
        "schedule": {"mode": "continuous"},
        "statistics": {"events_generated": 10, "errors": 0},
        "streams": [
            {"name": "lab::0", "template": "v/p/d/e", "state": "RUNNING", "events_generated": 10},
        ],
    }
    client = _mock_api_client(
        {
            ("POST", "/api/pipelines/lab/start"): {"payload": start_payload},
            ("POST", "/api/pipelines/lab/stop"): {"payload": stop_payload},
            ("GET", "/api/pipelines/lab"): {"payload": detail_payload},
            ("GET", "/api/pipelines"): {"payload": {"pipelines": [detail_payload]}},
        }
    )
    with patch("meltr.cli.pipelines.get_api_client", return_value=client):
        runner = CliRunner()
        assert runner.invoke(pipelines_app, ["start", "lab"]).exit_code == 0
        assert runner.invoke(pipelines_app, ["stop", "lab"]).exit_code == 0
        assert runner.invoke(pipelines_app, ["status", "lab"]).exit_code == 0
        assert runner.invoke(pipelines_app, ["status"]).exit_code == 0


def test_cli_generators_list_verbose(tmp_path, monkeypatch):
    from meltr.cli.generators import app as generators_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    payload = {
        "generators": [
            {
                "name": "gen-a",
                "state": "RUNNING",
                "template": "v/p/d/e",
                "enabled": True,
                "vendor": "v",
                "product": "p",
                "data_source": "d",
            }
        ]
    }
    with patch(
        "meltr.cli.generators.get_api_client",
        return_value=_mock_api_client({("GET", "/api/generators"): {"payload": payload}}),
    ):
        result = CliRunner().invoke(generators_app, ["list", "--verbose"])
    assert result.exit_code == 0
    assert "gen-a" in result.output
    assert "v" in result.output


def test_cli_config_validate_success(tmp_path, monkeypatch):
    from meltr.cli.config import app as config_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")
    result = CliRunner().invoke(config_app, ["validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_cli_config_show_json(tmp_path, monkeypatch):
    from meltr.cli.config import app as config_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")
    result = CliRunner().invoke(config_app, ["show", "--format", "json", "--path", "api.port"])
    assert result.exit_code == 0
    assert "8080" in result.output


# --- API pipelines auth ---


def test_api_pipelines_require_auth(tmp_path, monkeypatch):
    from meltr.api.server import APIServer

    monkeypatch.setenv("MELTR_API_KEY", "pipe-secret")
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    cfg.api.auth = AuthConfig(enabled=False, key=None)
    server = APIServer(cfg)
    client = TestClient(server.app)

    assert client.get("/api/pipelines").status_code == 401
    headers = {"Authorization": "Bearer pipe-secret"}
    assert client.get("/api/pipelines", headers=headers).status_code == 503  # no engine


def test_api_pipelines_not_found(tmp_path, monkeypatch):
    from meltr.api.server import APIServer
    from meltr.core.engine import Engine
    from meltr.entities.registry import EntityRegistry

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    registry = EntityRegistry(cfg)
    engine = Engine(cfg, registry)
    server = APIServer(cfg)
    server.app.state.engine = engine
    client = TestClient(server.app)

    try:
        assert client.get("/api/pipelines/missing").status_code == 404
    finally:
        engine.shutdown()


# --- template filters ---


def test_datetime_wrapper_arithmetic():
    base = datetime(2026, 1, 1, 12, 0, 0)
    wrapper = DateTimeWrapper(base)
    assert (wrapper + 30)._dt == base + timedelta(seconds=30)
    assert (wrapper - 10)._dt == base - timedelta(seconds=10)
    assert (wrapper * 60)._dt == base + timedelta(seconds=60)
    assert str(wrapper) == str(base)


def test_register_filters_adds_now():
    from jinja2 import Environment

    env = Environment()  # nosemgrep: python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2
    register_filters(env)
    assert "now" in env.globals
    assert "random_int" in env.filters

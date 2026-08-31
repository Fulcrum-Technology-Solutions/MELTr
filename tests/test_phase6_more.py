"""Additional Phase 6 coverage: TCP/syslog outputs, entities, package, renderer."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from meltr.community.package import get_local_collection_version
from meltr.core.config import GeneratorConfig, OutputDefinition, create_default_config, load_config
from meltr.entities.validator import _validate_entities_structure, validate_entities
from meltr.outputs.syslog import SyslogOutputHandler
from meltr.outputs.tcp import TCPOutputHandler
from meltr.templates.renderer import TemplateRenderer

SAMPLE_ENTITIES = Path(__file__).parent.parent / "src" / "meltr" / "data" / "entities.sample.yaml"
FIXTURES = Path(__file__).parent / "fixtures" / "templates"


def test_tcp_handler_write_mocked_socket():
    handler = TCPOutputHandler(name="tcp", host="127.0.0.1", port=9000)
    mock_sock = MagicMock()
    handler._socket = mock_sock
    handler.write("event line\n")
    mock_sock.sendall.assert_called_once()
    handler.close()


def test_tcp_handler_from_config():
    definition = OutputDefinition(name="t", type="tcp", host="host", port=9001)
    handler = TCPOutputHandler.from_config(definition)
    assert handler.port == 9001


def test_syslog_handler_write_udp_mocked():
    handler = SyslogOutputHandler(name="s", host="127.0.0.1", protocol="udp")
    mock_sock = MagicMock()
    handler._socket = mock_sock
    handler.write("syslog event")
    mock_sock.sendto.assert_called_once()
    handler.close()


def test_get_local_collection_version(tmp_path):
    product = tmp_path / "default" / "v" / "p"
    product.mkdir(parents=True)
    (product / "collection.json").write_text(json.dumps({"version": "1.2.3"}), encoding="utf-8")
    assert get_local_collection_version("v", "p", tmp_path) == "1.2.3"
    assert get_local_collection_version("missing", "p", tmp_path) is None


def test_validate_entities_structure_minimal():
    minimal = {
        "organization": {"name": "Acme", "domain": "acme.test"},
        "users": [],
        "devices": [],
        "services": [],
    }
    _validate_entities_structure(minimal)


def test_validate_entities_rejects_bad_email(tmp_path):
    with SAMPLE_ENTITIES.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["users"][0]["email"] = "not-an-email"
    with pytest.raises(ValueError):
        validate_entities(data)


def test_template_renderer_renders_json(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    import shutil

    from meltr.core.config import save_config

    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")

    from meltr.entities.registry import EntityRegistry

    registry = EntityRegistry(cfg)
    renderer = TemplateRenderer(registry)
    j2_path = FIXTURES / "testvendor" / "testproduct" / "events" / "preview.j2"
    output = renderer.render_template(str(j2_path))
    parsed = json.loads(output.strip())
    assert parsed["message"] == "preview test"
    registry.close()


def test_config_load_merges_generators(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    cfg.generators = [
        GeneratorConfig(
            name="g1",
            template="v/p/d/e",
            enabled=False,
            outputs=["console"],
        )
    ]
    path = tmp_path / "config.yaml"
    from meltr.core.config import save_config

    save_config(cfg, path)
    loaded = load_config(path, create_if_missing=False)
    g1 = next(g for g in loaded.generators if g.name == "g1")
    assert g1.name == "g1"


def test_http_handler_auth_error_tracking(monkeypatch):
    from meltr.outputs.http import HTTPOutputHandler

    handler = HTTPOutputHandler(name="h", url="https://example.invalid/x")
    handler.initialize()

    class FakeResponse:
        status_code = 401
        content = b"unauthorized"
        reason = "Unauthorized"

        @property
        def text(self):
            return "unauthorized"

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

    monkeypatch.setattr(
        "meltr.outputs.http.requests.request",
        lambda **kwargs: FakeResponse(),
    )
    import requests

    with pytest.raises(requests.HTTPError):
        handler._send_single_event('{"a":1}')
    stats = handler.get_statistics()
    assert stats["auth_errors"] >= 1


def test_cli_config_show_missing_path(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from meltr.cli.config import app as config_app
    from meltr.core.config import save_config

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    save_config(create_default_config(tmp_path), tmp_path / "config.yaml")
    result = CliRunner().invoke(config_app, ["show", "--path", "no.such.path"])
    assert result.exit_code == 1


def test_cli_generators_list_error_path(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from meltr.cli.generators import app as generators_app

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    class Client:
        def require_service_running(self):
            return None

        def get(self, path):
            raise RuntimeError("boom")

    with patch("meltr.cli.generators.get_api_client", return_value=Client()):
        result = CliRunner().invoke(generators_app, ["list"])
    assert result.exit_code == 1

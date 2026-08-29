"""Final Phase 6 coverage push: registry, CLI main, entities storage, config CLI."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from meltr.cli.main import app
from meltr.core.config import create_default_config, load_config, save_config
from meltr.entities.registry import EntityRegistry
from meltr.entities.storage import EntityStorage

SAMPLE_ENTITIES = Path(__file__).parent.parent / "src" / "meltr" / "data" / "entities.sample.yaml"


def test_entity_registry_random_helpers(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")
    cfg = create_default_config(tmp_path)
    save_config(cfg, tmp_path / "config.yaml")
    registry = EntityRegistry(cfg)
    user = registry.get_random_user()
    assert user is not None
    assert registry.get_organization()["name"]
    assert registry.get_all_users()
    assert registry.get_all_devices()
    assert registry.get_all_services()
    registry.close()


def test_entity_storage_backup_on_save(tmp_path):
    entities_path = tmp_path / "entities.yaml"
    shutil.copy(SAMPLE_ENTITIES, entities_path)
    storage = EntityStorage(
        entities_path=entities_path,
        auto_save=False,
        backup_enabled=True,
        backup_count=2,
    )
    data = storage.load(strict=False)
    storage.save(data)
    assert entities_path.with_suffix(".yaml.1").exists()


def test_cli_main_version():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "MELTr" in result.stdout


def test_cli_main_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"], env={"COLUMNS": "200", "TERM": "dumb"})
    assert result.exit_code == 0
    assert "pipelines" in result.stdout


def test_config_quick_add_generator(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    cfg = create_default_config(tmp_path)
    from meltr.core.config import OutputDefinition

    cfg.outputs.definitions = [
        OutputDefinition(name="console", type="console", format="json"),
    ]
    save_config(cfg, tmp_path / "config.yaml")
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "config",
            "edit",
            "--add-generator",
            "testvendor/testproduct/events/preview",
            "--name",
            "preview-gen",
            "--outputs",
            "console",
        ],
    )
    assert result.exit_code == 0
    loaded = load_config(tmp_path / "config.yaml", create_if_missing=False)
    names = [g.name for g in loaded.generators]
    assert "preview-gen" in names


def test_template_renderer_render_string(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")
    cfg = create_default_config(tmp_path)
    registry = EntityRegistry(cfg)
    from meltr.templates.renderer import TemplateRenderer

    renderer = TemplateRenderer(registry)
    out = renderer.render_string('{{ {"ok": true} | tojson }}')
    assert '"ok": true' in out
    registry.close()


def test_community_updates_format_version_status():
    from meltr.community.version import format_version_status

    assert "unknown" in format_version_status("1.0.0", None)


def test_public_errors_message():
    from meltr.utils.public_errors import public_failure_message, sanitize_stored_error

    assert "failed" in public_failure_message("Start generator")
    assert sanitize_stored_error("internal boom") == "An error occurred"
    assert sanitize_stored_error(None) is None


def test_create_http_output_cribl_preset_fields(monkeypatch):
    from meltr.cli import config_editor

    prompt_answers = iter(
        [
            "https://cribl.example/cribl/_bulk",
            "POST",
            "Bearer",
            "cribl-token",
        ]
    )
    int_answers = iter([100, 5, 30])
    confirm_answers = iter([True, True])

    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_answers))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirm_answers))

    output = config_editor._create_http_output("http-cribl")
    assert output.include_metadata is True
    assert output.headers["Authorization"] == "Bearer cribl-token"


def test_api_health_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from meltr.api.server import APIServer

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    server = APIServer(cfg)
    client = TestClient(server.app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_api_status_reports_package_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from meltr import __version__
    from meltr.api.server import APIServer

    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    monkeypatch.delenv("MELTR_API_KEY", raising=False)
    cfg = create_default_config(tmp_path)
    server = APIServer(cfg)
    client = TestClient(server.app)
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["version"] == __version__

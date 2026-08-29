"""CLI templates commands for local coverage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from meltr.cli.main import app
from meltr.core.config import create_default_config, save_config

FIXTURES = Path(__file__).parent / "fixtures" / "templates"
META = """vendor: testvendor
product: testproduct
data_source: events
description: list test
format: JSON
is_generator: true
"""


def _install_local_template(home: Path) -> str:
    tid = "testvendor/testproduct/events/preview"
    dest = home / "templates" / "default" / "testvendor" / "testproduct" / "events"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / "testvendor" / "testproduct" / "events" / "preview.j2", dest / "preview.j2")
    shutil.copy(FIXTURES / "testvendor" / "testproduct" / "events" / "preview.meta.yaml", dest / "preview.meta.yaml")
    (home / "templates" / "default" / "testvendor" / "testproduct" / "collection.json").write_text(
        json.dumps({"version": "1.0.0", "templates": ["events/preview"]}),
        encoding="utf-8",
    )
    return tid


def test_templates_list_local(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    save_config(create_default_config(tmp_path), tmp_path / "config.yaml")
    _install_local_template(tmp_path)

    result = CliRunner().invoke(app, ["templates", "list", "--local"])
    assert result.exit_code == 0
    assert "testvendor" in result.stdout


def test_templates_validate_fixture(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    j2 = FIXTURES / "testvendor" / "testproduct" / "events" / "preview.j2"
    result = CliRunner().invoke(app, ["templates", "validate", "--path", str(j2)])
    assert result.exit_code == 0
    assert "valid" in result.stdout.lower() or "✓" in result.stdout


def test_templates_validate_missing_path_exits_nonzero():
    result = CliRunner().invoke(app, ["templates", "validate"])
    assert result.exit_code == 1


def test_templates_info_local(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    save_config(create_default_config(tmp_path), tmp_path / "config.yaml")
    tid = _install_local_template(tmp_path)
    result = CliRunner().invoke(app, ["templates", "info", tid])
    assert result.exit_code == 0
    assert "testvendor" in result.stdout

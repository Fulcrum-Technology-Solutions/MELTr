"""Regression tests for templates CLI menu behavior."""

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from meltr.cli import templates
from meltr.cli.main import app


_META = """vendor: acme
product: prod
data_source: ds
description: test
format: JSON
is_generator: true
"""


def _write_default_template(home: Path, template_id: str, body: str) -> None:
    _vendor, _prod, _ds, name = template_id.split("/")
    ddir = home / "templates" / "default" / "acme" / "prod" / "ds"
    ddir.mkdir(parents=True, exist_ok=True)
    (ddir / f"{name}.j2").write_text(body, encoding="utf-8")
    (ddir / f"{name}.meta.yaml").write_text(_META, encoding="utf-8")


def test_templates_diff_errors_without_custom(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.config import create_default_config, save_config

    save_config(create_default_config(tmp_path))
    tid = "acme/prod/ds/t1"
    _write_default_template(tmp_path, tid, "default-line\n")

    runner = CliRunner()
    res = runner.invoke(app, ["templates", "diff", tid])
    assert res.exit_code == 1
    assert "custom" in res.stdout.lower()


def test_templates_diff_merge_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.config import create_default_config, save_config

    save_config(create_default_config(tmp_path))
    tid = "acme/prod/ds/t1"
    _write_default_template(tmp_path, tid, "from-default\n")

    cdir = tmp_path / "templates" / "custom" / "acme" / "prod" / "ds"
    cdir.mkdir(parents=True)
    shutil.copy2(tmp_path / "templates" / "default" / "acme" / "prod" / "ds" / "t1.j2", cdir / "t1.j2")
    shutil.copy2(
        tmp_path / "templates" / "default" / "acme" / "prod" / "ds" / "t1.meta.yaml",
        cdir / "t1.meta.yaml",
    )
    (cdir / "t1.j2").write_text("from-custom\n", encoding="utf-8")

    runner = CliRunner()
    res_diff = runner.invoke(app, ["templates", "diff", tid])
    assert res_diff.exit_code == 0
    assert "from-default" in res_diff.stdout or "from-custom" in res_diff.stdout

    res_merge = runner.invoke(app, ["templates", "merge", tid, "--yes"])
    assert res_merge.exit_code == 0
    assert (cdir / "t1.j2").read_text(encoding="utf-8") == "from-default\n"


def test_templates_merge_errors_without_custom_and_no_force(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.config import create_default_config, save_config

    save_config(create_default_config(tmp_path))
    tid = "acme/prod/ds/t1"
    _write_default_template(tmp_path, tid, "x\n")

    runner = CliRunner()
    res = runner.invoke(app, ["templates", "merge", tid])
    assert res.exit_code == 1


def test_templates_merge_force_creates_custom(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.config import create_default_config, save_config

    save_config(create_default_config(tmp_path))
    tid = "acme/prod/ds/t1"
    _write_default_template(tmp_path, tid, "new-default\n")

    runner = CliRunner()
    res = runner.invoke(app, ["templates", "merge", tid, "--force", "--yes"])
    assert res.exit_code == 0
    c_j2 = tmp_path / "templates" / "custom" / "acme" / "prod" / "ds" / "t1.j2"
    assert c_j2.read_text(encoding="utf-8") == "new-default\n"


def test_templates_create_writes_custom_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    from meltr.core.config import create_default_config, save_config

    save_config(create_default_config(tmp_path))
    tid = "acme/prod/ds/newtpl"
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["templates", "create", tid, "--description", "hello", "--format", "JSON"],
    )
    assert res.exit_code == 0
    j2 = tmp_path / "templates" / "custom" / "acme" / "prod" / "ds" / "newtpl.j2"
    meta = tmp_path / "templates" / "custom" / "acme" / "prod" / "ds" / "newtpl.meta.yaml"
    assert j2.is_file() and meta.is_file()
    assert "hello" in meta.read_text()


def test_count_data_source_templates_supports_both_keys() -> None:
    """Template counts should support both templates and event_types payload shapes."""
    data_sources = [
        {"templates": [{"id": "a"}, {"id": "b"}]},
        {"event_types": [{"id": "c"}]},
    ]
    assert templates._count_data_source_templates(data_sources) == 3


def test_paginate_templates_supports_back_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination should allow explicit back navigation."""
    monkeypatch.setattr(templates.Prompt, "ask", lambda *args, **kwargs: "b")
    result = templates._paginate_templates([("item-1", "value-1")], title="X")
    assert result == -1

"""CLI quick-edit generator guardrails."""

import pytest
import typer

from meltr.cli.config import _quick_edit_generator
from meltr.core.config import OutputDefinition, create_default_config
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME


def test_quick_edit_rejects_timezone_on_internal_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    config = create_default_config(tmp_path)
    config.outputs.definitions.append(
        OutputDefinition(name="stdout", type="console", stream="stdout", format="json")
    )
    for gen in config.generators:
        if gen.name == INTERNAL_LOGS_GENERATOR_NAME:
            gen.outputs = ["stdout"]
            break

    from meltr.core import config as config_module

    monkeypatch.setattr(config_module, "load_config", lambda: config)

    with pytest.raises(typer.Exit) as exc_info:
        _quick_edit_generator(
            name=INTERNAL_LOGS_GENERATOR_NAME,
            enable=None,
            outputs_str=None,
            timezone="America/Chicago",
        )

    assert exc_info.value.exit_code == 1

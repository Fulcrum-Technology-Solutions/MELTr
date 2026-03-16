"""Tests for internal log generator and engine integration."""

from pathlib import Path
from typing import List

import pytest

from logforge.core.config import (
    Config,
    InternalLogsConfig,
    OutputDefinition,
    OutputsConfig,
    create_default_config,
)
from logforge.core.engine import Engine
from logforge.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME, InternalLogGenerator
from logforge.core.paths import get_logforge_home
from logforge.entities.registry import EntityRegistry
from logforge.outputs.base import OutputHandler


class MockOutputHandler(OutputHandler):
    """Minimal output handler for tests."""

    def __init__(self, name: str = "mock"):
        super().__init__(name=name)
        self._events = []

    def _do_write(self, event: str) -> None:
        self._events.append(event)

    def write_batch(self, events: List[str]) -> None:
        for e in events:
            self._events.append(e)

    def close(self) -> None:
        pass


def test_internal_log_generator_lifecycle():
    """Test InternalLogGenerator start, get_status, stop."""
    handler = MockOutputHandler("out1")
    gen = InternalLogGenerator(output_handlers=[handler])
    assert gen.name == INTERNAL_LOGS_GENERATOR_NAME
    assert gen.state.value == "STOPPED"
    gen.start()
    assert gen.state.value == "RUNNING"
    status = gen.get_status()
    assert status["name"] == INTERNAL_LOGS_GENERATOR_NAME
    assert status["state"] == "RUNNING"
    assert status["template"] == "_internal"
    assert "outputs" in status
    gen.stop()
    assert gen.state.value == "STOPPED"


def test_engine_loads_internal_log_generator_when_configured(tmp_path, monkeypatch):
    """Test that Engine adds internal-logs generator when config.internal_logs is enabled."""
    monkeypatch.setenv("LOGFORGE_HOME", str(tmp_path))
    config = create_default_config(tmp_path)
    config.internal_logs = InternalLogsConfig(enabled=True, outputs=["stdout"])
    config.outputs.definitions.append(
        OutputDefinition(name="stdout", type="console", stream="stdout", format="json")
    )
    registry = EntityRegistry(config)
    engine = Engine(config, registry)
    assert INTERNAL_LOGS_GENERATOR_NAME in engine._generators
    gen = engine._generators[INTERNAL_LOGS_GENERATOR_NAME]
    assert isinstance(gen, InternalLogGenerator)


def test_engine_does_not_load_internal_log_generator_when_disabled(tmp_path, monkeypatch):
    """Test that Engine does not add internal-logs when internal_logs.enabled is False."""
    monkeypatch.setenv("LOGFORGE_HOME", str(tmp_path))
    config = create_default_config(tmp_path)
    assert config.internal_logs.enabled is False
    registry = EntityRegistry(config)
    engine = Engine(config, registry)
    assert INTERNAL_LOGS_GENERATOR_NAME not in engine._generators

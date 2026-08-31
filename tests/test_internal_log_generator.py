"""Tests for internal log generator and engine integration."""

import logging
import time
import uuid

import pytest

from meltr.core.config import OutputDefinition, create_default_config
from meltr.core.engine import Engine
from meltr.core.internal_log_generator import INTERNAL_LOGS_GENERATOR_NAME, InternalLogGenerator
from meltr.entities.registry import EntityRegistry
from meltr.outputs.base import OutputHandler


class MockOutputHandler(OutputHandler):
    """Minimal output handler for tests."""

    def __init__(self, name: str = "mock"):
        super().__init__(name=name)
        self._events = []

    def _do_write(self, event: str) -> None:
        self._events.append(event)

    def write_batch(self, events: list[str]) -> None:
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
    """Engine loads internal-logs when reserved generators entry is enabled."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    config = create_default_config(tmp_path)
    config.outputs.definitions.append(
        OutputDefinition(name="stdout", type="console", stream="stdout", format="json")
    )
    for gen in config.generators:
        if gen.name == INTERNAL_LOGS_GENERATOR_NAME:
            gen.enabled = True
            gen.outputs = ["stdout"]
    registry = EntityRegistry(config)
    engine = Engine(config, registry)
    assert INTERNAL_LOGS_GENERATOR_NAME in engine._generators
    gen = engine._generators[INTERNAL_LOGS_GENERATOR_NAME]
    assert isinstance(gen, InternalLogGenerator)


def test_engine_does_not_load_internal_log_generator_when_disabled(tmp_path, monkeypatch):
    """Engine skips internal-logs when reserved entry is disabled."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    config = create_default_config(tmp_path)
    internal = next(g for g in config.generators if g.name == INTERNAL_LOGS_GENERATOR_NAME)
    assert internal.enabled is False
    registry = EntityRegistry(config)
    engine = Engine(config, registry)
    assert INTERNAL_LOGS_GENERATOR_NAME not in engine._generators


def test_internal_log_generator_forwards_meltr_records_to_outputs():
    """Running internal-logs generator should deliver meltr.* records to output handlers."""
    token = f"lf-internal-forward-{uuid.uuid4()}"
    handler = MockOutputHandler("out1")
    gen = InternalLogGenerator(output_handlers=[handler])
    gen.start()
    try:
        # WARNING passes default/root levels in test runners; exercises InternalLogForwardingHandler.emit
        logging.getLogger("meltr").warning(token)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            if any(token in e for e in handler._events):
                return
            time.sleep(0.05)
        pytest.fail(f"expected a forwarded event containing {token!r}, got {handler._events!r}")
    finally:
        gen.stop()

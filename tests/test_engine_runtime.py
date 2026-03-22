"""Regression tests for engine runtime behavior."""

import threading
from unittest.mock import Mock

from logforge.core.engine import Engine
from logforge.core.generator import GeneratorState


class _FutureStub:
    def __init__(self) -> None:
        self._callback = None

    def add_done_callback(self, callback) -> None:
        self._callback = callback

    def done(self) -> bool:
        return False

    def result(self):
        return None


class _GeneratorStub:
    def __init__(self) -> None:
        self.state = GeneratorState.STOPPED
        self.start = Mock(side_effect=self._mark_running)
        self._generate_loop = Mock(return_value=None)

    def _mark_running(self) -> None:
        self.state = GeneratorState.RUNNING


def test_start_generator_registers_done_callback_on_future() -> None:
    """Engine should attach a done callback for immediate crash handling."""
    engine = Engine.__new__(Engine)
    engine._generators_lock = threading.Lock()
    engine._generators = {}
    engine._generator_futures = {}
    engine._thread_pool = Mock()
    engine._calculate_thread_pool_size = Mock(return_value=1)

    generator = _GeneratorStub()
    future = _FutureStub()
    engine._thread_pool.submit.return_value = future
    engine._generators["gen-1"] = generator

    Engine.start_generator(engine, "gen-1")

    assert future._callback is not None

"""Tests for HTTP output backpressure and shutdown behavior."""

from unittest.mock import MagicMock

from meltr.core.config import OutputDefinition
from meltr.outputs.http import HTTPOutputHandler


def test_http_batch_buffer_drop_newest_when_full_counts_drops() -> None:
    handler = HTTPOutputHandler(
        name="h",
        url="https://example.invalid/x",
        streaming=False,
        buffer_size=2,
        batch_size=100,
        overflow_policy="drop_newest",
    )
    handler._batch_buffer.put_nowait('{"a":1}')
    handler._batch_buffer.put_nowait('{"b":1}')
    handler._enqueue_batch_buffer('{"c":1}')
    assert handler._batch_buffer.qsize() == 2
    assert handler.get_statistics()["batch_buffer_dropped"] >= 1


def test_http_batch_buffer_drop_oldest_evicts_oldest_when_full() -> None:
    handler = HTTPOutputHandler(
        name="h",
        url="https://example.invalid/x",
        streaming=False,
        buffer_size=2,
        batch_size=100,
        overflow_policy="drop_oldest",
    )
    handler._batch_buffer.put_nowait('{"a":1}')
    handler._batch_buffer.put_nowait('{"b":1}')
    handler._enqueue_batch_buffer('{"c":1}')
    assert handler._batch_buffer.qsize() == 2
    items = []
    while not handler._batch_buffer.empty():
        items.append(handler._batch_buffer.get_nowait())
    assert items == ['{"b":1}', '{"c":1}']


def test_http_from_config_passes_buffer_overflow_policy() -> None:
    definition = OutputDefinition(
        name="x",
        type="http",
        url="https://example.com/e",
        buffer_overflow_policy="drop_oldest",
    )
    handler = HTTPOutputHandler.from_config(definition, buffer_size=10)
    assert handler.overflow_policy == "drop_oldest"


def test_http_close_shuts_down_executor() -> None:
    handler = HTTPOutputHandler(
        name="h",
        url="https://example.invalid/x",
        streaming=True,
        buffer_size=10,
    )
    assert handler._executor is not None
    mock_exec = MagicMock()
    handler._executor = mock_exec
    handler.close()
    mock_exec.shutdown.assert_called_once()
    assert handler._executor is None

"""Tests for output handlers."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from logforge.core.config import OutputDefinition, RetryConfig
from logforge.outputs.base import OutputHandler
from logforge.outputs.console import ConsoleOutputHandler
from logforge.outputs.file import FileOutputHandler
from logforge.outputs.factory import create_output_handlers
from logforge.outputs.http import HTTPOutputHandler
from logforge.outputs.tcp import TCPOutputHandler


def test_console_handler_json_format():
    """Test console handler with JSON format."""
    handler = ConsoleOutputHandler(name="test", format="json")
    
    # Test write
    event = '{"test": "data"}'
    handler.write(event)  # Should not raise
    
    # Test write_batch
    events = ['{"event1": 1}', '{"event2": 2}']
    handler.write_batch(events)  # Should not raise


def test_console_handler_text_format():
    """Test console handler with text format."""
    handler = ConsoleOutputHandler(name="test", format="text")
    
    event = "Test event message"
    handler.write(event)  # Should not raise


def test_file_handler_creates_file(tmp_path):
    """Test file handler creates output file."""
    output_file = tmp_path / 'output.log'
    handler = FileOutputHandler(
        name="test",
        path=str(output_file),
    )
    
    handler.initialize()
    handler.write('{"test": "event"}')
    handler.close()
    
    assert output_file.exists()
    assert 'test' in output_file.read_text()


def test_file_handler_from_config():
    """Test file handler creation from config."""
    definition = OutputDefinition(
        name="test_file",
        type="file",
        path="/tmp/test.log",
    )
    
    handler = FileOutputHandler.from_config(definition)
    assert handler.name == "test_file"
    assert handler.path_template == "/tmp/test.log"


def test_http_handler_from_config():
    """Test HTTP handler creation from config."""
    definition = OutputDefinition(
        name="test_http",
        type="http",
        url="https://example.com/events",
        method="POST",
        batch_size=50,
    )
    
    handler = HTTPOutputHandler.from_config(definition)
    assert handler.name == "test_http"
    assert handler.url == "https://example.com/events"
    assert handler.batch_size == 50


def test_tcp_handler_from_config():
    """Test TCP handler creation from config."""
    definition = OutputDefinition(
        name="test_tcp",
        type="tcp",
        host="localhost",
        port=9000,
    )
    
    handler = TCPOutputHandler.from_config(definition)
    assert handler.name == "test_tcp"
    assert handler.host == "localhost"
    assert handler.port == 9000


def test_output_handler_factory():
    """Test output handler factory."""
    definitions = [
        OutputDefinition(name="console1", type="console", format="json"),
        OutputDefinition(name="file1", type="file", path="/tmp/test.log"),
    ]
    
    handlers = create_output_handlers(
        output_names=["console1", "file1"],
        output_definitions=definitions,
    )
    
    assert len(handlers) == 2
    assert handlers[0].name == "console1"
    assert handlers[1].name == "file1"


def test_output_handler_retry_config():
    """Test output handler with retry configuration."""
    retry_config = RetryConfig(
        max_attempts=3,
        retry_interval=5,
        backoff_multiplier=2.0,
        max_backoff=60,
    )
    
    handler = ConsoleOutputHandler(name="test")
    handler.retry_config = retry_config
    
    assert handler.retry_config.max_attempts == 3
    assert handler.retry_config.retry_interval == 5


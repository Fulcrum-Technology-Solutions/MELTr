"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_home(monkeypatch) -> Generator[Path, None, None]:
    """Create a temporary MELTR_HOME directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        monkeypatch.setenv('MELTR_HOME', str(home))
        yield home


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration dictionary."""
    return {
        'api': {
            'enabled': True,
            'host': '127.0.0.1',
            'port': 8080,
        },
        'entity_registry': {
            'path': 'entities.yaml',
            'auto_save': True,
        },
        'templates': {
            'local_path': 'templates',
        },
        'outputs': {
            'definitions': [],
        },
        'generators': [],
    }










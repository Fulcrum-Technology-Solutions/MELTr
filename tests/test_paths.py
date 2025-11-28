"""Tests for path resolution."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from logforge.core.paths import (
    get_config_path,
    get_entities_path,
    get_logforge_home,
    get_templates_path,
    validate_path_within_home,
)


def test_get_logforge_home_from_env():
    """Test LOGFORGE_HOME resolution from environment variable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.dict(os.environ, {'LOGFORGE_HOME': tmpdir}, clear=False):
            home = get_logforge_home()
            assert home == Path(tmpdir).resolve()
            assert home.exists()


def test_get_logforge_home_local_directory(tmp_path, monkeypatch):
    """Test LOGFORGE_HOME resolution from local ./logforge directory."""
    # Create a logforge directory in temp path
    logforge_dir = tmp_path / 'logforge'
    logforge_dir.mkdir()
    
    # Change to temp directory
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('LOGFORGE_HOME', raising=False)
    
    home = get_logforge_home()
    assert home == logforge_dir.resolve()


def test_get_logforge_home_default(monkeypatch):
    """Test default LOGFORGE_HOME resolution."""
    # Set HOME environment variable
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv('HOME', tmpdir)
        monkeypatch.delenv('LOGFORGE_HOME', raising=False)
        
        with patch('os.getuid', return_value=1000):  # Regular user
            home = get_logforge_home()
            assert home == Path(tmpdir) / '.logforge'


def test_get_config_path():
    """Test config path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        config_path = get_config_path(home)
        assert config_path == home / 'config.yaml'


def test_get_entities_path():
    """Test entities path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        entities_path = get_entities_path(home)
        assert entities_path == home / 'entities.yaml'


def test_get_templates_path():
    """Test templates path resolution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        templates_path = get_templates_path(home)
        assert templates_path == home / 'templates'


def test_validate_path_within_home():
    """Test path validation within LOGFORGE_HOME."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        
        # Valid paths
        assert validate_path_within_home(home / 'config.yaml', home) is True
        assert validate_path_within_home(home / 'templates' / 'default', home) is True
        
        # Invalid paths
        assert validate_path_within_home(Path('/etc/passwd'), home) is False
        assert validate_path_within_home(Path('/tmp'), home) is False


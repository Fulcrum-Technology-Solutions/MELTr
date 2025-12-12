"""Tests for init command."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from logforge.cli.init import app, init


def test_init_creates_directory_structure(tmp_path, monkeypatch):
    """Test that init creates required directory structure."""
    # Set LOGFORGE_HOME to temp directory
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    runner = CliRunner()
    result = runner.invoke(app, ['--force'])
    
    assert result.exit_code == 0
    assert (tmp_path / 'config.yaml').exists()
    assert (tmp_path / 'entities.yaml').exists()
    assert (tmp_path / 'templates').exists()
    assert (tmp_path / 'templates' / 'default').exists()
    assert (tmp_path / 'templates' / 'custom').exists()


def test_init_creates_config_file(tmp_path, monkeypatch):
    """Test that init creates config.yaml."""
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    runner = CliRunner()
    result = runner.invoke(app, ['--force'])
    
    assert result.exit_code == 0
    config_path = tmp_path / 'config.yaml'
    assert config_path.exists()
    
    # Verify config is valid YAML
    with config_path.open() as f:
        config_data = yaml.safe_load(f)
        assert 'api' in config_data
        assert 'entity_registry' in config_data


def test_init_creates_entities_file(tmp_path, monkeypatch):
    """Test that init creates entities.yaml."""
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    runner = CliRunner()
    result = runner.invoke(app, ['--force'])
    
    assert result.exit_code == 0
    entities_path = tmp_path / 'entities.yaml'
    assert entities_path.exists()
    
    # Verify entities file structure
    with entities_path.open() as f:
        entities_data = yaml.safe_load(f)
        assert 'organization' in entities_data
        assert 'users' in entities_data
        assert 'devices' in entities_data
        assert 'services' in entities_data


def test_init_respects_force_flag(tmp_path, monkeypatch):
    """Test that --force overwrites existing config."""
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    # Create existing config
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('existing: config')
    
    runner = CliRunner()
    result = runner.invoke(app, ['--force'])
    
    assert result.exit_code == 0
    # Config should be overwritten
    with config_path.open() as f:
        config_data = yaml.safe_load(f)
        assert 'api' in config_data  # New config structure


def test_init_sets_file_permissions(tmp_path, monkeypatch):
    """Test that init sets secure file permissions."""
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    runner = CliRunner()
    result = runner.invoke(app, ['--force'])
    
    assert result.exit_code == 0
    
    # Check permissions (600 = rw-------)
    config_path = tmp_path / 'config.yaml'
    entities_path = tmp_path / 'entities.yaml'
    
    if os.name != 'nt':  # Skip on Windows
        config_mode = config_path.stat().st_mode & 0o777
        entities_mode = entities_path.stat().st_mode & 0o777
        assert config_mode == 0o600
        assert entities_mode == 0o600










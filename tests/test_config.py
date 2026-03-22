"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest
import yaml

from logforge.core.config import Config, create_default_config, load_config


def test_create_default_config():
    """Test default config creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        config = create_default_config(home)
        
        assert isinstance(config, Config)
        assert config.api.enabled is True
        assert config.api.port == 8080
        assert config.entity_registry.path == str(home / 'entities.yaml')


def test_load_config(tmp_path, monkeypatch):
    """Test config loading from file."""
    # Set LOGFORGE_HOME to temp directory
    monkeypatch.setenv('LOGFORGE_HOME', str(tmp_path))
    
    config_path = tmp_path / 'config.yaml'
    
    # Create default config
    config = create_default_config(tmp_path)
    config_dict = config.model_dump(mode='json', exclude_none=True)
    
    # Write to file
    with config_path.open('w') as f:
        yaml.dump(config_dict, f)
    
    # Load from file
    loaded_config = load_config(config_path)
    assert loaded_config.api.port == config.api.port
    assert loaded_config.api.enabled == config.api.enabled


def test_config_validation():
    """Test config validation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        config = create_default_config(home)
        
        # Config should be valid
        assert config.api.host is not None
        assert config.api.port > 0
        assert config.entity_registry.auto_save is True


def test_default_config_includes_internal_logs():
    """Test that default config has internal_logs section (disabled by default)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = create_default_config(Path(tmpdir))
        assert hasattr(config, "internal_logs")
        assert config.internal_logs.enabled is False
        assert config.internal_logs.outputs == []


def test_edit_output_updates_existing_output_without_recreate(tmp_path, monkeypatch):
    """In-place output edit must replace the same list slot (no delete/recreate)."""
    from logforge.cli import config_editor
    from logforge.core.config import OutputDefinition

    config = create_default_config(tmp_path)
    http_out = OutputDefinition(
        name="http1",
        type="http",
        url="https://old.example/hook",
        method="POST",
        include_metadata=False,
        buffer_overflow_policy="drop_newest",
    )
    config.outputs.definitions = [http_out]

    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: 1)

    def fake_edit_http(output: OutputDefinition) -> OutputDefinition:
        return output.model_copy(update={"url": "https://new.example/hook"})

    monkeypatch.setattr(config_editor, "_edit_http_output_definition", fake_edit_http)

    updated = config_editor._edit_output_interactive(config)
    assert len(updated.outputs.definitions) == 1
    assert updated.outputs.definitions[0].name == "http1"
    assert updated.outputs.definitions[0].url == "https://new.example/hook"


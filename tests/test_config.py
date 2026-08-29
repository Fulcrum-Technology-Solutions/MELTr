"""Tests for configuration management."""

import tempfile
from pathlib import Path
from types import SimpleNamespace

import requests
import yaml

from meltr.core.config import Config, create_default_config, load_config


def test_create_default_config():
    """Test default config creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        config = create_default_config(home)

        assert isinstance(config, Config)
        assert config.api.enabled is True
        assert config.api.port == 8080
        assert config.entity_registry.path == str(home / "entities.yaml")


def test_load_config(tmp_path, monkeypatch):
    """Test config loading from file."""
    # Set MELTR_HOME to temp directory
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))

    config_path = tmp_path / "config.yaml"

    # Create default config
    config = create_default_config(tmp_path)
    config_dict = config.model_dump(mode="json", exclude_none=True)

    # Write to file
    with config_path.open("w") as f:
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
    from meltr.cli import config_editor
    from meltr.core.config import OutputDefinition

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


def test_create_http_output_bearer_stores_plaintext_token(monkeypatch):
    """HTTP output create flow stores plaintext bearer token."""
    from meltr.cli import config_editor

    prompt_answers = iter(
        [
            "https://collector.example/v1/events",  # HTTP URL
            "POST",  # method
            "Bearer",  # auth type
            "  abc123  ",  # bearer token (trimmed)
        ]
    )
    int_answers = iter([100, 5, 30])  # batch_size, batch_interval, timeout
    confirm_answers = iter([True, False])  # add auth, include metadata

    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_answers))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirm_answers))

    output = config_editor._create_http_output("dest_http")

    assert output.headers["Authorization"] == "Bearer abc123"
    assert output.headers["Content-Type"] == "application/json"


def test_create_http_output_splunk_stores_plaintext_token(monkeypatch):
    """HTTP output create flow stores plaintext Splunk HEC token."""
    from meltr.cli import config_editor

    prompt_answers = iter(
        [
            "https://collector.example/v1/events",
            "POST",
            "Splunk HEC",
            "  hec-token  ",
        ]
    )
    int_answers = iter([100, 5, 30])
    confirm_answers = iter([True, False])

    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_answers))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirm_answers))

    output = config_editor._create_http_output("dest_http")

    assert output.headers["Authorization"] == "Splunk hec-token"
    assert output.headers["Content-Type"] == "application/json"


def test_create_http_output_api_key_stores_plaintext_token(monkeypatch):
    """HTTP output create flow stores plaintext API key token."""
    from meltr.cli import config_editor

    prompt_answers = iter(
        [
            "https://collector.example/v1/events",
            "POST",
            "API Key",
            "X-Custom-Api-Key",
            "  key-123  ",
        ]
    )
    int_answers = iter([100, 5, 30])
    confirm_answers = iter([True, False])

    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_answers))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirm_answers))

    output = config_editor._create_http_output("dest_http")

    assert output.headers["X-Custom-Api-Key"] == "key-123"
    assert output.headers["Content-Type"] == "application/json"


def test_edit_http_output_rebuild_auth_stores_plaintext_token(monkeypatch):
    """HTTP output edit rebuild path stores plaintext bearer token."""
    from meltr.cli import config_editor
    from meltr.core.config import OutputDefinition

    existing = OutputDefinition(
        name="http1",
        type="http",
        url="https://old.example/v1/events",
        method="POST",
        headers={"Authorization": "Bearer ${OLD}", "Content-Type": "application/json"},
        include_metadata=False,
        buffer_overflow_policy="drop_newest",
    )

    prompt_answers = iter(
        [
            "https://new.example/v1/events",  # URL
            "POST",  # method
            "drop_newest",  # policy
            "Bearer",  # auth type
            "  new-token  ",  # token
        ]
    )
    int_answers = iter([100, 5, 30])
    confirm_answers = iter(
        [
            True,  # streaming mode
            False,  # include metadata
            True,  # rebuild auth headers
            True,  # add authentication header
        ]
    )

    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_answers))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirm_answers))

    output = config_editor._edit_http_output_definition(existing)
    assert output.headers["Authorization"] == "Bearer new-token"
    assert output.headers["Content-Type"] == "application/json"


def test_plaintext_token_prompt_rejects_empty_and_dollar_brace(monkeypatch):
    """Token prompt rejects empty and ${...} values, then returns valid token."""
    from meltr.cli import config_editor

    prompt_answers = iter(["   ", "${BAD}", "  valid-token  "])
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompt_answers))

    token = config_editor._prompt_plaintext_token("Bearer token")
    assert token == "valid-token"


def test_save_config_service_down_local_connection_refused_is_info(monkeypatch, tmp_path):
    """Local connection-refused should be treated as info-only (save still succeeds)."""
    from meltr.cli import config_editor

    cfg = create_default_config(tmp_path)
    rendered = []

    monkeypatch.setattr(config_editor, "_preview_config", lambda *_a, **_k: None)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(config_editor, "save_config_file", lambda _cfg: None)
    monkeypatch.setattr(
        config_editor.console, "print", lambda msg="", *a, **k: rendered.append(str(msg))
    )

    class _Client:
        api_url = "http://127.0.0.1:8080"

        def get(self, *_a, **_k):
            raise requests.exceptions.ConnectionError(
                "Failed to establish a new connection: [Errno 111] Connection refused"
            )

        def post(self, *_a, **_k):
            raise AssertionError("reload should not be attempted when service is down")

    fake_api_module = SimpleNamespace(get_api_client=lambda: _Client())
    monkeypatch.setitem(__import__("sys").modules, "meltr.cli.api_client", fake_api_module)

    assert config_editor._save_config(cfg) is True
    out = "\n".join(rendered)
    assert "Service is not running; skipping live reload" in out
    assert "loaded automatically on next start" in out
    assert "Could not connect to service" not in out


def test_save_config_service_up_calls_reload(monkeypatch, tmp_path):
    """When service is healthy, config reload endpoint is called."""
    from meltr.cli import config_editor

    cfg = create_default_config(tmp_path)
    calls = {"post": 0}

    monkeypatch.setattr(config_editor, "_preview_config", lambda *_a, **_k: None)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(config_editor, "save_config_file", lambda _cfg: None)

    class _Response:
        def __init__(self, status_code=200, data=None):
            self.status_code = status_code
            self._data = data or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class _Client:
        api_url = "http://127.0.0.1:8080"

        def get(self, *_a, **_k):
            return _Response(status_code=200)

        def post(self, *_a, **_k):
            calls["post"] += 1
            return _Response(
                status_code=200,
                data={"results": {"added": [], "removed": [], "updated": [], "errors": []}},
            )

    fake_api_module = SimpleNamespace(get_api_client=lambda: _Client())
    monkeypatch.setitem(__import__("sys").modules, "meltr.cli.api_client", fake_api_module)

    assert config_editor._save_config(cfg) is True
    assert calls["post"] == 1


def test_save_config_timeout_keeps_warning_guidance(monkeypatch, tmp_path):
    """Timeout should continue to show warning-style manual reload guidance."""
    from meltr.cli import config_editor

    cfg = create_default_config(tmp_path)
    rendered = []

    monkeypatch.setattr(config_editor, "_preview_config", lambda *_a, **_k: None)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(config_editor, "save_config_file", lambda _cfg: None)
    monkeypatch.setattr(
        config_editor.console, "print", lambda msg="", *a, **k: rendered.append(str(msg))
    )

    class _Client:
        api_url = "http://127.0.0.1:8080"

        def get(self, *_a, **_k):
            raise requests.exceptions.Timeout("timed out")

    fake_api_module = SimpleNamespace(get_api_client=lambda: _Client())
    monkeypatch.setitem(__import__("sys").modules, "meltr.cli.api_client", fake_api_module)

    assert config_editor._save_config(cfg) is True
    out = "\n".join(rendered)
    assert "timed out" in out.lower()
    assert "Use 'logforge config reload'" in out


def test_save_config_unexpected_apply_error_keeps_warning(monkeypatch, tmp_path):
    """Unexpected apply exceptions should remain warning-style."""
    from meltr.cli import config_editor

    cfg = create_default_config(tmp_path)
    rendered = []

    monkeypatch.setattr(config_editor, "_preview_config", lambda *_a, **_k: None)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(config_editor, "save_config_file", lambda _cfg: None)
    monkeypatch.setattr(
        config_editor.console, "print", lambda msg="", *a, **k: rendered.append(str(msg))
    )

    class _Client:
        api_url = "http://127.0.0.1:8080"

        def get(self, *_a, **_k):
            raise RuntimeError("boom")

    fake_api_module = SimpleNamespace(get_api_client=lambda: _Client())
    monkeypatch.setitem(__import__("sys").modules, "meltr.cli.api_client", fake_api_module)

    assert config_editor._save_config(cfg) is True
    out = "\n".join(rendered)
    assert "Could not apply changes automatically" in out
    assert "Use 'logforge config reload'" in out


def test_save_config_non_local_connection_error_stays_warning(monkeypatch, tmp_path):
    """Non-local connection failures should keep warning path, not info-only skip."""
    from meltr.cli import config_editor

    cfg = create_default_config(tmp_path)
    rendered = []

    monkeypatch.setattr(config_editor, "_preview_config", lambda *_a, **_k: None)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(config_editor, "save_config_file", lambda _cfg: None)
    monkeypatch.setattr(
        config_editor.console, "print", lambda msg="", *a, **k: rendered.append(str(msg))
    )

    class _Client:
        api_url = "https://api.example.com"

        def get(self, *_a, **_k):
            raise requests.exceptions.ConnectionError("temporary DNS failure")

    fake_api_module = SimpleNamespace(get_api_client=lambda: _Client())
    monkeypatch.setitem(__import__("sys").modules, "meltr.cli.api_client", fake_api_module)

    assert config_editor._save_config(cfg) is True
    out = "\n".join(rendered)
    assert "Could not connect to service at https://api.example.com" in out

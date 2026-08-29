"""Config editor output creation helpers (mocked prompts)."""

from __future__ import annotations

from meltr.cli import config_editor


def test_create_file_output_with_rotation(monkeypatch):
    prompts = iter(["/tmp/{generator}.log", "size", "50MB"])
    confirms = iter([True, True])
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "size")))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: 5)
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: next(confirms))

    output = config_editor._create_file_output("file-out")
    assert output.type == "file"
    assert output.rotation is not None
    assert output.rotation.max_files == 5


def test_create_console_output_json(monkeypatch):
    prompts = iter(["stdout", "json"])
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompts))

    output = config_editor._create_console_output("console-out")
    assert output.stream == "stdout"
    assert output.format == "json"


def test_create_tcp_output(monkeypatch):
    prompts = iter(["collector.local"])
    int_prompts = iter([9000])
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "\\n")))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_prompts, k.get("default", 514)))
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: True)

    output = config_editor._create_tcp_output("tcp-out")
    assert output.host == "collector.local"
    assert output.port == 9000


def test_create_syslog_output(monkeypatch):
    prompts = iter(["syslog.local", "tcp", "local1", "warning"])
    int_prompts = iter([5514])
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: next(prompts, k.get("default", "udp")))
    monkeypatch.setattr(config_editor.IntPrompt, "ask", lambda *a, **k: next(int_prompts, k.get("default", 514)))

    output = config_editor._create_syslog_output("syslog-out")
    assert output.host == "syslog.local"
    assert output.port == 5514
    assert output.protocol == "tcp"


def test_create_file_output_no_rotation(monkeypatch):
    monkeypatch.setattr(config_editor.Prompt, "ask", lambda *a, **k: "/tmp/out.log")
    monkeypatch.setattr(config_editor.Confirm, "ask", lambda *a, **k: False)

    output = config_editor._create_file_output("plain-file")
    assert output.rotation is None


def test_is_expected_local_service_down_connection_refused():
    import requests

    err = requests.exceptions.ConnectionError("Connection refused")
    assert config_editor._is_expected_local_service_down("http://127.0.0.1:8080", err) is True
    assert config_editor._is_expected_local_service_down("https://remote.example", err) is False

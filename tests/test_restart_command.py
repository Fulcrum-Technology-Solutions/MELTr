"""Tests for Splunk-style `logforge restart` systemd vs local fallback."""

import typer
from rich.console import Console

from logforge.cli import restart as r


def test_restart_uses_systemd_when_unit_exists_and_restart_ok(monkeypatch):
    monkeypatch.setattr(r, "systemd_unit_exists", lambda *_a, **_k: True)
    monkeypatch.setattr(r, "systemd_restart", lambda *_a, **_k: True)

    calls = {"stop": 0, "start": 0}

    def api_stop(**_k):
        calls["stop"] += 1

    def api_start(**_k):
        calls["start"] += 1

    r.restart(timeout=30, foreground=False, console=Console(), api_stop=api_stop, api_start=api_start)
    assert calls == {"stop": 0, "start": 0}


def test_restart_falls_back_when_unit_missing(monkeypatch):
    monkeypatch.setattr(r, "systemd_unit_exists", lambda *_a, **_k: False)
    monkeypatch.setattr(r, "systemd_restart", lambda *_a, **_k: False)

    calls = {"stop": None, "start": None}

    def api_stop(**k):
        calls["stop"] = k
        raise typer.Exit(code=0)

    def api_start(**k):
        calls["start"] = k

    r.restart(timeout=12, foreground=True, console=Console(), api_stop=api_stop, api_start=api_start)
    assert calls["stop"] == {"timeout": 12}
    assert calls["start"] == {"foreground": True}


def test_restart_falls_back_when_systemd_restart_fails(monkeypatch):
    monkeypatch.setattr(r, "systemd_unit_exists", lambda *_a, **_k: True)
    monkeypatch.setattr(r, "systemd_restart", lambda *_a, **_k: False)

    calls = {"stop": None, "start": None}

    def api_stop(**k):
        calls["stop"] = k
        raise typer.Exit(code=0)

    def api_start(**k):
        calls["start"] = k

    r.restart(timeout=9, foreground=False, console=Console(), api_stop=api_stop, api_start=api_start)
    assert calls["stop"] == {"timeout": 9}
    assert calls["start"] == {"foreground": False}


def test_restart_propagates_nonzero_stop_exit(monkeypatch):
    monkeypatch.setattr(r, "systemd_unit_exists", lambda *_a, **_k: False)
    monkeypatch.setattr(r, "systemd_restart", lambda *_a, **_k: False)

    def api_stop(**_k):
        raise typer.Exit(code=2)

    def api_start(**_k):
        raise AssertionError("api_start must not be called if stop failed")

    try:
        r.restart(timeout=30, foreground=False, console=Console(), api_stop=api_stop, api_start=api_start)
        raise AssertionError("expected typer.Exit to propagate")
    except typer.Exit as e:
        assert getattr(e, "exit_code", getattr(e, "code", None)) == 2


"""Dashboard rendering safety tests (markup + per-tick fallback)."""

from typing import Any

from meltr.cli import dashboard as dash


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def get(self, _path: str):
        return _FakeResponse(self._payload)


def test_render_status_snapshot_escapes_markup_like_strings():
    # This used to be a Rich MarkupError failure mode if any dynamic string was unescaped.
    payload = {
        "system": {"cpu_percent": 1.0, "memory_mb": 10, "threads": 1},
        "uptime": 1,
        "generators": [
            {
                "name": "bad[/bold]name",
                "state": "RUNNING",
                "events_generated": 1,
                "errors": 0,
                "uptime": 1,
            }
        ],
    }
    layout = dash.render_status_snapshot(payload, refresh_count=1)
    assert layout is not None


def test_safe_render_tick_returns_error_layout_when_render_raises(monkeypatch):
    payload = {
        "system": {"cpu_percent": 1.0, "memory_mb": 10, "threads": 1},
        "uptime": 1,
        "generators": [],
    }
    client = _FakeClient(payload)

    calls = {"n": 0}

    def boom(_snapshot, _refresh_count=0):
        calls["n"] += 1
        raise RuntimeError("boom[/bold]")

    monkeypatch.setattr(dash, "render_status_snapshot", boom)

    # First tick: render blows up -> should return a safe error layout
    layout1 = dash.safe_render_tick(client, refresh_count=1)
    assert layout1 is not None
    assert calls["n"] == 1

    # Second tick: still safe (never raises) and keeps calling render
    layout2 = dash.safe_render_tick(client, refresh_count=2)
    assert layout2 is not None
    assert calls["n"] == 2

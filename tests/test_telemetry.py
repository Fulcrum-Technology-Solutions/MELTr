from __future__ import annotations

from pathlib import Path

from meltr.telemetry.client import TelemetryClient, TelemetryEvent, get_actor_id


def test_get_actor_id_is_stable(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    a1 = get_actor_id()
    a2 = get_actor_id()
    assert a1 == a2


def test_telemetry_client_posts_events(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setenv("MELTR_TELEMETRY", "1")

    client = TelemetryClient(base_api_url="https://meltr.ftsc.cloud/api/v1")
    actor_id = "actor-xyz"
    client.post_events(
        actor_id=actor_id,
        events=[
            TelemetryEvent(
                event_type="template_installed",
                vendor_id="acme",
                product_id="widget",
                data_source_id="audit",
                template_id="acme/widget/audit/login",
                collection_version="1.2.3",
                properties={"method": "test"},
            )
        ],
    )

    assert len(calls) == 1
    assert calls[0]["url"].endswith("/telemetry/events")
    assert calls[0]["headers"]["X-MELTr-Client"] == "cli"
    assert calls[0]["headers"]["X-MELTr-Actor-Id"] == actor_id
    assert calls[0]["json"]["actor_id"] == actor_id
    assert calls[0]["json"]["events"][0]["event_type"] == "template_installed"


def test_telemetry_client_respects_opt_out(monkeypatch):
    calls = []

    class FakeResp:
        status_code = 200
        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(1)
        return FakeResp()

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setenv("MELTR_TELEMETRY", "0")

    client = TelemetryClient(base_api_url="https://meltr.ftsc.cloud/api/v1")
    client.post_events(actor_id="actor", events=[TelemetryEvent(event_type="template_installed")])

    assert calls == []

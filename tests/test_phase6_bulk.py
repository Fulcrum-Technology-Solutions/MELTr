"""Bulk coverage tests: filters, file output, updates, schedule, template validator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from meltr.community.updates import (
    ProductVersionLookup,
    find_stale_updates,
    get_remote_collection_version,
    iter_installed_products,
)
from meltr.core.config import OutputDefinition
from meltr.core.schedule import ScheduleSharedState
from meltr.outputs.file import FileOutputHandler
from meltr.templates.filters import (
    DateTimeWrapper,
    iso8601_utc,
    random_guid,
    random_hex,
    random_hostname,
    random_port,
    random_private_ip,
    random_public_ip,
    random_string,
    random_weighted,
    rfc3339,
    timestamp_to_iso,
)
from meltr.templates.validator import validate_template

FIXTURES = Path(__file__).parent / "fixtures" / "templates"
PREVIEW_J2 = FIXTURES / "testvendor" / "testproduct" / "events" / "preview.j2"
PREVIEW_META = FIXTURES / "testvendor" / "testproduct" / "events" / "preview.meta.yaml"


# --- filters bulk ---


def test_all_random_filters_smoke():
    assert 1 <= random_port() <= 65535
    assert 1024 <= random_port(1024, 1024) <= 1024
    assert len(random_string(8)) == 8
    assert random_weighted(["a", "b"], [1.0, 0.0]) == "a"
    assert len(random_guid()) == 36
    assert len(random_hex(1, 255)) >= 1
    assert "." in random_public_ip()
    assert random_private_ip().startswith(("10.", "172.", "192.168."))
    assert random_hostname()


def test_datetime_filter_aliases():
    dt = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    wrapped = DateTimeWrapper(dt)
    assert timestamp_to_iso(wrapped).endswith("+00:00") or "T" in timestamp_to_iso(wrapped)
    assert "2026" in iso8601_utc(wrapped)
    assert "2026" in rfc3339(wrapped)


# --- file output ---


def test_file_handler_write_batch_and_rotate(tmp_path):
    out = tmp_path / "nested" / "events.log"
    handler = FileOutputHandler(name="f", path=str(out))
    handler.initialize()
    handler.write('{"a":1}\n')
    handler.write_batch(['{"b":2}\n', '{"c":3}\n'])
    handler.close()
    text = out.read_text()
    assert "a" in text and "b" in text


def test_file_handler_from_config_path_template():
    definition = OutputDefinition(
        name="rot",
        type="file",
        path="/tmp/{generator}.log",
    )
    handler = FileOutputHandler.from_config(definition)
    assert handler.path_template == "/tmp/{generator}.log"


# --- community updates ---


def _write_product(base: Path, version: str = "1.0.0") -> None:
    product = base / "default" / "vendor_a" / "product_b"
    product.mkdir(parents=True)
    (product / "collection.json").write_text(json.dumps({"version": version}), encoding="utf-8")


def test_iter_installed_products(tmp_path):
    _write_product(tmp_path / "templates")
    products = list(iter_installed_products(tmp_path / "templates"))
    assert products == [("vendor_a", "product_b")]


def test_find_stale_updates(tmp_path):
    _write_product(tmp_path / "templates", "1.0.0")
    client = MagicMock()
    client.get_product_detail.return_value = {"collection_version": "2.0.0"}
    stale = find_stale_updates(client, tmp_path / "templates")
    assert len(stale) == 1
    assert stale[0]["remote_version"] == "2.0.0"


def test_product_version_lookup(tmp_path):
    _write_product(tmp_path / "templates", "1.0.0")
    client = MagicMock()
    client.get_product_detail.return_value = {"collection_version": "1.0.0"}
    lookup = ProductVersionLookup(tmp_path / "templates", client)
    local, remote = lookup.for_product("vendor_a", "product_b")
    assert local == "1.0.0"
    assert remote == "1.0.0"


def test_get_remote_collection_version_uses_cache():
    client = MagicMock()
    client.get_product_detail.return_value = {"collection_version": "3.0.0"}
    cache: dict = {}
    assert get_remote_collection_version(client, "v", "p", cache=cache) == "3.0.0"
    assert get_remote_collection_version(client, "v", "p", cache=cache) == "3.0.0"
    client.get_product_detail.assert_called_once()


# --- schedule shared state ---


def test_schedule_shared_state_thread_safe():
    started = datetime.now(timezone.utc)
    state = ScheduleSharedState(started)
    assert state.events_emitted == 0
    state.increment()
    state.increment()
    assert state.events_emitted == 2
    state.reset()
    assert state.events_emitted == 0


# --- template validator ---


def test_validate_template_fixture():
    result = validate_template(PREVIEW_J2, PREVIEW_META)
    assert result.is_valid is True


# --- http batch send mocked ---


def test_http_send_batch_posts_json_array(monkeypatch):
    from meltr.outputs.http import HTTPOutputHandler

    handler = HTTPOutputHandler(
        name="batch",
        url="https://example.invalid/bulk",
        streaming=False,
        batch_size=2,
    )
    handler.initialize()
    captured = {}

    class FakeResponse:
        status_code = 200
        content = b"ok"

        def raise_for_status(self):
            return None

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("meltr.outputs.http.requests.request", fake_request)
    handler._send_batch(['{"a":1}', '{"b":2}'])
    assert captured["json"] == [{"a": 1}, {"b": 2}]


def test_http_write_streaming_submits_to_executor(monkeypatch):
    from meltr.outputs.http import HTTPOutputHandler

    handler = HTTPOutputHandler(name="s", url="https://example.invalid/x", streaming=True)
    handler.initialize()
    submitted = []

    class FakeFuture:
        def result(self, timeout=None):
            return None

    class FakeExecutor:
        def submit(self, fn, event):
            submitted.append(event)
            fn(event)
            return FakeFuture()

        def shutdown(self, wait=True):
            return None

    handler._executor = FakeExecutor()
    monkeypatch.setattr(handler, "_send_single_event", lambda event: None)
    handler.write('{"z":1}')
    assert submitted == ['{"z":1}']
    handler.close()

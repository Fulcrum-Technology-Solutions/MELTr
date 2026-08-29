"""Tests for schedule gate evaluation."""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

import yaml

from meltr.core.config import (
    GeneratorConfig,
    OutputDefinition,
    ScheduleConfig,
    create_default_config,
)
from meltr.core.engine import Engine
from meltr.core.generator import GeneratorState
from meltr.core.schedule import ScheduleDecision, evaluate_schedule
from meltr.entities.registry import EntityRegistry

SAMPLE_ENTITIES = Path(__file__).parent.parent / "src" / "meltr" / "data" / "entities.sample.yaml"


def _dt(iso: str, tz: str = "UTC") -> datetime:
    """Build a timezone-aware datetime from an ISO local time string."""
    local = datetime.fromisoformat(iso)
    return local.replace(tzinfo=ZoneInfo(tz))


def test_continuous_always_emits():
    schedule = ScheduleConfig(mode="continuous")
    now = _dt("2026-08-29T03:00:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_window_inside_business_hours():
    schedule = ScheduleConfig(
        mode="window",
        days=["mon", "tue", "wed", "thu", "fri"],
        time="09:00-17:00",
        timezone="America/New_York",
    )
    # Friday 2026-08-28 10:30 EDT
    now = _dt("2026-08-28T10:30:00", "America/New_York")
    started = _dt("2026-08-28T09:00:00", "America/New_York")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_window_outside_time_range():
    schedule = ScheduleConfig(
        mode="window",
        days=["mon", "tue", "wed", "thu", "fri"],
        time="09:00-17:00",
        timezone="America/New_York",
    )
    # Friday 2026-08-28 20:00 EDT
    now = _dt("2026-08-28T20:00:00", "America/New_York")
    started = _dt("2026-08-28T09:00:00", "America/New_York")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=False, reason="outside_window")


def test_window_outside_allowed_day():
    schedule = ScheduleConfig(
        mode="window",
        days=["mon", "tue", "wed", "thu", "fri"],
        time="09:00-17:00",
        timezone="America/New_York",
    )
    # Saturday 2026-08-29 10:30 EDT
    now = _dt("2026-08-29T10:30:00", "America/New_York")
    started = _dt("2026-08-29T09:00:00", "America/New_York")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=False, reason="outside_window")


def test_burst_under_count_limit():
    schedule = ScheduleConfig(mode="burst", count=10)
    now = _dt("2026-08-29T00:01:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(schedule, now=now, events_emitted=9, started_at=started)

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_burst_count_reached():
    schedule = ScheduleConfig(mode="burst", count=10)
    now = _dt("2026-08-29T00:01:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(schedule, now=now, events_emitted=10, started_at=started)

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")


def test_burst_duration_exceeded():
    schedule = ScheduleConfig(mode="burst", duration="5m")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:05:00")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")


def test_burst_within_duration():
    schedule = ScheduleConfig(mode="burst", duration="5m")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:04:59")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_window_boundary_start_inclusive():
    schedule = ScheduleConfig(
        mode="window",
        days=["fri"],
        time="09:00-17:00",
        timezone="UTC",
    )
    now = _dt("2026-08-28T09:00:00", "UTC")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=now)

    assert decision.emit is True
    assert decision.reason == "ok"


def test_window_boundary_end_inclusive():
    schedule = ScheduleConfig(
        mode="window",
        days=["fri"],
        time="09:00-17:00",
        timezone="UTC",
    )
    now = _dt("2026-08-28T17:00:00", "UTC")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=now)

    assert decision.emit is True
    assert decision.reason == "ok"


def test_window_overnight_span():
    schedule = ScheduleConfig(
        mode="window",
        days=["fri"],
        time="22:00-06:00",
        timezone="UTC",
    )
    now = _dt("2026-08-28T23:30:00", "UTC")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=now)

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_burst_duration_seconds_suffix():
    schedule = ScheduleConfig(mode="burst", duration="30seconds")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:00:31")

    decision = evaluate_schedule(schedule, now=now, events_emitted=0, started_at=started)

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")


def _install_high_rate_template(base: Path) -> str:
    """Install a fast template under default/ layout."""
    events_dir = base / "templates" / "default" / "testvendor" / "testproduct" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    template_id = "testvendor/testproduct/events/window_test"

    (events_dir.parent / "collection.json").write_text(
        json.dumps({"version": "1.0.0", "templates": ["events/window_test"]}),
        encoding="utf-8",
    )
    (events_dir / "window_test.j2").write_text(
        '{{ {"marker": "window-test"} | tojson }}\n',
        encoding="utf-8",
    )
    (events_dir / "window_test.meta.yaml").write_text(
        "vendor: testvendor\n"
        "product: testproduct\n"
        "data_source: events\n"
        "description: Window schedule test template\n"
        "format: JSON\n"
        "is_generator: true\n"
        "base_frequency: 360000\n",
        encoding="utf-8",
    )
    return template_id


def test_generator_window_schedule_emits_zero_outside_window(tmp_path, monkeypatch) -> None:
    """Standalone generator with window schedule emits nothing outside the window."""
    monkeypatch.setenv("MELTR_HOME", str(tmp_path))
    template_id = _install_high_rate_template(tmp_path)
    shutil.copy(SAMPLE_ENTITIES, tmp_path / "entities.yaml")

    out_file = tmp_path / "window-out.log"
    config = create_default_config(tmp_path)
    config.outputs.definitions = [
        OutputDefinition(name="window-file", type="file", path=str(out_file))
    ]
    config.generators = [
        GeneratorConfig(
            name="window-gen",
            template=template_id,
            enabled=False,
            outputs=["window-file"],
            timezone="America/New_York",
            schedule=ScheduleConfig(
                mode="window",
                days=["mon", "tue", "wed", "thu", "fri"],
                time="09:00-17:00",
                timezone="America/New_York",
            ),
        )
    ]

    config_path = tmp_path / "config.yaml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.dump(config.model_dump(mode="json"), handle, default_flow_style=False)

    # Saturday 20:00 EDT — outside weekday business hours.
    frozen_outside = datetime(2026, 8, 29, 20, 0, 0, tzinfo=ZoneInfo("America/New_York"))

    def _fake_now(tz=None):
        return frozen_outside.astimezone(tz) if tz else frozen_outside

    registry = EntityRegistry(config)
    engine = Engine(config, registry)

    try:
        with mock.patch("meltr.core.generator.datetime") as mock_datetime:
            mock_datetime.now.side_effect = _fake_now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            engine.start_generator("window-gen")
            time.sleep(1.5)

            status = engine.get_generator_status("window-gen")
            assert status["statistics"]["events_generated"] == 0
            assert not out_file.exists() or out_file.read_text().strip() == ""
            assert status["state"] in {
                GeneratorState.RUNNING.value,
                GeneratorState.STARTING.value,
            }
            engine.stop_generator("window-gen")
    finally:
        engine.shutdown()

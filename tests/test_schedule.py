"""Tests for schedule gate evaluation."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from meltr.core.config import ScheduleConfig
from meltr.core.schedule import ScheduleDecision, evaluate_schedule


def _dt(iso: str, tz: str = "UTC") -> datetime:
    """Build a timezone-aware datetime from an ISO local time string."""
    local = datetime.fromisoformat(iso)
    return local.replace(tzinfo=ZoneInfo(tz))


def test_continuous_always_emits():
    schedule = ScheduleConfig(mode="continuous")
    now = _dt("2026-08-29T03:00:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

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

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

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

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

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

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

    assert decision == ScheduleDecision(emit=False, reason="outside_window")


def test_burst_under_count_limit():
    schedule = ScheduleConfig(mode="burst", count=10)
    now = _dt("2026-08-29T00:01:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=9, started_at=started
    )

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_burst_count_reached():
    schedule = ScheduleConfig(mode="burst", count=10)
    now = _dt("2026-08-29T00:01:00")
    started = _dt("2026-08-29T00:00:00")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=10, started_at=started
    )

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")


def test_burst_duration_exceeded():
    schedule = ScheduleConfig(mode="burst", duration="5m")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:05:00")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")


def test_burst_within_duration():
    schedule = ScheduleConfig(mode="burst", duration="5m")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:04:59")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_window_boundary_start_inclusive():
    schedule = ScheduleConfig(
        mode="window",
        days=["fri"],
        time="09:00-17:00",
        timezone="UTC",
    )
    now = _dt("2026-08-28T09:00:00", "UTC")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=now
    )

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

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=now
    )

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

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=now
    )

    assert decision == ScheduleDecision(emit=True, reason="ok")


def test_burst_duration_seconds_suffix():
    schedule = ScheduleConfig(mode="burst", duration="30seconds")
    started = _dt("2026-08-29T00:00:00")
    now = _dt("2026-08-29T00:00:31")

    decision = evaluate_schedule(
        schedule, now=now, events_emitted=0, started_at=started
    )

    assert decision == ScheduleDecision(emit=False, reason="burst_complete")

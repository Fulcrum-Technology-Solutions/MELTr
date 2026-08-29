"""Schedule gate for pipeline and generator emission control."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from meltr.core.config import ScheduleConfig

_DAY_NAME_TO_ISO = {
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
    "sun": 7,
    "sunday": 7,
}

_DURATION_MULTIPLIERS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


@dataclass
class ScheduleDecision:
    """Result of schedule gate evaluation."""

    emit: bool
    reason: str  # "ok" | "outside_window" | "burst_complete"


def evaluate_schedule(
    schedule: ScheduleConfig,
    *,
    now: datetime,
    events_emitted: int,
    started_at: datetime,
) -> ScheduleDecision:
    """Evaluate whether emission is allowed under the configured schedule."""
    if schedule.mode == "continuous":
        return ScheduleDecision(emit=True, reason="ok")

    if schedule.mode == "window":
        if _inside_window(schedule, now):
            return ScheduleDecision(emit=True, reason="ok")
        return ScheduleDecision(emit=False, reason="outside_window")

    if schedule.mode == "burst":
        if _burst_complete(schedule, now=now, events_emitted=events_emitted, started_at=started_at):
            return ScheduleDecision(emit=False, reason="burst_complete")
        return ScheduleDecision(emit=True, reason="ok")

    return ScheduleDecision(emit=True, reason="ok")


def _inside_window(schedule: ScheduleConfig, now: datetime) -> bool:
    tz = _resolve_timezone(schedule.timezone)
    local_now = now.astimezone(tz)

    if schedule.days:
        allowed_days = {_DAY_NAME_TO_ISO[d.lower()] for d in schedule.days if d.lower() in _DAY_NAME_TO_ISO}
        if allowed_days and local_now.isoweekday() not in allowed_days:
            return False

    if schedule.time and "-" in schedule.time:
        start_str, end_str = schedule.time.split("-", 1)
        start_time = _parse_time(start_str)
        end_time = _parse_time(end_str)
        current_time = local_now.time()
        if start_time <= end_time:
            if not (start_time <= current_time <= end_time):
                return False
        elif not (current_time >= start_time or current_time <= end_time):
            return False

    return True


def _burst_complete(
    schedule: ScheduleConfig,
    *,
    now: datetime,
    events_emitted: int,
    started_at: datetime,
) -> bool:
    if schedule.count is not None and events_emitted >= schedule.count:
        return True

    duration_seconds = _parse_duration(schedule.duration)
    if duration_seconds is not None:
        elapsed = now - started_at
        if elapsed >= timedelta(seconds=duration_seconds):
            return True

    return False


def _resolve_timezone(timezone_name: Optional[str]) -> ZoneInfo:
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except Exception:
            pass
    return ZoneInfo("UTC")


def _parse_time(time_str: str) -> time:
    try:
        hour, minute = map(int, time_str.strip().split(":", 1))
        return time(hour, minute)
    except (ValueError, AttributeError):
        return time(0, 0)


def _parse_duration(duration: Optional[str]) -> Optional[int]:
    if not duration:
        return None

    value = duration.lower().strip()
    for unit, multiplier in sorted(
        _DURATION_MULTIPLIERS.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if value.endswith(unit):
            try:
                number = int(value[: -len(unit)])
            except ValueError:
                return None
            return number * multiplier

    return None

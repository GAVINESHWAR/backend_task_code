"""Scheduling helpers: available time, rescheduling, task splitting (§18, §20, §34)."""
from __future__ import annotations

from datetime import date, datetime, time as dtime

from app.core import recommendation_config as cfg


def parse_hm(value: str) -> dtime:
    h, m = value.split(":")
    return dtime(int(h), int(m))


def minutes_between(start: str, end: str) -> int:
    s, e = parse_hm(start), parse_hm(end)
    return (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)


def available_minutes_today(time_blocks: list[dict], events: list[dict], on_date: date) -> int:
    """Sum time-block minutes minus overlapping event minutes, minus buffer."""
    total = 0
    for b in time_blocks:
        wd = b.get("weekday")
        if wd is not None and wd != on_date.weekday():
            continue
        total += max(0, minutes_between(b["start_time"], b["end_time"]))
    busy = 0
    for e in events:
        s: datetime = e["start_time"]
        en: datetime = e["end_time"]
        if s.date() == on_date:
            busy += max(0, int((en - s).total_seconds() // 60))
    return max(0, total - busy - cfg.BUFFER_MINUTES_PER_DAY) if total else max(0, 8 * 60 - busy - cfg.BUFFER_MINUTES_PER_DAY)


def suggest_split(estimated_minutes: int, chunk: int = 25) -> list[dict]:
    """Split a large task into parent + N sub-steps (§18)."""
    if estimated_minutes <= cfg.BREAKDOWN_THRESHOLD_MINUTES:
        return []
    steps: list[dict] = []
    remaining = estimated_minutes
    i = 1
    while remaining > 0:
        take = min(chunk, remaining)
        steps.append({"title": f"Step {i} — {take} min", "estimated_minutes": take})
        remaining -= take
        i += 1
    return steps


def reschedule_options(task: dict) -> list[dict]:
    """Rule-based options for an overdue task (§34)."""
    postponed = task.get("postponed_count", 0) or 0
    options = [
        {"action": "move_tomorrow", "label": "Move to tomorrow"},
        {"action": "next_slot", "label": "Find next available slot"},
        {"action": "backlog", "label": "Keep in backlog"},
        {"action": "cancel", "label": "Cancel"},
    ]
    est = task.get("estimated_minutes") or 0
    if est > cfg.BREAKDOWN_THRESHOLD_MINUTES or postponed >= cfg.POSTPONE_NUDGE_THRESHOLD:
        options.insert(2, {"action": "split", "label": "Break into smaller tasks"})
    if postponed >= cfg.POSTPONE_NUDGE_THRESHOLD:
        options.append({"action": "reduce_scope", "label": "Reduce estimated duration"})
    return options

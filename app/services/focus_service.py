"""Focus session state machine (§13-§15)."""
from __future__ import annotations

ALLOWED_TRANSITIONS = {
    "Active": {"Paused", "Completed", "Cancelled", "Interrupted"},
    "Paused": {"Active", "Completed", "Cancelled"},
    "Interrupted": {"Active", "Cancelled"},
    "Completed": set(),
    "Cancelled": set(),
}


def can_transition(frm: str, to: str) -> bool:
    return to in ALLOWED_TRANSITIONS.get(frm, set())


def actual_minutes(started, ended) -> int:
    if not started or not ended:
        return 0
    return max(0, int((ended - started).total_seconds() // 60))

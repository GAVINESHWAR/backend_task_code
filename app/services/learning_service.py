"""Spaced repetition + learning helpers (§26)."""
from __future__ import annotations

from datetime import date, timedelta

from app.core import recommendation_config as cfg


def next_review_date(from_date: date, stage: int, difficult: bool = False) -> tuple[date, int]:
    """Return (next_date, new_stage) after a review at given stage."""
    intervals = cfg.REVIEW_INTERVALS_DAYS
    new_stage = min(stage + 1, len(intervals) - 1)
    if difficult:
        new_stage = max(0, stage - cfg.DIFFICULT_STEP_BACK)
    delta = intervals[new_stage] if new_stage < len(intervals) else intervals[-1]
    return from_date + timedelta(days=delta), new_stage


def due_for_review(topics: list[dict], today: date) -> list[dict]:
    return [t for t in topics if (t.get("next_review_date") is None) or (t.get("next_review_date") <= today)]

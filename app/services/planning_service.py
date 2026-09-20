"""Planning (morning/end-of-day) + analytics aggregation (§36, §37, §33)."""
from __future__ import annotations

from collections import Counter
from datetime import date


def morning_plan(events, top_tasks, recommended, learning_due, personal, available_minutes) -> dict:
    return {
        "fixed_events": events,
        "top_priorities": top_tasks,
        "recommended_tasks": recommended,
        "learning_session": learning_due,
        "personal_tasks": personal,
        "available_minutes": available_minutes,
    }


def end_of_day_summary(tasks_completed, tasks_unfinished, interrupted, overdue, learning_done, focus_minutes, distractions) -> dict:
    return {
        "completed": tasks_completed,
        "unfinished": tasks_unfinished,
        "interrupted": interrupted,
        "overdue": overdue,
        "learning_completed": learning_done,
        "focus_minutes": focus_minutes,
        "distractions": distractions,
    }


def focus_stats(sessions: list[dict]) -> dict:
    minutes = [s.get("actual_minutes", 0) or 0 for s in sessions]
    total = sum(minutes)
    return {
        "total_focus_minutes": total,
        "session_count": len(sessions),
        "average_minutes": round(total / len(sessions), 1) if sessions else 0,
        "longest_minutes": max(minutes) if minutes else 0,
        "interruptions": sum(s.get("interruption_count", 0) or 0 for s in sessions),
    }


def category_allocation(tasks_or_sessions: list[dict]) -> dict:
    c = Counter(t.get("category", "Other") for t in tasks_or_sessions)
    total = sum(c.values()) or 1
    return {k: round(v / total * 100, 1) for k, v in c.items()}

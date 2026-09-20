"""Rule-based recommendation engine (§7, §35). No AI — pure scoring."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core import recommendation_config as cfg


def score_task(task: dict, ctx: dict) -> tuple[float, list[str]]:
    """Return (score, reasons). ``task`` and ``ctx`` are plain dicts so the
    engine is unit-testable without a DB."""
    today: date = ctx.get("today")
    available_minutes: int | None = ctx.get("available_minutes")
    requested_context: str | None = ctx.get("context")
    today_ids: set[str] = set(ctx.get("today_priority_ids") or [])
    has_workstate: bool = bool(ctx.get("has_workstate"))
    was_interrupted: bool = bool(ctx.get("was_interrupted"))
    project_priority: str | None = ctx.get("project_priority")

    score = 0.0
    reasons: list[str] = []

    prio = task.get("priority", "Medium")
    w = cfg.PRIORITY_WEIGHTS.get(prio, 40)
    score += w
    reasons.append(f"{prio} priority (+{w})")

    due = task.get("due_date")
    if due and today:
        delta = (due - today).days
        if delta < 0:
            bonus = min(cfg.DEADLINE_BONUS["overdue_per_day_cap"],
                        abs(delta) * cfg.DEADLINE_BONUS["overdue_per_day"] + 30)
            score += bonus
            reasons.append(f"Overdue by {abs(delta)}d (+{bonus})")
        elif delta == 0:
            score += cfg.DEADLINE_BONUS["due_today"]
            reasons.append(f"Due today (+{cfg.DEADLINE_BONUS['due_today']})")
        elif delta == 1:
            score += cfg.DEADLINE_BONUS["due_tomorrow"]
            reasons.append(f"Due tomorrow (+{cfg.DEADLINE_BONUS['due_tomorrow']})")
        elif delta <= 3:
            score += cfg.DEADLINE_BONUS["due_within_3_days"]
        elif delta <= 7:
            score += cfg.DEADLINE_BONUS["due_within_7_days"]

    if has_workstate or was_interrupted:
        score += cfg.CONTINUATION_BONUS
        reasons.append(f"Continue where you left off (+{cfg.CONTINUATION_BONUS})")

    if str(task.get("id")) in today_ids:
        score += cfg.TODAY_PLAN_BONUS
        reasons.append(f"In today's top priorities (+{cfg.TODAY_PLAN_BONUS})")

    if requested_context and task.get("context") == requested_context:
        score += cfg.CONTEXT_MATCH_BONUS
        reasons.append(f"Matches context '{requested_context}' (+{cfg.CONTEXT_MATCH_BONUS})")

    if project_priority:
        score += cfg.PROJECT_IMPORTANCE.get(project_priority, 0)

    est = task.get("estimated_minutes") or 30
    if available_minutes is not None:
        if est <= available_minutes:
            score += cfg.TIME_FIT_BONUS
            reasons.append(f"Fits your {available_minutes}-min window (+{cfg.TIME_FIT_BONUS})")
        else:
            score -= cfg.TIME_MISMATCH_PENALTY
            reasons.append(f"Needs {est}m, only {available_minutes}m free (-{cfg.TIME_MISMATCH_PENALTY})")

    start = task.get("start_date")
    if start and today and start > today:
        score -= cfg.FUTURE_START_PENALTY
        reasons.append(f"Future start date (-{cfg.FUTURE_START_PENALTY})")

    if task.get("status") == "Waiting":
        score -= cfg.BLOCKED_PENALTY
        reasons.append(f"Blocked/waiting (-{cfg.BLOCKED_PENALTY})")

    if task.get("parent_incomplete"):
        score -= cfg.DEPENDENCY_PENALTY
        reasons.append(f"Parent task incomplete (-{cfg.DEPENDENCY_PENALTY})")

    if (task.get("postponed_count") or 0) >= cfg.POSTPONE_NUDGE_THRESHOLD:
        score -= 10
        reasons.append("Postponed repeatedly — consider splitting (-10)")

    return score, reasons


def pick_next(candidates: list[dict], ctx: dict) -> dict | None:
    """Pick highest scoring candidate. Returns {task, score, reasons}."""
    best = None
    best_score = float("-inf")
    best_reasons: list[str] = []
    for t in candidates:
        s, r = score_task(t, ctx)
        if s > best_score:
            best, best_score, best_reasons = t, s, r
    if best is None:
        return None
    return {"task": best, "score": best_score, "reasons": best_reasons}


def human_reason(task: dict, reasons: list[str], score: float) -> str:
    title = task.get("title", "task")
    fit = ""
    est = task.get("estimated_minutes")
    if est:
        fit = f" (~{est} min)"
    top = reasons[0] if reasons else "matches your plan"
    return f"{title}{fit} — {top}."

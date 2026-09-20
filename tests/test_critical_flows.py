"""Critical-flow tests (§51). Service-level: no DB required, run with `pytest`."""
from datetime import date, timedelta

from app.services import recommendation_service as rec
from app.services.focus_service import actual_minutes, can_transition
from app.services.learning_service import due_for_review, next_review_date
from app.services.scheduling_service import available_minutes_today, reschedule_options, suggest_split


def _task(**kw):
    base = {"id": "t1", "title": "Payment verification", "priority": "High",
            "due_date": date.today(), "estimated_minutes": 25, "status": "Planned",
            "context": "Work", "postponed_count": 0}
    base.update(kw)
    return base


def test_recommendation_prefers_overdue_urgent():
    today = date.today()
    ctx = {"today": today, "available_minutes": 30}
    a = _task(id="a", priority="Low", due_date=today + timedelta(days=30), estimated_minutes=20)
    b = _task(id="b", priority="Urgent", due_date=today - timedelta(days=2), estimated_minutes=25)
    sa, _ = rec.score_task(a, ctx)
    sb, _ = rec.score_task(b, ctx)
    assert sb > sa
    pick = rec.pick_next([a, b], ctx)
    assert pick["task"]["id"] == "b"


def test_recommendation_time_fit_bonus_and_penalty():
    ctx = {"today": date.today(), "available_minutes": 30}
    fits = _task(estimated_minutes=25)
    big = _task(estimated_minutes=120)
    assert rec.score_task(fits, ctx)[0] > rec.score_task(big, ctx)[0]


def test_recommendation_continuation_bonus():
    ctx = {"today": date.today(), "available_minutes": 60}
    plain = _task()
    resumed = _task()
    s1, _ = rec.score_task(plain, ctx)
    s2, _ = rec.score_task(resumed, {**ctx, "has_workstate": True})
    assert s2 > s1


def test_recommendation_blocked_penalty():
    ctx = {"today": date.today(), "available_minutes": 60}
    ok = _task()
    blocked = _task(status="Waiting")
    assert rec.score_task(ok, ctx)[0] > rec.score_task(blocked, ctx)[0]


def test_split_suggests_steps_for_large_task():
    steps = suggest_split(120, 25)
    assert len(steps) == 5
    assert sum(s["estimated_minutes"] for s in steps) == 120
    assert suggest_split(60) == []


def test_reschedule_options_nudge_after_3_postpones():
    opts = reschedule_options({"postponed_count": 3, "estimated_minutes": 30})
    actions = [o["action"] for o in opts]
    assert "split" in actions


def test_available_minutes_subtracts_events_and_buffer():
    blocks = [{"weekday": None, "start_time": "09:00", "end_time": "17:00"}]  # 480m
    from datetime import datetime
    events = [{"start_time": datetime(2026, 9, 21, 10, 0), "end_time": datetime(2026, 9, 21, 11, 0)}]
    avail = available_minutes_today(blocks, events, date(2026, 9, 21))
    assert avail == 480 - 60 - 60  # events minus buffer


def test_focus_state_machine():
    assert can_transition("Active", "Paused")
    assert can_transition("Paused", "Active")
    assert not can_transition("Completed", "Active")
    from datetime import datetime, timezone
    s = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    e = datetime(2026, 1, 1, 10, 45, tzinfo=timezone.utc)
    assert actual_minutes(s, e) == 45


def test_spaced_repetition_intervals():
    nxt, stage = next_review_date(date(2026, 9, 20), 0)
    assert nxt == date(2026, 9, 21) and stage == 1
    nxt2, _ = next_review_date(date(2026, 9, 20), 2)
    assert nxt2 == date(2026, 9, 27)  # +7
    # difficult steps back
    nxt3, stage3 = next_review_date(date(2026, 9, 20), 3, difficult=True)
    assert stage3 == 2


def test_due_for_review():
    topics = [{"id": "1", "next_review_date": date.today()},
              {"id": "2", "next_review_date": date.today() + timedelta(days=5)}]
    assert len(due_for_review(topics, date.today())) == 1

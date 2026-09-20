"""Calendar, time blocks, daily planning & reviews (§19-§22, §36-§37)."""
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import DailyPlan, DailyReview, Event, FocusSession, Task, TimeBlock
from app.schemas.schemas import DailyPlanUpsert, DailyReviewUpsert, EventCreate, TimeBlockCreate
from app.services import recommendation_service as rec
from app.services.planning_service import end_of_day_summary, morning_plan
from app.services.scheduling_service import available_minutes_today

router = APIRouter(tags=["planning"])


# ---- events ----
@router.get("/calendar/events")
def list_events(day: date | None = Query(default=None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Event).filter(Event.user_id == user.id).order_by(Event.start_time)
    if day:
        start = datetime(day.year, day.month, day.day)
        end = datetime(day.year, day.month, day.day, 23, 59, 59)
        q = q.filter(Event.start_time >= start, Event.start_time <= end)
    rows = q.limit(200).all()
    return {"success": True, "data": [{"id": str(e.id), "title": e.title, "start_time": e.start_time.isoformat(),
                                       "end_time": e.end_time.isoformat(), "category": e.category} for e in rows]}


@router.post("/calendar/events", status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=422, detail="end_time must be after start_time.")
    # Scheduling conflict detection (§41)
    clash = db.query(Event).filter(Event.user_id == user.id, Event.start_time < payload.end_time,
                                   Event.end_time > payload.start_time).first()
    if clash:
        raise HTTPException(status_code=409, detail=f"Conflicts with '{clash.title}'.")
    e = Event(user_id=user.id, **payload.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"success": True, "data": {"id": str(e.id)}}


# ---- time blocks ----
@router.get("/calendar/time-blocks")
def list_blocks(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(TimeBlock).filter(TimeBlock.user_id == user.id).all()
    return {"success": True, "data": [{"id": str(b.id), "label": b.label, "weekday": b.weekday,
                                       "start_time": b.start_time, "end_time": b.end_time} for b in rows]}


@router.post("/calendar/time-blocks", status_code=201)
def create_block(payload: TimeBlockCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    b = TimeBlock(user_id=user.id, **payload.model_dump())
    db.add(b)
    db.commit()
    db.refresh(b)
    return {"success": True, "data": {"id": str(b.id)}}


# ---- daily plan ----
@router.get("/planning/today")
def today_plan(day: date | None = None, context: str | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    today = day or date.today()
    events = db.query(Event).filter(Event.user_id == user.id).all()
    events_today = [{"title": e.title, "start_time": e.start_time.isoformat(), "end_time": e.end_time.isoformat()}
                    for e in events if e.start_time.date() == today]
    blocks = [{"weekday": b.weekday, "start_time": b.start_time, "end_time": b.end_time}
              for b in db.query(TimeBlock).filter(TimeBlock.user_id == user.id).all()]
    avail = available_minutes_today(blocks, [{"start_time": e.start_time, "end_time": e.end_time} for e in events], today)
    plan = db.query(DailyPlan).filter(DailyPlan.user_id == user.id, DailyPlan.plan_date == today).first()
    top_ids = set(plan.top_priorities if plan else [])
    open_tasks = db.query(Task).filter(Task.user_id == user.id, Task.status.notin_(["Completed", "Cancelled"]),
                                       Task.deleted_at.is_(None)).all()
    cands = [{"id": str(t.id), "title": t.title, "priority": t.priority, "due_date": t.due_date,
              "estimated_minutes": t.estimated_minutes, "status": t.status, "context": t.context,
              "postponed_count": t.postponed_count} for t in open_tasks]
    ctx = {"today": today, "available_minutes": avail, "context": context, "today_priority_ids": top_ids}
    scored = sorted(((rec.score_task(c, ctx)[0], c) for c in cands), reverse=True)
    recommended = [{"task_id": c["id"], "title": c["title"], "score": s} for s, c in scored[:5]]
    top_tasks = [c for _, c in scored if c["id"] in top_ids][:3]
    return {"success": True, "data": morning_plan(events_today, top_tasks, recommended, [], [], avail)}


@router.put("/planning/daily-plan")
def upsert_plan(payload: DailyPlanUpsert, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if len(payload.top_priorities) > 3:
        raise HTTPException(status_code=422, detail="Top priorities: maximum 3.")
    plan = db.query(DailyPlan).filter(DailyPlan.user_id == user.id, DailyPlan.plan_date == payload.plan_date).first()
    if plan:
        plan.top_priorities = [str(x) for x in payload.top_priorities]
        plan.secondary_tasks = [str(x) for x in payload.secondary_tasks]
        plan.notes = payload.notes
    else:
        plan = DailyPlan(user_id=user.id, plan_date=payload.plan_date,
                         top_priorities=[str(x) for x in payload.top_priorities],
                         secondary_tasks=[str(x) for x in payload.secondary_tasks], notes=payload.notes)
        db.add(plan)
    db.commit()
    return {"success": True, "message": "Daily plan saved."}


@router.get("/planning/end-of-day")
def eod(day: date | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    today = day or date.today()
    completed = db.query(Task).filter(Task.user_id == user.id, Task.status == "Completed").count()
    unfinished = db.query(Task).filter(Task.user_id == user.id, Task.status.notin_(["Completed", "Cancelled"])).count()
    overdue = db.query(Task).filter(Task.user_id == user.id, Task.due_date < today,
                                    Task.status.notin_(["Completed", "Cancelled"])).count()
    sessions = db.query(FocusSession).filter(FocusSession.user_id == user.id).all()
    focus_min = sum(s.actual_minutes or 0 for s in sessions)
    return {"success": True, "data": end_of_day_summary(completed, unfinished, 0, overdue, 0, focus_min, [])}


@router.put("/reviews/daily")
def upsert_review(payload: DailyReviewUpsert, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.query(DailyReview).filter(DailyReview.user_id == user.id, DailyReview.review_date == payload.review_date).first()
    if r:
        for k, v in payload.model_dump().items():
            if k != "review_date":
                setattr(r, k, v)
    else:
        r = DailyReview(user_id=user.id, **payload.model_dump())
        db.add(r)
    db.commit()
    return {"success": True, "message": "Review saved."}


@router.get("/reviews/daily")
def get_review(day: date, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.query(DailyReview).filter(DailyReview.user_id == user.id, DailyReview.review_date == day).first()
    if not r:
        return {"success": True, "data": None}
    return {"success": True, "data": {"review_date": r.review_date.isoformat(), "completed_summary": r.completed_summary,
                                      "focus_rating": r.focus_rating, "tomorrow_notes": r.tomorrow_notes}}

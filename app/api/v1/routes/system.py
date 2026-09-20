"""Recommendations, analytics, search (§33, §35, §38)."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import DailyPlan, Distraction, Event, FocusSession, Habit, LearningSession, LearningTopic, Note, Project, Task, TimeBlock
from app.services import recommendation_service as rec
from app.services.planning_service import category_allocation, focus_stats
from app.services.scheduling_service import available_minutes_today

router = APIRouter(tags=["system"])


@router.get("/recommendations/next-task")
def next_task(context: str | None = None, available_minutes: int | None = Query(default=None),
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    today = date.today()
    open_tasks = db.query(Task).filter(Task.user_id == user.id,
                                       Task.status.notin_(["Completed", "Cancelled"]),
                                       Task.deleted_at.is_(None)).all()
    if not open_tasks:
        return {"success": True, "data": {"task_id": None, "reason": "Inbox zero. Capture something new.", "score": 0}}
    events = db.query(Event).filter(Event.user_id == user.id).all()
    blocks = [{"weekday": b.weekday, "start_time": b.start_time, "end_time": b.end_time}
              for b in db.query(TimeBlock).filter(TimeBlock.user_id == user.id).all()]
    if available_minutes is None:
        available_minutes = available_minutes_today(
            blocks, [{"start_time": e.start_time, "end_time": e.end_time} for e in events], today)
    plan = db.query(DailyPlan).filter(DailyPlan.user_id == user.id, DailyPlan.plan_date == today).first()
    top_ids = set(plan.top_priorities if plan else [])
    # WorkState lookup for continuation bonus
    from app.models.models import WorkState
    ws_ids = {str(w.task_id) for w in db.query(WorkState).filter(WorkState.user_id == user.id).all()}
    proj_prio = {str(p.id): p.priority for p in db.query(Project).filter(Project.user_id == user.id).all()}
    cands = []
    for t in open_tasks:
        parent_incomplete = False
        if t.parent_task_id:
            parent = db.query(Task).filter(Task.id == t.parent_task_id).first()
            parent_incomplete = bool(parent and parent.status != "Completed")
        cands.append({"id": str(t.id), "title": t.title, "priority": t.priority, "due_date": t.due_date,
                      "estimated_minutes": t.estimated_minutes, "status": t.status, "context": t.context,
                      "start_date": t.start_date, "postponed_count": t.postponed_count or 0,
                      "parent_incomplete": parent_incomplete})
    ctx = {"today": today, "available_minutes": available_minutes, "context": context, "today_priority_ids": top_ids}
    best, best_score, reasons = None, float("-inf"), []
    for c in cands:
        c_ctx = dict(ctx)
        # project importance
        t_obj = next((x for x in open_tasks if str(x.id) == c["id"]), None)
        if t_obj and t_obj.project_id:
            c_ctx["project_priority"] = proj_prio.get(str(t_obj.project_id))
        c_ctx["has_workstate"] = c["id"] in ws_ids
        s, r = rec.score_task(c, c_ctx)
        if s > best_score:
            best, best_score, reasons = c, s, r
    reason = rec.human_reason(best, reasons, best_score)
    return {"success": True, "data": {"task_id": best["id"], "reason": reason,
                                      "estimated_minutes": best.get("estimated_minutes"), "score": round(best_score, 1)}}


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sessions = [{"actual_minutes": s.actual_minutes, "interruption_count": s.interruption_count}
                for s in db.query(FocusSession).filter(FocusSession.user_id == user.id).all()]
    tasks = db.query(Task).filter(Task.user_id == user.id, Task.deleted_at.is_(None)).all()
    task_stats = {
        "completed": len([t for t in tasks if t.status == "Completed"]),
        "pending": len([t for t in tasks if t.status not in ("Completed", "Cancelled")]),
        "overdue": len([t for t in tasks if t.due_date and t.due_date < date.today() and t.status not in ("Completed", "Cancelled")]),
        "deferred": len([t for t in tasks if t.status == "Deferred"]),
    }
    learning_minutes = sum(s.duration_minutes or 0 for s in
                           db.query(LearningSession).filter(LearningSession.user_id == user.id).all())
    topics_done = db.query(LearningTopic).filter(LearningTopic.user_id == user.id, LearningTopic.status == "Completed").count()
    distractions = db.query(Distraction).filter(Distraction.user_id == user.id).all()
    return {"success": True, "data": {
        "focus": focus_stats(sessions),
        "tasks": task_stats,
        "learning": {"learning_minutes": learning_minutes, "topics_completed": topics_done},
        "time_allocation": category_allocation([{"category": t.category} for t in tasks]),
        "distractions_minutes": sum(d.duration_minutes or 0 for d in distractions),
    }}


@router.get("/search")
def global_search(q: str = Query(min_length=2), db: Session = Depends(get_db), user=Depends(get_current_user)):
    like = f"%{q}%"
    tasks = db.query(Task).filter(Task.user_id == user.id, or_(Task.title.ilike(like), Task.description.ilike(like))).limit(10).all()
    notes = db.query(Note).filter(Note.user_id == user.id, or_(Note.title.ilike(like), Note.content.ilike(like))).limit(10).all()
    projects = db.query(Project).filter(Project.user_id == user.id, Project.name.ilike(like)).limit(5).all()
    habits = db.query(Habit).filter(Habit.user_id == user.id, Habit.title.ilike(like)).limit(5).all()
    return {"success": True, "data": {
        "tasks": [{"id": str(t.id), "title": t.title} for t in tasks],
        "notes": [{"id": str(n.id), "title": n.title} for n in notes],
        "projects": [{"id": str(p.id), "name": p.name} for p in projects],
        "habits": [{"id": str(h.id), "title": h.title} for h in habits],
    }}

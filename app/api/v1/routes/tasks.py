"""Tasks + subtasks + reschedule helpers (§8, §10, §18, §34)."""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core import recommendation_config as cfg
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Task
from app.repositories.base import log_activity
from app.schemas.schemas import TaskCreate, TaskUpdate
from app.services.scheduling_service import reschedule_options, suggest_split

router = APIRouter(prefix="/tasks", tags=["tasks"])

TERMINAL = {"Completed", "Cancelled"}


def _serialize(t: Task) -> dict:
    return {
        "id": str(t.id), "title": t.title, "description": t.description,
        "status": t.status, "priority": t.priority, "category": t.category,
        "project_id": str(t.project_id) if t.project_id else None,
        "goal_id": str(t.goal_id) if t.goal_id else None,
        "parent_task_id": str(t.parent_task_id) if t.parent_task_id else None,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "estimated_minutes": t.estimated_minutes, "actual_minutes": t.actual_minutes,
        "energy_level": t.energy_level, "context": t.context,
        "postponed_count": t.postponed_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("")
def list_tasks(
    status: str | None = None, category: str | None = None, project_id: UUID | None = None,
    search: str | None = None, limit: int = Query(50, le=200), offset: int = 0,
    db: Session = Depends(get_db), user=Depends(get_current_user),
):
    q = db.query(Task).filter(Task.user_id == user.id, Task.deleted_at.is_(None))
    if status:
        q = q.filter(Task.status == status)
    if category:
        q = q.filter(Task.category == category)
    if project_id:
        q = q.filter(Task.project_id == project_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))
    q = q.order_by(Task.created_at.desc()).limit(limit).offset(offset)
    return {"success": True, "data": [_serialize(t) for t in q.all()]}


@router.post("", status_code=201)
def create_task(payload: TaskCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Quick-add: only title is truly required (§9); schema defaults the rest.
    t = Task(user_id=user.id, **payload.model_dump())
    if t.status == "Inbox" and t.start_date:
        t.status = "Planned"
    elif t.status == "Inbox" and t.due_date:
        t.status = "Planned"
    db.add(t)
    db.commit()
    db.refresh(t)
    log_activity(db, user.id, "task", t.id, "Task created", {"title": t.title})
    out = _serialize(t)
    # Non-AI breakdown nudge (§18)
    if (t.estimated_minutes or 0) > cfg.BREAKDOWN_THRESHOLD_MINUTES:
        out["suggest_split"] = True
        out["chunk_options"] = list(cfg.BREAKDOWN_CHUNK_OPTIONS)
    return {"success": True, "message": "Task created.", "data": out}


@router.get("/{task_id}")
def get_task(task_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    data = _serialize(t)
    data["subtasks"] = [_serialize(s) for s in db.query(Task).filter(Task.parent_task_id == t.id).all()]
    data["notes"] = []  # joined by frontend via /notes?task_id=
    return {"success": True, "data": data}


@router.patch("/{task_id}")
def update_task(task_id: UUID, payload: TaskUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    data = payload.model_dump(exclude_unset=True)
    data.pop("progress_percent", None)
    # Invalid state transitions: terminal tasks cannot be re-opened silently
    if t.status in TERMINAL and data.get("status") not in (None, t.status):
        raise HTTPException(status_code=409, detail=f"Cannot move task from {t.status}.")
    # Postpone tracking (§34): moving due_date forward counts as a postponement
    if data.get("due_date") and t.due_date and data["due_date"] > t.due_date and t.status != "Completed":
        t.postponed_count = (t.postponed_count or 0) + 1
        log_activity(db, user.id, "task", t.id, "Task postponed", {"postponed_count": t.postponed_count})
    for k, v in data.items():
        setattr(t, k, v)
    if t.status == "Completed" and not t.completed_at:
        from datetime import datetime, timezone
        t.completed_at = datetime.now(timezone.utc)
        log_activity(db, user.id, "task", t.id, "Task completed", {})
    db.commit()
    db.refresh(t)
    return {"success": True, "message": "Task updated.", "data": _serialize(t)}


@router.post("/{task_id}/complete")
def complete_task(task_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    from datetime import datetime, timezone
    t.status = "Completed"
    t.completed_at = datetime.now(timezone.utc)
    db.commit()
    log_activity(db, user.id, "task", t.id, "Task completed", {})
    return {"success": True, "message": "Task completed.", "data": _serialize(t)}


@router.post("/{task_id}/split")
def split_task(task_id: UUID, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Auto-subdivide a large task into N sub-steps (§18). Body: {chunk_minutes}."""
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    chunk = int(body.get("chunk_minutes", 25))
    steps = suggest_split(t.estimated_minutes or 0, chunk)
    if not steps:
        raise HTTPException(status_code=400, detail="Task is small enough; no split needed.")
    created = []
    for s in steps:
        sub = Task(user_id=user.id, title=f"{t.title} — {s['title']}",
                   status="Planned", priority=t.priority, category=t.category,
                   project_id=t.project_id, parent_task_id=t.id, estimated_minutes=s["estimated_minutes"])
        db.add(sub)
        created.append(sub)
    db.commit()
    return {"success": True, "message": f"Split into {len(created)} steps.", "data": [_serialize(c) for c in created]}


@router.get("/{task_id}/reschedule-options")
def reschedule(task_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    overdue = bool(t.due_date and t.due_date < date.today() and t.status != "Completed")
    return {"success": True, "data": {
        "overdue": overdue,
        "postponed_count": t.postponed_count,
        "options": reschedule_options(_serialize(t)),
        "nudge": t.postponed_count >= cfg.POSTPONE_NUDGE_THRESHOLD,
    }}


@router.delete("/{task_id}")
def delete_task(task_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found.")
    from datetime import datetime, timezone
    t.deleted_at = datetime.now(timezone.utc)  # soft delete
    db.commit()
    return {"success": True, "message": "Task deleted."}

"""Focus sessions + work-states (§13-§17)."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import FocusSession, Task, WorkState
from app.repositories.base import log_activity
from app.schemas.schemas import FocusNote, FocusStart, WorkStateUpsert
from app.services.focus_service import actual_minutes, can_transition

router = APIRouter(tags=["focus"])


@router.post("/focus/start", status_code=201)
def start_focus(payload: FocusStart, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == payload.task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    # Single active session per user: pause the previous one (checkpoint §17)
    active = db.query(FocusSession).filter(FocusSession.user_id == user.id, FocusSession.status == "Active").first()
    if active:
        active.status = "Paused"
    task.status = "In Progress"
    s = FocusSession(user_id=user.id, task_id=task.id, started_at=datetime.now(timezone.utc),
                     planned_minutes=payload.planned_minutes, status="Active")
    db.add(s)
    db.commit()
    db.refresh(s)
    log_activity(db, user.id, "focus_session", s.id, "Focus session started", {"task_id": str(task.id)})
    return {"success": True, "data": {"id": str(s.id), "task_id": str(task.id), "started_at": s.started_at.isoformat()}}


def _get_session(sid: UUID, db: Session, user) -> FocusSession:
    s = db.query(FocusSession).filter(FocusSession.id == sid, FocusSession.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Focus session not found.")
    return s


@router.post("/focus/{session_id}/pause")
def pause_focus(session_id: UUID, body: WorkStateUpsert | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = _get_session(session_id, db, user)
    if not can_transition(s.status, "Paused"):
        raise HTTPException(status_code=409, detail=f"Cannot pause from {s.status}.")
    s.status = "Paused"
    s.interruption_count = (s.interruption_count or 0) + 1
    if body:
        upsert_workstate(db, user, s.task_id, body)
    db.commit()
    log_activity(db, user.id, "focus_session", s.id, "Focus session paused", {})
    return {"success": True, "message": "Paused. WorkState saved."}


@router.post("/focus/{session_id}/resume")
def resume_focus(session_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = _get_session(session_id, db, user)
    if not can_transition(s.status, "Active"):
        raise HTTPException(status_code=409, detail=f"Cannot resume from {s.status}.")
    s.status = "Active"
    db.commit()
    return {"success": True, "message": "Resumed."}


@router.post("/focus/{session_id}/finish")
def finish_focus(session_id: UUID, body: FocusNote | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = _get_session(session_id, db, user)
    if not can_transition(s.status, "Completed"):
        raise HTTPException(status_code=409, detail=f"Cannot finish from {s.status}.")
    now = datetime.now(timezone.utc)
    s.ended_at = now
    s.status = "Completed"
    s.actual_minutes = actual_minutes(s.started_at, now)
    if body and body.notes:
        s.notes = body.notes
    task = db.query(Task).filter(Task.id == s.task_id).first()
    if task:
        task.actual_minutes = (task.actual_minutes or 0) + s.actual_minutes
    db.commit()
    log_activity(db, user.id, "focus_session", s.id, "Focus session completed", {"actual_minutes": s.actual_minutes})
    return {"success": True, "data": {"actual_minutes": s.actual_minutes}}


@router.post("/focus/{session_id}/cancel")
def cancel_focus(session_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = _get_session(session_id, db, user)
    s.status = "Cancelled"
    s.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True, "message": "Session cancelled."}


@router.get("/focus/active")
def active_session(db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.query(FocusSession).filter(FocusSession.user_id == user.id, FocusSession.status.in_(["Active", "Paused"])).order_by(FocusSession.started_at.desc()).first()
    if not s:
        return {"success": True, "data": None}
    return {"success": True, "data": {"id": str(s.id), "task_id": str(s.task_id), "status": s.status,
                                      "started_at": s.started_at.isoformat(), "planned_minutes": s.planned_minutes}}


def upsert_workstate(db: Session, user, task_id: UUID, payload: WorkStateUpsert):
    ws = db.query(WorkState).filter(WorkState.task_id == task_id).first()
    data = payload.model_dump()
    if ws:
        for k, v in data.items():
            setattr(ws, k, v)
        ws.last_worked_at = datetime.now(timezone.utc)
    else:
        ws = WorkState(user_id=user.id, task_id=task_id, **data, last_worked_at=datetime.now(timezone.utc))
        db.add(ws)
    db.commit()
    log_activity(db, user.id, "work_state", ws.id, "WorkState updated", {"task_id": str(task_id)})
    return ws


@router.put("/work-states/{task_id}")
def save_workstate(task_id: UUID, payload: WorkStateUpsert, db: Session = Depends(get_db), user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    ws = upsert_workstate(db, user, task_id, payload)
    return {"success": True, "data": {"id": str(ws.id)}}


@router.get("/work-states/recent")
def recent_workstates(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(WorkState).filter(WorkState.user_id == user.id).order_by(WorkState.last_worked_at.desc()).limit(5).all()
    out = []
    for ws in rows:
        task = db.query(Task).filter(Task.id == ws.task_id).first()
        out.append({"task_id": str(ws.task_id), "task_title": task.title if task else "?",
                    "progress_percent": ws.progress_percent, "next_action": ws.next_action,
                    "last_action": ws.last_action, "last_worked_at": ws.last_worked_at.isoformat()})
    return {"success": True, "data": out}

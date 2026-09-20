"""Learning, habits, goals, notes, inbox, distractions (§23-§31)."""
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import (
    Distraction, Event, Goal, GoalMilestone, Habit, HabitLog, InboxItem,
    LearningPath, LearningSession, LearningTopic, Note, Task,
)
from app.schemas.schemas import (
    DistractionCreate, GoalCreate, HabitCreate, InboxConvert, InboxCreate,
    LearningPathCreate, LearningTopicCreate, NoteCreate,
)
from app.services.learning_service import due_for_review, next_review_date

router = APIRouter(tags=["life"])


# ---- learning ----
@router.post("/learning/paths", status_code=201)
def create_path(payload: LearningPathCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = LearningPath(user_id=user.id, **payload.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return {"success": True, "data": {"id": str(p.id)}}


@router.get("/learning/paths")
def list_paths(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(LearningPath).filter(LearningPath.user_id == user.id).all()
    out = []
    for p in rows:
        topics = db.query(LearningTopic).filter(LearningTopic.path_id == p.id).all()
        done = len([t for t in topics if t.status == "Completed"])
        out.append({"id": str(p.id), "title": p.title, "status": p.status,
                    "progress": round(done / len(topics) * 100) if topics else 0,
                    "topics": [{"id": str(t.id), "title": t.title, "status": t.status} for t in topics]})
    return {"success": True, "data": out}


@router.post("/learning/topics", status_code=201)
def create_topic(payload: LearningTopicCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    path = db.query(LearningPath).filter(LearningPath.id == payload.path_id, LearningPath.user_id == user.id).first()
    if not path:
        raise HTTPException(status_code=404, detail="Learning path not found.")
    t = LearningTopic(user_id=user.id, **payload.model_dump())
    db.add(t); db.commit(); db.refresh(t)
    return {"success": True, "data": {"id": str(t.id)}}


@router.post("/learning/topics/{topic_id}/sessions", status_code=201)
def log_learning_session(topic_id: UUID, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id, LearningTopic.user_id == user.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    s = LearningSession(user_id=user.id, topic_id=topic.id,
                        start_time=datetime.now(timezone.utc),
                        duration_minutes=int(body.get("duration_minutes", 25)),
                        session_type=body.get("session_type", "Study"),
                        notes=body.get("notes"), confidence=body.get("confidence"))
    db.add(s); db.commit()
    return {"success": True, "data": {"id": str(s.id)}}


@router.post("/learning/topics/{topic_id}/review")
def review_topic(topic_id: UUID, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id, LearningTopic.user_id == user.id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found.")
    difficult = bool(body.get("difficult", False))
    nxt, stage = next_review_date(date.today(), topic.review_stage or 0, difficult)
    topic.review_stage = stage
    topic.next_review_date = nxt
    if body.get("status"):
        topic.status = body["status"]
    db.commit()
    return {"success": True, "data": {"next_review_date": nxt.isoformat(), "review_stage": stage}}


@router.get("/learning/due")
def learning_due(db: Session = Depends(get_db), user=Depends(get_current_user)):
    topics = db.query(LearningTopic).filter(LearningTopic.user_id == user.id).all()
    dicts = [{"id": str(t.id), "title": t.title, "next_review_date": t.next_review_date} for t in topics]
    return {"success": True, "data": due_for_review(dicts, date.today())}


# ---- habits ----
@router.post("/habits", status_code=201)
def create_habit(payload: HabitCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    h = Habit(user_id=user.id, **payload.model_dump())
    db.add(h); db.commit(); db.refresh(h)
    return {"success": True, "data": {"id": str(h.id)}}


@router.get("/habits")
def list_habits(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Habit).filter(Habit.user_id == user.id, Habit.is_active.is_(True)).all()
    out = []
    for h in rows:
        logs = db.query(HabitLog).filter(HabitLog.habit_id == h.id).order_by(HabitLog.log_date.desc()).limit(14).all()
        out.append({"id": str(h.id), "title": h.title, "frequency": h.frequency,
                    "history": [{"log_date": l.log_date.isoformat(), "completed": l.completed} for l in logs]})
    return {"success": True, "data": out}


@router.post("/habits/{habit_id}/check-in")
def habit_checkin(habit_id: UUID, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    h = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="Habit not found.")
    day = body.get("log_date")
    log_date = date.fromisoformat(day) if day else date.today()
    existing = db.query(HabitLog).filter(HabitLog.habit_id == h.id, HabitLog.log_date == log_date).first()
    if existing:
        existing.completed = bool(body.get("completed", True))
    else:
        db.add(HabitLog(habit_id=h.id, user_id=user.id, log_date=log_date,
                        completed=bool(body.get("completed", True)), notes=body.get("notes")))
    db.commit()
    return {"success": True, "message": "Logged."}


# ---- goals ----
@router.post("/goals", status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    g = Goal(user_id=user.id, **payload.model_dump())
    db.add(g); db.commit(); db.refresh(g)
    return {"success": True, "data": {"id": str(g.id)}}


@router.get("/goals")
def list_goals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Goal).filter(Goal.user_id == user.id).all()
    out = []
    for g in rows:
        ms = db.query(GoalMilestone).filter(GoalMilestone.goal_id == g.id).all()
        out.append({"id": str(g.id), "title": g.title, "status": g.status,
                    "milestones": [{"id": str(m.id), "title": m.title, "status": m.status} for m in ms]})
    return {"success": True, "data": out}


# ---- notes ----
@router.post("/notes", status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    n = Note(user_id=user.id, **payload.model_dump())
    db.add(n); db.commit(); db.refresh(n)
    return {"success": True, "data": {"id": str(n.id)}}


@router.get("/notes")
def list_notes(search: str | None = None, task_id: UUID | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(Note).filter(Note.user_id == user.id).order_by(Note.updated_at.desc())
    if task_id:
        q = q.filter(Note.task_id == task_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Note.title.ilike(like), Note.content.ilike(like)))
    rows = q.limit(100).all()
    return {"success": True, "data": [{"id": str(n.id), "title": n.title, "content": n.content, "tags": n.tags} for n in rows]}


# ---- inbox ----
@router.post("/inbox", status_code=201)
def capture(payload: InboxCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = InboxItem(user_id=user.id, **payload.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"success": True, "data": {"id": str(item.id)}}


@router.get("/inbox")
def list_inbox(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(InboxItem).filter(InboxItem.user_id == user.id, InboxItem.status == "Open").order_by(InboxItem.created_at.desc()).all()
    return {"success": True, "data": [{"id": str(i.id), "title": i.title, "description": i.description} for i in rows]}


@router.post("/inbox/{item_id}/convert")
def convert_inbox(item_id: UUID, payload: InboxConvert, db: Session = Depends(get_db), user=Depends(get_current_user)):
    item = db.query(InboxItem).filter(InboxItem.id == item_id, InboxItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inbox item not found.")
    new_id = None
    if payload.target == "task":
        t = Task(user_id=user.id, title=item.title, description=item.description,
                 status="Planned", priority=payload.priority, category=payload.category)
        db.add(t); db.flush()
        new_id = t.id
    elif payload.target == "note":
        n = Note(user_id=user.id, title=item.title, content=item.description)
        db.add(n); db.flush()
        new_id = n.id
    elif payload.target == "event":
        e = Event(user_id=user.id, title=item.title, description=item.description,
                  start_time=datetime.now(timezone.utc), end_time=datetime.now(timezone.utc))
        db.add(e); db.flush()
        new_id = e.id
    elif payload.target == "learning_topic":
        paths = db.query(LearningPath).filter(LearningPath.user_id == user.id).first()
        if not paths:
            raise HTTPException(status_code=400, detail="Create a learning path first.")
        t = LearningTopic(user_id=user.id, path_id=paths.id, title=item.title, description=item.description)
        db.add(t); db.flush()
        new_id = t.id
    else:  # reminder -> task with due tomorrow
        from datetime import timedelta
        t = Task(user_id=user.id, title=item.title, description=item.description, status="Planned",
                 priority=payload.priority, category=payload.category, due_date=date.today() + timedelta(days=1))
        db.add(t); db.flush()
        new_id = t.id
    item.status = "Converted"
    item.converted_to = payload.target
    item.converted_id = new_id
    db.commit()
    return {"success": True, "data": {"converted_to": payload.target, "id": str(new_id)}}


# ---- distractions ----
@router.post("/distractions", status_code=201)
def log_distraction(payload: DistractionCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = Distraction(user_id=user.id, timestamp=datetime.now(timezone.utc), **payload.model_dump())
    db.add(d); db.commit(); db.refresh(d)
    return {"success": True, "data": {"id": str(d.id)}}


@router.get("/distractions/weekly")
def weekly_distractions(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Distraction).filter(Distraction.user_id == user.id).order_by(Distraction.timestamp.desc()).limit(200).all()
    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r.category] = by_cat.get(r.category, 0) + (r.duration_minutes or 0)
    return {"success": True, "data": {"by_category_minutes": by_cat, "count": len(rows)}}

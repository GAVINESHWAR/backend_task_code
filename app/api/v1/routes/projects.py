"""Projects + milestones (§11, §12)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.models import Project, ProjectMilestone, Task
from app.schemas.schemas import MilestoneCreate, ProjectCreate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
def list_projects(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.query(Project).filter(Project.user_id == user.id).order_by(Project.updated_at.desc()).all()
    out = []
    for p in rows:
        total = db.query(Task).filter(Task.project_id == p.id, Task.deleted_at.is_(None)).count()
        done = db.query(Task).filter(Task.project_id == p.id, Task.status == "Completed").count()
        out.append({"id": str(p.id), "name": p.name, "status": p.status, "priority": p.priority,
                    "category": p.category, "target_date": p.target_date.isoformat() if p.target_date else None,
                    "progress": round(done / total * 100) if total else 0, "task_count": total})
    return {"success": True, "data": out}


@router.post("", status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = Project(user_id=user.id, **payload.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"success": True, "message": "Project created.", "data": {"id": str(p.id), "name": p.name}}


@router.get("/{project_id}")
def get_project(project_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")
    milestones = db.query(ProjectMilestone).filter(ProjectMilestone.project_id == p.id).order_by(ProjectMilestone.sort_order).all()
    tasks = db.query(Task).filter(Task.project_id == p.id, Task.deleted_at.is_(None)).all()
    blocked = [t for t in tasks if t.status == "Waiting"]
    total = len(tasks)
    done = len([t for t in tasks if t.status == "Completed"])
    return {"success": True, "data": {
        "id": str(p.id), "name": p.name, "description": p.description, "status": p.status,
        "priority": p.priority, "category": p.category,
        "progress": round(done / total * 100) if total else 0,
        "milestones": [{"id": str(m.id), "title": m.title, "status": m.status} for m in milestones],
        "tasks": [{"id": str(t.id), "title": t.title, "status": t.status} for t in tasks],
        "blocked_tasks": [{"id": str(t.id), "title": t.title} for t in blocked],
    }}


@router.post("/{project_id}/milestones", status_code=201)
def add_milestone(project_id: UUID, payload: MilestoneCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")
    m = ProjectMilestone(project_id=p.id, **payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"success": True, "data": {"id": str(m.id)}}


@router.patch("/{project_id}")
def update_project(project_id: UUID, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id, Project.user_id == user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Project not found.")
    for k in ("name", "description", "category", "status", "priority", "start_date", "target_date"):
        if k in body:
            setattr(p, k, body[k])
    db.commit()
    return {"success": True, "message": "Project updated."}

from fastapi import APIRouter

from app.api.v1.routes import auth, calendar_planning, focus, life, projects, system, tasks

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(projects.router)
api_router.include_router(focus.router)
api_router.include_router(calendar_planning.router)
api_router.include_router(life.router)
api_router.include_router(system.router)

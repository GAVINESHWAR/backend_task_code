"""FastAPI entrypoint. Auto-runs db/*.sql on startup for deployments."""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers

log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Deployment auto-migration: run idempotent db/*.sql scripts first.
    try:
        from app.core.db_init import run_sql_files
        executed = run_sql_files()
        log.warning("SQL auto-run executed: %s", executed)
    except Exception as exc:  # do not crash boot if DB not yet reachable
        log.warning("SQL auto-run skipped/failed: %s", exc)
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health():
    return {"success": True, "message": "OK", "data": {"app": settings.APP_NAME}}


# Convenience: `python -m app.main` for local dev
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

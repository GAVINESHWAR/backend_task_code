"""Auto-run db/*.sql scripts on deployment / startup.

Behaviour:
- On backend startup (see main.py lifespan) every ``db/*.sql`` file is
  executed in lexicographic order against ``SYNC_DATABASE_URL``.
- Scripts must be idempotent (CREATE TABLE IF NOT EXISTS, etc.) so
  re-running on every deploy is safe.
- The same folder is also mounted into the postgres container at
  ``/docker-entrypoint-initdb.d`` (see docker-compose.yml) so a fresh
  database volume is initialised even before the backend starts.
- Set ``AUTO_RUN_SQL=false`` to disable the backend-side runner
  (e.g. when Alembic migrations own the schema in production).
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings, normalize_psycopg_url

log = logging.getLogger(__name__)


def _db_dir() -> Path:
    # app/core/db_init.py -> backend_task_code/db
    return Path(__file__).resolve().parents[2] / "db"


def list_sql_files() -> list[Path]:
    d = _db_dir()
    if not d.is_dir():
        return []
    return sorted(d.glob("*.sql"))


def run_sql_files(database_url: str | None = None) -> list[str]:
    """Execute all db/*.sql files. Returns list of executed filenames."""
    settings = get_settings()
    if not settings.AUTO_RUN_SQL:
        log.info("AUTO_RUN_SQL=false, skipping SQL auto-run.")
        return []
    url = normalize_psycopg_url(database_url) if database_url else settings.psycopg_url
    files = list_sql_files()
    if not files:
        log.warning("No db/*.sql files found, nothing to run.")
        return []
    try:
        import psycopg
    except ImportError:
        log.warning("psycopg not installed, skipping SQL auto-run.")
        return []

    executed: list[str] = []
    # psycopg3 autocommit is required for CREATE INDEX CONCURRENTLY etc.
    with psycopg.connect(url, autocommit=True) as conn:
        for f in files:
            sql = f.read_text(encoding="utf-8")
            if not sql.strip():
                continue
            log.info("Applying SQL script: %s", f.name)
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
            except Exception as exc:
                # Managed Postgres (Render/RDS/...) may reject e.g.
                # CREATE EXTENSION without superuser. Log and continue so
                # one script never kills the whole deploy boot.
                log.warning("SQL script %s failed, continuing: %s", f.name, exc)
                continue
            executed.append(f.name)
    return executed

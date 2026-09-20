"""SQLAlchemy engine / session.

The engine is created lazily (first DB access), never at import time, so a
missing/unreachable database can never crash ``uvicorn app.main:app`` imports.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    # SQLAlchemy 2.x sync engine (psycopg3). Async variant can be added later
    # without changing repositories (they depend on Session protocol).
    return create_engine(get_settings().sqlalchemy_url, pool_pre_ping=True, future=True)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


# Backwards compat: existing code importing ``engine``/``SessionLocal`` keeps
# working, but nothing is created until first attribute access.
class _LazyEngine:
    def __getattr__(self, name: str):
        return getattr(get_engine(), name)


class _LazySessionFactory:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(get_session_factory(), name)


engine: Engine = _LazyEngine()  # type: ignore[assignment]
SessionLocal = _LazySessionFactory()  # type: ignore[assignment]

"""Generic repository helpers — business logic stays in services."""
from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import Base

M = TypeVar("M", bound=Base)


class Repository(Generic[M]):
    def __init__(self, model: type[M], db: Session):
        self.model = model
        self.db = db

    def get(self, id_: UUID) -> M | None:
        return self.db.get(self.model, id_)

    def list(self, *filters, limit: int = 50, offset: int = 0, order_by=None) -> list[M]:
        q = self.db.query(self.model)
        for f in filters:
            q = q.filter(f)
        if order_by is not None:
            q = q.order_by(order_by)
        return q.limit(limit).offset(offset).all()

    def add(self, obj: M) -> M:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def commit(self) -> None:
        self.db.commit()


def log_activity(db: Session, user_id: UUID, entity_type: str, entity_id, action: str, meta: dict | None = None):
    from app.models.models import ActivityLog

    db.add(ActivityLog(user_id=user_id, entity_type=entity_type, entity_id=entity_id, action=action, meta=meta or {}))
    db.commit()

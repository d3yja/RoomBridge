"""SQLite engine + session helpers."""
from __future__ import annotations

from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from ..config import settings
from . import models  # noqa: F401  (import registers tables on SQLModel.metadata)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(settings.db_url(), connect_args={"check_same_thread": False})
    return _engine


def init_db() -> None:
    SQLModel.metadata.create_all(get_engine())


@contextmanager
def session_scope():
    # expire_on_commit=False: column values loaded during the session stay readable after
    # the session closes, so callers can return ORM rows without DetachedInstanceError.
    with Session(get_engine(), expire_on_commit=False) as session:
        yield session
        session.commit()

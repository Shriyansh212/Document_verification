from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    settings = get_settings()
    db_url = settings.database_url
    connect_args = {}

    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if db_url.startswith("sqlite:///"):
            db_file = Path(db_url.replace("sqlite:///", "", 1))
            if db_file.parent and str(db_file.parent) not in ("", "."):
                db_file.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(db_url, connect_args=connect_args, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)


def init_db() -> None:
    from app.models import document as _document_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

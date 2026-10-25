"""Conexión a SQLite y manejo de sesiones."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import db_path
from app.data.models import Base

_SessionLocal: sessionmaker[Session] | None = None


def init_db(url: str | None = None) -> Engine:
    """Crea el motor, activa las claves foráneas y crea las tablas que falten."""
    global _SessionLocal
    engine = create_engine(url or f"sqlite:///{db_path().as_posix()}")

    @event.listens_for(engine, "connect")
    def _activar_claves_foraneas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    _SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Abre una sesión, hace commit al salir y rollback si hay error."""
    if _SessionLocal is None:
        raise RuntimeError("Llama a init_db() antes de usar la base de datos.")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

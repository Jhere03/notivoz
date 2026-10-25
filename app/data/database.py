"""Conexión a SQLite y manejo de sesiones."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import db_path
from app.data.models import Base

_SessionLocal: sessionmaker[Session] | None = None

# create_all() crea las tablas nuevas, pero no añade columnas a tablas que ya
# existen en la base de datos del usuario. Cada columna agregada después de la
# primera versión se registra aquí: (tabla, columna, definición SQL).
_COLUMNAS_AGREGADAS = [
    ("pendientes", "fecha_realizado", "DATETIME"),
    ("comandos", "procesos", "TEXT NOT NULL DEFAULT ''"),
]


def _migrar(engine: Engine) -> None:
    """Agrega las columnas que falten, sin tocar los datos existentes."""
    inspector = inspect(engine)
    with engine.begin() as conexion:
        for tabla, columna, definicion in _COLUMNAS_AGREGADAS:
            existentes = {c["name"] for c in inspector.get_columns(tabla)}
            if columna not in existentes:
                conexion.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}"))


def init_db(url: str | None = None) -> Engine:
    """Crea el motor, activa las claves foráneas, crea las tablas que falten y
    aplica las migraciones de columnas."""
    global _SessionLocal
    engine = create_engine(url or f"sqlite:///{db_path().as_posix()}")

    @event.listens_for(engine, "connect")
    def _activar_claves_foraneas(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    _migrar(engine)
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

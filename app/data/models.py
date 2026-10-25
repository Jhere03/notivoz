"""Modelos de la base de datos (SQLAlchemy)."""

from datetime import date, datetime
from enum import IntEnum, StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Estado(StrEnum):
    PENDIENTE = "Pendiente"
    EN_PROCESO = "En proceso"
    REALIZADO = "Realizado"


class Importancia(IntEnum):
    BAJA = 1
    MEDIA = 2
    ALTA = 3
    CRITICA = 4

    @property
    def etiqueta(self) -> str:
        return _ETIQUETAS_IMPORTANCIA[self]


_ETIQUETAS_IMPORTANCIA = {
    Importancia.BAJA: "Baja",
    Importancia.MEDIA: "Media",
    Importancia.ALTA: "Alta",
    Importancia.CRITICA: "Crítica",
}


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)

    pendientes: Mapped[list[Pendiente]] = relationship(back_populates="cliente")


class Pendiente(Base):
    __tablename__ = "pendientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL")
    )
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    importancia: Mapped[int] = mapped_column(Integer, default=Importancia.MEDIA)
    fecha_ingreso: Mapped[date] = mapped_column(Date, default=date.today)
    estado: Mapped[str] = mapped_column(String(20), default=Estado.PENDIENTE)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    cliente: Mapped[Cliente | None] = relationship(back_populates="pendientes")


class Nota(Base):
    __tablename__ = "notas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    contenido: Mapped[str] = mapped_column(Text, default="")
    # Fecha y hora local del aviso; None si la nota no tiene recordatorio.
    recordatorio: Mapped[datetime | None] = mapped_column(DateTime)
    notificado: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now
    )


class Ajuste(Base):
    """Preferencias de la app guardadas como clave → valor (JSON)."""

    __tablename__ = "ajustes"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)

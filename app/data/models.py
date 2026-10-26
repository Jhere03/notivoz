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
    # Se fija al pasar a Realizado y se borra si vuelve a otro estado.
    fecha_realizado: Mapped[datetime | None] = mapped_column(DateTime)
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


class Comando(Base):
    """Frase de voz que abre una lista de aplicaciones (por ejemplo «modo trabajo»)."""

    __tablename__ = "comandos"

    id: Mapped[int] = mapped_column(primary_key=True)
    frase: Mapped[str] = mapped_column(String(120), unique=True)
    # Lo que Notivoz dice al terminar de abrir todo; vacío = «<Frase> activado».
    respuesta: Mapped[str] = mapped_column(String(200), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Ejecutables que abrió la última vez (separados por «;»), para poder cerrarlos.
    procesos: Mapped[str] = mapped_column(Text, default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    apps: Mapped[list[ComandoApp]] = relationship(
        back_populates="comando",
        order_by="ComandoApp.orden",
        cascade="all, delete-orphan",
    )


class ComandoApp(Base):
    __tablename__ = "comando_apps"

    id: Mapped[int] = mapped_column(primary_key=True)
    comando_id: Mapped[int] = mapped_column(ForeignKey("comandos.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(120))
    # Ruta a un .exe/.lnk, un enlace (https://, steam://…) o shell:AppsFolder\<id>.
    destino: Mapped[str] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(Integer, default=0)

    comando: Mapped[Comando] = relationship(back_populates="apps")


class AccionRutina(StrEnum):
    EJECUTAR_COMANDO = "ejecutar_comando"
    LEER_PENDIENTES = "leer_pendientes"
    RESUMEN_DIA = "resumen_dia"

    @property
    def etiqueta(self) -> str:
        return {
            "ejecutar_comando": "Ejecutar un comando",
            "leer_pendientes": "Leer mis pendientes",
            "resumen_dia": "Leer el resumen del día",
        }[self]


class Rutina(Base):
    """Algo que Notivoz hace solo, ciertos días a cierta hora."""

    __tablename__ = "rutinas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    accion: Mapped[str] = mapped_column(String(30), default=AccionRutina.LEER_PENDIENTES)
    comando_id: Mapped[int | None] = mapped_column(ForeignKey("comandos.id", ondelete="SET NULL"))
    # Días de la semana separados por comas: 0 = lunes … 6 = domingo.
    dias: Mapped[str] = mapped_column(String(20), default="0,1,2,3,4")
    hora: Mapped[str] = mapped_column(String(5), default="09:00")  # HH:MM
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_ejecucion: Mapped[date | None] = mapped_column(Date)

    comando: Mapped[Comando | None] = relationship()

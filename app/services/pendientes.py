"""Lógica de negocio de los pendientes (tareas)."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import contains_eager

from app.data.database import session_scope
from app.data.models import Cliente, Estado, Importancia, Pendiente


@dataclass
class FiltroPendientes:
    texto: str = ""
    estado: Estado | None = None
    importancia: Importancia | None = None
    cliente_id: int | None = None

    @property
    def activo(self) -> bool:
        return bool(self.texto.strip()) or any(
            v is not None for v in (self.estado, self.importancia, self.cliente_id)
        )


@dataclass
class DatosPendiente:
    titulo: str
    descripcion: str = ""
    cliente_id: int | None = None
    importancia: Importancia = Importancia.MEDIA
    fecha_ingreso: date = field(default_factory=date.today)
    estado: Estado = Estado.PENDIENTE
    id: int | None = None


# Orden por defecto: primero lo activo, luego lo más importante y lo más antiguo.
_ORDEN_ESTADO = case(
    (Pendiente.estado == Estado.EN_PROCESO, 0),
    (Pendiente.estado == Estado.PENDIENTE, 1),
    else_=2,
)


def listar(filtro: FiltroPendientes | None = None) -> list[Pendiente]:
    filtro = filtro or FiltroPendientes()
    stmt = (
        select(Pendiente)
        .outerjoin(Pendiente.cliente)
        .options(contains_eager(Pendiente.cliente))
    )
    if filtro.estado is not None:
        stmt = stmt.where(Pendiente.estado == filtro.estado)
    if filtro.importancia is not None:
        stmt = stmt.where(Pendiente.importancia == filtro.importancia)
    if filtro.cliente_id is not None:
        stmt = stmt.where(Pendiente.cliente_id == filtro.cliente_id)
    texto = filtro.texto.strip()
    if texto:
        like = f"%{texto}%"
        stmt = stmt.where(
            or_(
                Pendiente.titulo.ilike(like),
                Pendiente.descripcion.ilike(like),
                Cliente.nombre.ilike(like),
            )
        )
    stmt = stmt.order_by(
        _ORDEN_ESTADO, Pendiente.importancia.desc(), Pendiente.fecha_ingreso, Pendiente.id
    )
    with session_scope() as s:
        return list(s.scalars(stmt).unique())


def obtener(pendiente_id: int) -> Pendiente | None:
    stmt = (
        select(Pendiente)
        .outerjoin(Pendiente.cliente)
        .options(contains_eager(Pendiente.cliente))
        .where(Pendiente.id == pendiente_id)
    )
    with session_scope() as s:
        return s.scalars(stmt).first()


def guardar(datos: DatosPendiente) -> int:
    """Crea o actualiza un pendiente. Devuelve su id."""
    titulo = datos.titulo.strip()
    if not titulo:
        raise ValueError("El pendiente necesita un título.")
    with session_scope() as s:
        if datos.id is None:
            pendiente = Pendiente()
            s.add(pendiente)
        else:
            pendiente = s.get(Pendiente, datos.id)
            if pendiente is None:
                raise ValueError(f"No existe el pendiente {datos.id}.")
        pendiente.titulo = titulo
        pendiente.descripcion = datos.descripcion.strip()
        cliente = None
        if datos.cliente_id is not None:
            cliente = s.get(Cliente, datos.cliente_id)
            if cliente is None:
                raise ValueError("El cliente elegido ya no existe.")
        pendiente.cliente = cliente
        pendiente.importancia = Importancia(datos.importancia)
        pendiente.fecha_ingreso = datos.fecha_ingreso
        pendiente.estado = Estado(datos.estado)
        s.flush()
        return pendiente.id


def cambiar_estado(pendiente_id: int, estado: Estado) -> None:
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None:
            pendiente.estado = Estado(estado)


def eliminar(pendiente_id: int) -> None:
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None:
            s.delete(pendiente)


def resumen() -> dict[Estado, int]:
    """Cantidad de pendientes por estado."""
    stmt = select(Pendiente.estado, func.count()).group_by(Pendiente.estado)
    conteo = {estado: 0 for estado in Estado}
    with session_scope() as s:
        for estado, total in s.execute(stmt):
            conteo[Estado(estado)] = total
    return conteo

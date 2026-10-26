"""Lógica de negocio de los pendientes (tareas)."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

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
        _aplicar_estado(pendiente, Estado(datos.estado))
        s.flush()
        return pendiente.id


def _aplicar_estado(pendiente: Pendiente, estado: Estado) -> None:
    """Cambia el estado y mantiene la fecha de culminación coherente."""
    if estado == Estado.REALIZADO:
        if pendiente.estado != Estado.REALIZADO or pendiente.fecha_realizado is None:
            pendiente.fecha_realizado = datetime.now()
    else:
        pendiente.fecha_realizado = None
    pendiente.estado = estado


def cambiar_fecha_realizado(pendiente_id: int, momento: datetime) -> None:
    """Corrige cuándo se terminó una tarea realizada."""
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None and pendiente.estado == Estado.REALIZADO:
            pendiente.fecha_realizado = momento


def cambiar_estado(pendiente_id: int, estado: Estado) -> None:
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None:
            _aplicar_estado(pendiente, Estado(estado))


def cambiar_importancia(pendiente_id: int, importancia: Importancia) -> None:
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None:
            pendiente.importancia = Importancia(importancia)


def cambiar_descripcion(pendiente_id: int, descripcion: str) -> None:
    with session_scope() as s:
        pendiente = s.get(Pendiente, pendiente_id)
        if pendiente is not None:
            pendiente.descripcion = descripcion.strip()


# --- Racha, resumen del día y sugerencias --------------------------------------


def racha(hoy: date | None = None) -> int:
    """Días seguidos en los que se terminó al menos una tarea. Si hoy todavía no
    se terminó ninguna, la racha sigue viva contando desde ayer."""
    hoy = hoy or date.today()
    with session_scope() as s:
        fechas = {
            f.date()
            for f in s.scalars(select(Pendiente.fecha_realizado).where(Pendiente.fecha_realizado.is_not(None)))
        }
    dia = hoy if hoy in fechas else hoy - timedelta(days=1)
    dias = 0
    while dia in fechas:
        dias += 1
        dia -= timedelta(days=1)
    return dias


@dataclass
class ResumenDia:
    realizadas: list[str]  # títulos terminados hoy
    en_proceso: int
    pendientes: int
    racha: int


def resumen_del_dia(hoy: date | None = None) -> ResumenDia:
    hoy = hoy or date.today()
    todas = listar()
    return ResumenDia(
        realizadas=[
            p.titulo for p in todas if p.fecha_realizado is not None and p.fecha_realizado.date() == hoy
        ],
        en_proceso=sum(1 for p in todas if p.estado == Estado.EN_PROCESO),
        pendientes=sum(1 for p in todas if p.estado == Estado.PENDIENTE),
        racha=racha(hoy),
    )


DIAS_PARA_SUGERIR = 7


def sugerencias_prioridad(hoy: date | None = None) -> dict[int, Importancia]:
    """Tareas sin terminar que llevan mucho tiempo esperando: id → importancia
    sugerida (un nivel más). Una semana para subir de Baja/Media, dos semanas
    para pasar de Alta a Crítica."""
    hoy = hoy or date.today()
    sugerencias = {}
    for p in listar():
        if p.estado == Estado.REALIZADO or p.importancia >= Importancia.CRITICA:
            continue
        dias = (hoy - p.fecha_ingreso).days
        limite = DIAS_PARA_SUGERIR * (2 if p.importancia == Importancia.ALTA else 1)
        if dias >= limite:
            sugerencias[p.id] = Importancia(p.importancia + 1)
    return sugerencias


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

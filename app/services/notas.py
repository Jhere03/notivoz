"""Lógica de negocio de las notas y sus recordatorios."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import or_, select

from app.data.database import session_scope
from app.data.models import Nota


class FiltroNotas(StrEnum):
    TODAS = "Todas las notas"
    PROXIMAS = "Con recordatorio próximo"
    SIN_RECORDATORIO = "Sin recordatorio"
    AVISADAS = "Ya avisadas"


@dataclass
class DatosNota:
    titulo: str
    contenido: str = ""
    recordatorio: datetime | None = None
    id: int | None = None


def es_proxima(nota: Nota) -> bool:
    return nota.recordatorio is not None and not nota.notificado


def fecha_de(nota: Nota) -> date:
    """Fecha que identifica a la nota: la de su recordatorio o, si no tiene,
    la de creación. Es la que usa el filtro por fecha."""
    return (nota.recordatorio or nota.creado_en).date()


def listar(
    texto: str = "", filtro: FiltroNotas = FiltroNotas.TODAS, fecha: date | None = None
) -> list[Nota]:
    """Notas ordenadas: primero los recordatorios próximos (el más cercano arriba),
    luego las notas sin recordatorio y al final las ya avisadas."""
    stmt = select(Nota)
    texto = texto.strip()
    if texto:
        like = f"%{texto}%"
        stmt = stmt.where(or_(Nota.titulo.ilike(like), Nota.contenido.ilike(like)))
    match filtro:
        case FiltroNotas.PROXIMAS:
            stmt = stmt.where(Nota.recordatorio.is_not(None), Nota.notificado.is_(False))
        case FiltroNotas.SIN_RECORDATORIO:
            stmt = stmt.where(Nota.recordatorio.is_(None))
        case FiltroNotas.AVISADAS:
            stmt = stmt.where(Nota.recordatorio.is_not(None), Nota.notificado.is_(True))
    with session_scope() as s:
        notas = list(s.scalars(stmt))
    if fecha is not None:
        notas = [n for n in notas if fecha_de(n) == fecha]

    def orden(n: Nota):
        if es_proxima(n):
            return (0, n.recordatorio.timestamp())
        if n.recordatorio is None:
            return (1, -n.actualizado_en.timestamp())
        return (2, -n.recordatorio.timestamp())

    return sorted(notas, key=orden)


def obtener(nota_id: int) -> Nota | None:
    with session_scope() as s:
        return s.get(Nota, nota_id)


def guardar(datos: DatosNota) -> int:
    """Crea o actualiza una nota. Devuelve su id."""
    titulo = datos.titulo.strip()
    if not titulo:
        raise ValueError("La nota necesita un título.")
    recordatorio = datos.recordatorio.replace(second=0, microsecond=0) if datos.recordatorio else None
    with session_scope() as s:
        if datos.id is None:
            nota = Nota()
            s.add(nota)
        else:
            nota = s.get(Nota, datos.id)
            if nota is None:
                raise ValueError("La nota ya no existe.")
        # Si el recordatorio cambia, vuelve a quedar pendiente de aviso.
        if recordatorio != nota.recordatorio:
            nota.notificado = False
        nota.titulo = titulo
        nota.contenido = datos.contenido.strip()
        nota.recordatorio = recordatorio
        s.flush()
        return nota.id


def eliminar(nota_id: int) -> None:
    with session_scope() as s:
        nota = s.get(Nota, nota_id)
        if nota is not None:
            s.delete(nota)


def vencidas(ahora: datetime | None = None) -> list[Nota]:
    """Recordatorios cuya hora ya llegó y todavía no se avisaron."""
    ahora = ahora or datetime.now()
    stmt = (
        select(Nota)
        .where(
            Nota.recordatorio.is_not(None),
            Nota.recordatorio <= ahora,
            Nota.notificado.is_(False),
        )
        .order_by(Nota.recordatorio)
    )
    with session_scope() as s:
        return list(s.scalars(stmt))


def marcar_notificada(nota_id: int) -> None:
    with session_scope() as s:
        nota = s.get(Nota, nota_id)
        if nota is not None:
            nota.notificado = True


def posponer(nota_id: int, minutos: int) -> None:
    with session_scope() as s:
        nota = s.get(Nota, nota_id)
        if nota is not None:
            nota.recordatorio = (datetime.now() + timedelta(minutes=minutos)).replace(
                second=0, microsecond=0
            )
            nota.notificado = False

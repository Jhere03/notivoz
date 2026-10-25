"""Lógica de negocio de los clientes."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.data.database import session_scope
from app.data.models import Cliente, Pendiente


def listar() -> list[Cliente]:
    with session_scope() as s:
        return list(s.scalars(select(Cliente).order_by(func.lower(Cliente.nombre))))


def listar_con_total() -> list[tuple[Cliente, int]]:
    """Clientes con la cantidad de tareas que tiene cada uno."""
    stmt = (
        select(Cliente, func.count(Pendiente.id))
        .outerjoin(Pendiente, Pendiente.cliente_id == Cliente.id)
        .group_by(Cliente.id)
        .order_by(func.lower(Cliente.nombre))
    )
    with session_scope() as s:
        return [(cliente, total) for cliente, total in s.execute(stmt)]


def crear(nombre: str) -> int:
    with session_scope() as s:
        cliente = Cliente(nombre=_validar_nombre(s, nombre))
        s.add(cliente)
        s.flush()
        return cliente.id


def renombrar(cliente_id: int, nombre: str) -> None:
    with session_scope() as s:
        cliente = s.get(Cliente, cliente_id)
        if cliente is None:
            raise ValueError("El cliente ya no existe.")
        cliente.nombre = _validar_nombre(s, nombre, excluir_id=cliente_id)


def eliminar(cliente_id: int) -> None:
    """Elimina el cliente. Sus tareas se conservan, pero quedan sin cliente."""
    with session_scope() as s:
        cliente = s.get(Cliente, cliente_id)
        if cliente is not None:
            s.delete(cliente)


def _validar_nombre(s: Session, nombre: str, excluir_id: int | None = None) -> str:
    nombre = " ".join(nombre.split())
    if not nombre:
        raise ValueError("Escribe el nombre del cliente.")
    stmt = select(Cliente.id).where(func.lower(Cliente.nombre) == nombre.lower())
    if excluir_id is not None:
        stmt = stmt.where(Cliente.id != excluir_id)
    if s.scalars(stmt).first() is not None:
        raise ValueError(f"Ya existe un cliente llamado «{nombre}».")
    return nombre

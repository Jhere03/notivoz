"""Textos que Notivoz lee en voz alta: el saludo al iniciar (tareas y
recordatorios de hoy) y el resumen del día."""

from collections import Counter
from collections.abc import Iterable
from datetime import date

from app.data.models import Estado, Pendiente
from app.services import notas, pendientes
from app.services.redaccion import saludo_hora


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def dias_texto(dias: int) -> str:
    return _plural(dias, "día", "días")


def texto_resumen_dia(hoy: date | None = None) -> str:
    """«Hoy cerraste 3 tareas. Tienes 1 en proceso. Te quedan 2 pendientes. Llevas
    una racha de 4 días.» (para rutinas, la bandeja y al apagar la PC)."""
    r = pendientes.resumen_del_dia(hoy)
    partes = []
    if r.realizadas:
        partes.append(f"Hoy cerraste {_plural(len(r.realizadas), 'tarea', 'tareas')}.")
    else:
        partes.append("Hoy no cerraste tareas.")
    if r.en_proceso:
        partes.append(f"Tienes {r.en_proceso} en proceso.")
    if r.pendientes == 1:
        partes.append("Te queda 1 pendiente.")
    elif r.pendientes:
        partes.append(f"Te quedan {r.pendientes} pendientes.")
    else:
        partes.append("No te quedan pendientes.")
    if r.racha > 1:
        partes.append(f"Llevas una racha de {r.racha} días.")
    return " ".join(partes)


def _enumerar(partes: list[str]) -> str:
    """['a', 'b', 'c'] → 'a, b y c'."""
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} y {partes[-1]}"


def _por_cliente(cantidad: str, tareas: list[Pendiente]) -> str:
    """Si todas son del mismo cliente: '2 tareas pendientes de EFE'. Si no:
    '4 tareas pendientes: 2 de EFE, 1 de Acme SAC y 1 sin cliente'."""
    conteo = Counter(p.cliente.nombre if p.cliente else None for p in tareas)
    if len(conteo) == 1:
        cliente = next(iter(conteo))
        return f"{cantidad} de {cliente}" if cliente else f"{cantidad} sin cliente"
    partes = [
        f"{n} de {cliente}" if cliente else f"{n} sin cliente"
        for cliente, n in sorted(conteo.items(), key=lambda c: (-c[1], c[0] or "￿"))
    ]
    return f"{cantidad}: {_enumerar(partes)}"


def texto_conteo_tareas(tareas: Iterable[Pendiente]) -> str:
    """Cuántas tareas hay pendientes y en proceso, y de qué cliente (sin títulos):
    «Tienes 3 tareas pendientes: 2 de EFE y 1 sin cliente. Y 1 en proceso de EFE.»"""
    activas = [p for p in tareas if p.estado != Estado.REALIZADO]
    pendiente = [p for p in activas if p.estado == Estado.PENDIENTE]
    proceso = [p for p in activas if p.estado == Estado.EN_PROCESO]
    partes = []
    if pendiente:
        cantidad = _plural(len(pendiente), "tarea pendiente", "tareas pendientes")
        partes.append(f"Tienes {_por_cliente(cantidad, pendiente)}.")
    if proceso:
        inicio = "Y" if pendiente else "Tienes"
        partes.append(f"{inicio} {_por_cliente(f'{len(proceso)} en proceso', proceso)}.")
    return " ".join(partes) if partes else "No tienes tareas pendientes."


def texto_saludo(nombre: str = "") -> str:
    nombre = nombre.strip()
    partes = [f"{saludo_hora()}, {nombre}." if nombre else f"{saludo_hora()}."]
    partes.append(texto_conteo_tareas(pendientes.listar()))

    hoy = date.today()
    recordatorios = [
        n for n in notas.listar() if notas.es_proxima(n) and n.recordatorio.date() == hoy
    ]
    if recordatorios:
        detalle = "; ".join(
            f"a las {n.recordatorio.strftime('%H:%M')}, {n.titulo.rstrip('.')}" for n in recordatorios
        )
        partes.append(
            f"Hoy tienes {_plural(len(recordatorios), 'recordatorio', 'recordatorios')}: {detalle}."
        )
    return " ".join(partes)

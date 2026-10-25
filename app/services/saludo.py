"""Texto que Notivoz lee en voz alta al iniciar: pendientes y recordatorios de hoy."""

from datetime import date, datetime

from app.data.models import Estado
from app.services import notas, pendientes

_MAX_TAREAS = 5


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def saludo_hora(ahora: datetime | None = None) -> str:
    hora = (ahora or datetime.now()).hour
    if 5 <= hora < 12:
        return "Buenos días"
    if 12 <= hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def texto_saludo(nombre: str = "") -> str:
    nombre = nombre.strip()
    partes = [f"{saludo_hora()}, {nombre}." if nombre else f"{saludo_hora()}."]

    activas = [p for p in pendientes.listar() if p.estado != Estado.REALIZADO]
    if not activas:
        partes.append("No tienes tareas pendientes.")
    else:
        en_pendiente = sum(1 for p in activas if p.estado == Estado.PENDIENTE)
        en_proceso = len(activas) - en_pendiente
        conteo = []
        if en_pendiente:
            conteo.append(_plural(en_pendiente, "tarea pendiente", "tareas pendientes"))
        if en_proceso:
            conteo.append(f"{en_proceso} en proceso")
        partes.append(f"Tienes {' y '.join(conteo)}.")

        titulos = []
        for p in activas[:_MAX_TAREAS]:
            titulo = p.titulo.rstrip(".")
            titulos.append(f"{titulo}, de {p.cliente.nombre}" if p.cliente else titulo)
        partes.append(("Tu tarea es: " if len(activas) == 1 else "Tus tareas: ") + "; ".join(titulos) + ".")
        if len(activas) > _MAX_TAREAS:
            partes.append(f"Y {len(activas) - _MAX_TAREAS} más.")

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

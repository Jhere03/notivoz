"""Textos de fecha y hora para mostrar en la interfaz, y textos que se acomodan."""

import re
from datetime import date, datetime, timedelta

_LARGO_SIN_CORTE = 24
_PALABRA_LARGA = re.compile(rf"\S{{{_LARGO_SIN_CORTE + 1},}}")
_CORTE_INVISIBLE = "\u200b"  # espacio de ancho cero: deja saltar de línea sin verse


def partible(texto: str) -> str:
    """Una «palabra» larguísima sin espacios (un enlace, «dasdasdas…») no deja
    hacer el salto de línea y empuja la ventana: se le marcan puntos de corte
    invisibles para que el texto se acomode al ancho disponible."""
    return _PALABRA_LARGA.sub(
        lambda m: _CORTE_INVISIBLE.join(
            m.group()[i : i + _LARGO_SIN_CORTE] for i in range(0, len(m.group()), _LARGO_SIN_CORTE)
        ),
        texto,
    )

_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def fecha_hora_corta(dt: datetime) -> str:
    """'Hoy 15:30', 'Mañana 09:00', 'Ayer 18:00' o 'sáb 25/10/2026 15:30'."""
    hoy = date.today()
    hora = dt.strftime("%H:%M")
    if dt.date() == hoy:
        return f"Hoy {hora}"
    if dt.date() == hoy + timedelta(days=1):
        return f"Mañana {hora}"
    if dt.date() == hoy - timedelta(days=1):
        return f"Ayer {hora}"
    return f"{_DIAS[dt.weekday()]} {dt.strftime('%d/%m/%Y')} {hora}"


def tiempo_restante(dt: datetime) -> str:
    """'en 15 min', 'en 2 h 5 min', 'en 3 días'…"""
    segundos = (dt - datetime.now()).total_seconds()
    if segundos < 60:
        return "en menos de 1 min"
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"en {minutos} min"
    horas, minutos = divmod(minutos, 60)
    if horas < 24:
        return f"en {horas} h {minutos} min" if minutos else f"en {horas} h"
    dias = horas // 24
    return f"en {dias} día{'s' if dias != 1 else ''}"

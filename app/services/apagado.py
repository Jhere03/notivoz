"""Apagar o reiniciar la PC a una hora, a pedido del usuario.

El plazo lo lleva Notivoz (no Windows): un minuto antes avisa encima de todo
con «Cancelar», y a la hora pide a Windows apagar sin forzar, así los
programas con cambios sin guardar pueden pedir guardar. Si Notivoz se cierra,
el apagado programado se cancela.
"""

import logging
import os
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta

log = logging.getLogger(__name__)

APAGAR, REINICIAR = "apagar", "reiniciar"
ACCIONES = (APAGAR, REINICIAR)
MINIMO = timedelta(minutes=1)  # siempre hay al menos un minuto para cancelar
MAXIMO = timedelta(hours=24)
_SEGUNDOS_PARA_DESPEDIRSE = 3

# Ruta completa: nunca otro «shutdown» que esté en la carpeta actual o el PATH.
_SHUTDOWN = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "shutdown.exe")
_PALABRAS = ("apag", "reinici", "reinic", "shutdown", "cierra windows", "cerrar windows")


@dataclass(frozen=True)
class Programado:
    accion: str
    cuando: datetime
    # Ya lo confirmaste («apágala ahora» → «sí»): sin el aviso de un minuto,
    # apenas Notivoz termina de despedirse.
    confirmado: bool = False


_lock = threading.Lock()
_programado: Programado | None = None


def pidio_apagar(pedido: str) -> bool:
    """¿El usuario pidió apagar o reiniciar con sus palabras?"""
    texto = pedido.lower()
    return any(p in texto for p in _PALABRAS)


def calcular_hora(
    ahora: datetime, en_minutos: int | None = None, a_las: str | None = None, ambigua: bool = False
) -> datetime:
    """Cuándo: «en 5 minutos» o «a las 20:50». Una hora es siempre la próxima vez
    que llega; si no se dijo mañana o noche (`ambigua`), la más cercana de las
    dos (08:50 o 20:50)."""
    if (en_minutos is None) == (a_las is None):
        raise ValueError("Indica en cuántos minutos o a qué hora (solo una de las dos).")
    if en_minutos is not None:
        if not 0 <= en_minutos <= MAXIMO.total_seconds() // 60:
            raise ValueError("El apagado se puede programar hasta 24 horas después.")
        return max(ahora + timedelta(minutes=en_minutos), ahora + MINIMO)
    try:
        hora = time.fromisoformat(a_las.strip())
    except (AttributeError, ValueError):
        raise ValueError("La hora debe ir como HH:MM en 24 horas (por ejemplo 20:50).") from None
    candidatas = [hora]
    if ambigua and hora.hour < 12:
        candidatas.append(hora.replace(hour=hora.hour + 12))
    elif ambigua and hora.hour >= 12:
        candidatas.append(hora.replace(hour=hora.hour - 12))
    proximas = []
    for h in candidatas:
        cuando = ahora.replace(hour=h.hour, minute=h.minute, second=0, microsecond=0)
        if cuando < ahora + MINIMO:
            cuando += timedelta(days=1)
        proximas.append(cuando)
    return min(proximas)


def describir(cuando: datetime, ahora: datetime) -> str:
    """«a las 8:50 de la noche» / «mañana a las 7:15 de la mañana»."""
    h = cuando.hour
    parte = "de la madrugada" if h < 6 else "de la mañana" if h < 12 else "de la tarde" if h < 19 else "de la noche"
    texto = f"a las {h % 12 or 12}:{cuando.minute:02d} {parte}"
    if cuando.date() != ahora.date():
        texto = f"mañana {texto}"
    return texto


def programar(accion: str, cuando: datetime, confirmado: bool = False) -> Programado:
    global _programado
    if accion not in ACCIONES:
        raise ValueError("Solo se puede apagar o reiniciar.")
    with _lock:
        _programado = Programado(accion, cuando, confirmado)
    log.info("%s programado para %s", accion.capitalize(), cuando.strftime("%Y-%m-%d %H:%M"))
    return _programado


def ahora_confirmado(accion: str) -> Programado:
    """«Sí, apágala»: en unos segundos (lo justo para despedirse)."""
    return programar(accion, datetime.now() + timedelta(seconds=_SEGUNDOS_PARA_DESPEDIRSE), confirmado=True)


def cancelar() -> Programado | None:
    """Cancela lo programado. Devuelve lo que había (o None)."""
    global _programado
    with _lock:
        anterior, _programado = _programado, None
    if anterior is not None:
        log.info("Apagado programado cancelado")
    return anterior


def actual() -> Programado | None:
    with _lock:
        return _programado


def ejecutar(accion: str) -> None:
    """Pide a Windows apagar o reiniciar ya, sin forzar el cierre de los programas."""
    bandera = "/s" if accion == APAGAR else "/r"
    log.info("Notivoz va a %s la PC", accion)
    subprocess.run(
        [_SHUTDOWN, bandera, "/t", "0"],
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

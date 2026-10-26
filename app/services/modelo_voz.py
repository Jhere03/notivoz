"""Modelo de reconocimiento de voz en español (Vosk): ubicación y descarga."""

import hashlib
import shutil
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from app.config import data_dir

MODELO = "vosk-model-small-es-0.42"
URL = f"https://alphacephei.com/vosk/models/{MODELO}.zip"
TAMANO_APROX_MB = 39
# Huella del archivo oficial: si lo que llega no coincide, se descarta.
_TAMANO = 39817833
_SHA256 = "09b239888f633ef2f0b4e09736e3d9936acfd810bc65d53fad45261762c6511f"


def carpeta_modelos() -> Path:
    carpeta = data_dir() / "modelos"
    carpeta.mkdir(exist_ok=True)
    return carpeta


def carpeta_modelo() -> Path:
    return carpeta_modelos() / MODELO


def instalado() -> bool:
    carpeta = carpeta_modelo()
    return (carpeta / "am").is_dir() and (carpeta / "conf").is_dir()


def descargar(progreso: Callable[[int, int], None] | None = None) -> None:
    """Descarga y descomprime el modelo. `progreso(bytes_leidos, bytes_totales)`."""
    destino = carpeta_modelos()
    zip_temporal = destino / f"{MODELO}.zip.part"
    try:
        with urllib.request.urlopen(URL, timeout=30) as respuesta, open(zip_temporal, "wb") as archivo:
            total = int(respuesta.headers.get("Content-Length") or 0) or _TAMANO
            leidos = 0
            huella = hashlib.sha256()
            while bloque := respuesta.read(256 * 1024):
                archivo.write(bloque)
                huella.update(bloque)
                leidos += len(bloque)
                if progreso is not None:
                    progreso(leidos, total)
        if leidos != _TAMANO or huella.hexdigest() != _SHA256:
            raise RuntimeError("El modelo descargado no coincide con el original; se descartó.")
        # Si una descarga anterior quedó a medias, empezar limpio.
        shutil.rmtree(carpeta_modelo(), ignore_errors=True)
        with zipfile.ZipFile(zip_temporal) as zip_modelo:
            zip_modelo.extractall(destino)
        if not instalado():
            raise RuntimeError("El archivo descargado no contiene el modelo esperado.")
    finally:
        zip_temporal.unlink(missing_ok=True)

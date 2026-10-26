"""Actualizaciones automáticas desde los Releases de GitHub.

- Al abrir Notivoz y cada pocas horas se consulta el último Release publicado.
- Si es más nuevo, la app ofrece actualizar: descarga el instalador, comprueba
  su huella SHA-256 (publicada junto a él) y lo ejecuta en silencio; el
  instalador reemplaza los archivos de la app (tus datos en %APPDATA% no se
  tocan) y vuelve a abrir Notivoz.

Seguridad: solo se descarga de los Releases de este repositorio, por HTTPS, y
el instalador se descarta si su tamaño o su huella no coinciden.
"""

import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import APP_NAME, APP_VERSION

log = logging.getLogger(__name__)

REPOSITORIO = "Jhere03/notivoz"
_API = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
_DESCARGAS = f"https://github.com/{REPOSITORIO}/releases/download/"
_TIEMPO_MAXIMO = 20
_TAMANO_MAXIMO = 600 * 1024 * 1024  # un instalador nunca debería pesar más


@dataclass
class Version:
    numero: str  # «0.1.1»
    url_instalador: str
    url_huella: str
    tamano: int
    notas: str


def _tupla(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def es_ejecutable() -> bool:
    """True si corre el Notivoz instalado (no el código fuente en desarrollo)."""
    return bool(getattr(sys, "frozen", False))


def _leer_json(url: str) -> dict:
    pedido = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": f"{APP_NAME}/{APP_VERSION}"}
    )
    with urllib.request.urlopen(pedido, timeout=_TIEMPO_MAXIMO) as respuesta:
        return json.loads(respuesta.read(1024 * 1024))


def buscar() -> Version | None:
    """La versión publicada, si es más nueva que la instalada; si no, None."""
    datos = _leer_json(_API)
    numero = str(datos.get("tag_name", "")).lstrip("vV")
    if not numero or _tupla(numero) <= _tupla(APP_VERSION):
        return None
    nombre = f"{APP_NAME}-Setup-{numero}.exe"
    archivos = {a.get("name"): a for a in datos.get("assets", [])}
    instalador, huella = archivos.get(nombre), archivos.get(f"{nombre}.sha256")
    if not instalador or not huella:
        log.warning("El Release %s no tiene el instalador o su huella.", numero)
        return None
    url_instalador = instalador.get("browser_download_url", "")
    url_huella = huella.get("browser_download_url", "")
    # Solo descargas de los Releases de este mismo repositorio.
    if not (url_instalador.startswith(_DESCARGAS) and url_huella.startswith(_DESCARGAS)):
        log.warning("El Release %s apunta a otro sitio: se ignora.", numero)
        return None
    return Version(numero, url_instalador, url_huella, int(instalador.get("size", 0)), datos.get("body") or "")


def descargar(version: Version, progreso: Callable[[int, int], None] | None = None) -> Path:
    """Descarga el instalador y comprueba su huella. Devuelve su ruta."""
    if not 0 < version.tamano <= _TAMANO_MAXIMO:
        raise RuntimeError("El tamaño del instalador no es válido.")
    with urllib.request.urlopen(version.url_huella, timeout=_TIEMPO_MAXIMO) as respuesta:
        esperada = respuesta.read(4096).decode("ascii", "ignore").split()[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", esperada):
        raise RuntimeError("La huella publicada no es válida.")

    carpeta = Path(tempfile.gettempdir()) / f"{APP_NAME}-actualizacion"
    carpeta.mkdir(exist_ok=True)
    destino = carpeta / f"{APP_NAME}-Setup-{version.numero}.exe"
    temporal = destino.with_suffix(".part")
    huella = hashlib.sha256()
    leidos = 0
    with urllib.request.urlopen(version.url_instalador, timeout=_TIEMPO_MAXIMO) as respuesta, open(temporal, "wb") as archivo:
        while bloque := respuesta.read(256 * 1024):
            leidos += len(bloque)
            if leidos > version.tamano:
                break
            archivo.write(bloque)
            huella.update(bloque)
            if progreso is not None:
                progreso(leidos, version.tamano)
    if leidos != version.tamano or huella.hexdigest() != esperada:
        temporal.unlink(missing_ok=True)
        raise RuntimeError("La descarga no coincide con la publicada; se descartó por seguridad.")
    temporal.replace(destino)
    log.info("Actualización %s descargada y verificada.", version.numero)
    return destino


def instalar(instalador: Path) -> None:
    """Lanza el instalador en silencio: cierra Notivoz (quien llama debe salir
    enseguida), reemplaza los archivos y lo vuelve a abrir."""
    subprocess.Popen(
        [str(instalador), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

"""Constantes de la aplicación y rutas de datos."""

import os
import sys
from pathlib import Path

APP_NAME = "Notivoz"
APP_VERSION = "0.1.1"


def ruta_recurso(relativa: str) -> Path:
    """Ruta a un archivo del proyecto (por ejemplo 'assets/logo.png'), tanto en
    desarrollo como dentro del .exe empaquetado (PyInstaller lo descomprime en
    sys._MEIPASS)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relativa


def data_dir() -> Path:
    """Carpeta de datos del usuario: %APPDATA%\\Notivoz.

    Se puede cambiar con la variable de entorno NOTIVOZ_DATA_DIR (útil para pruebas).
    """
    override = os.environ.get("NOTIVOZ_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = Path(os.environ.get("APPDATA", Path.home())) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "notivoz.db"

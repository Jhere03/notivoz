"""Inicio automático con Windows (clave Run del registro del usuario)."""

import sys
import winreg
from pathlib import Path

from app.config import APP_NAME

_RUTA_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
ARG_INICIO = "--inicio"


def comando() -> str:
    """Comando que Windows ejecuta al iniciar sesión."""
    if getattr(sys, "frozen", False):
        # Versión empaquetada (.exe, fase 6).
        return f'"{sys.executable}" {ARG_INICIO}'
    # En desarrollo: pythonw.exe del entorno, para que no se abra una consola.
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    if pythonw.exists():
        python = pythonw
    main = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{python}" "{main}" {ARG_INICIO}'


def esta_activo() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUTA_RUN) as clave:
            winreg.QueryValueEx(clave, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def activar(activo: bool) -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUTA_RUN, 0, winreg.KEY_SET_VALUE
    ) as clave:
        if activo:
            winreg.SetValueEx(clave, APP_NAME, 0, winreg.REG_SZ, comando())
        else:
            try:
                winreg.DeleteValue(clave, APP_NAME)
            except FileNotFoundError:
                pass


def actualizar_ruta() -> None:
    """Si está activo, reescribe el comando por si el proyecto cambió de carpeta."""
    if esta_activo():
        activar(True)

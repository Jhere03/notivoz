"""Abre aplicaciones, archivos y enlaces, y espera a que estén listas."""

import ctypes
import json
import logging
import os
import subprocess
import time
from ctypes import wintypes

log = logging.getLogger(__name__)

_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SEE_MASK_FLAG_NO_UI = 0x00000400
_SW_SHOWNORMAL = 1
_ESPERA_SIN_PROCESO = 2.0  # segundos, para enlaces y apps de la Tienda


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_shell32 = ctypes.windll.shell32
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(_SHELLEXECUTEINFOW)]
_user32.WaitForInputIdle.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def normalizar_destino(destino: str) -> str:
    """'www.youtube.com' o 'youtube.com/x' → 'https://…'. Rutas y otros enlaces, igual."""
    destino = destino.strip()
    es_ruta = (
        os.path.isabs(destino)
        or destino.lower().startswith("shell:")
        or destino.lower().endswith((".exe", ".lnk", ".bat", ".cmd", ".msc"))
    )
    if "://" in destino or es_ruta or "." not in destino.split("/")[0]:
        return destino
    return f"https://{destino}"


def abrir(destino: str) -> int | None:
    """Abre `destino` como si se hiciera doble clic. Devuelve el handle del proceso
    si Windows lo da (programas .exe/.lnk), o None (enlaces, apps de la Tienda)."""
    info = _SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS | _SEE_MASK_FLAG_NO_UI
    # Sin verbo = la acción predeterminada del sistema: las webs se abren en el
    # navegador predeterminado de Windows (algunos navegadores no registran "open").
    info.lpVerb = None
    info.lpFile = normalizar_destino(destino)
    info.nShow = _SW_SHOWNORMAL
    if not _shell32.ShellExecuteExW(ctypes.byref(info)):
        raise OSError(f"Windows no pudo abrir «{destino}» (error {ctypes.GetLastError()}).")
    return info.hProcess or None


def abrir_y_esperar(destinos: list[str], tiempo_maximo: float = 12.0) -> list[str]:
    """Abre todos los destinos y espera a que estén listos para usarse.
    Devuelve los que no se pudieron abrir."""
    procesos: list[int] = []
    fallidos: list[str] = []
    sin_proceso = False
    for destino in destinos:
        try:
            handle = abrir(destino)
        except OSError as error:
            log.warning("%s", error)
            fallidos.append(destino)
            continue
        if handle:
            procesos.append(handle)
        else:
            sin_proceso = True

    # Esperar a que cada app termine de arrancar y acepte interacción. Muchos
    # lanzadores (Steam, Opera GX, Bloc de notas de Windows 11…) abren otro
    # proceso y terminan: si el proceso ya acabó, se da por listo.
    limite = time.monotonic() + tiempo_maximo
    pendientes = list(procesos)
    while pendientes and time.monotonic() < limite:
        for handle in list(pendientes):
            listo = _user32.WaitForInputIdle(handle, 0) == 0
            termino = _kernel32.WaitForSingleObject(handle, 0) == 0
            if listo or termino:
                pendientes.remove(handle)
        if pendientes:
            time.sleep(0.2)
    for handle in procesos:
        _kernel32.CloseHandle(handle)
    if sin_proceso:
        time.sleep(_ESPERA_SIN_PROCESO)
    return fallidos


_apps_instaladas: list[tuple[str, str]] | None = None


def apps_instaladas(recargar: bool = False) -> list[tuple[str, str]]:
    """Apps del menú Inicio (programas normales y de la Tienda): (nombre, destino)."""
    global _apps_instaladas
    if _apps_instaladas is not None and not recargar:
        return _apps_instaladas
    comando = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
    )
    salida = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=30,
    ).stdout
    try:
        datos = json.loads(salida or "[]")
    except ValueError:
        log.warning("No se pudo leer la lista de apps instaladas.")
        datos = []
    if isinstance(datos, dict):
        datos = [datos]
    apps = {
        app["Name"]: f"shell:AppsFolder\\{app['AppID']}"
        for app in datos
        if app.get("Name") and app.get("AppID")
    }
    _apps_instaladas = sorted(apps.items(), key=lambda a: a[0].lower())
    return _apps_instaladas

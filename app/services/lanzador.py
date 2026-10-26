"""Abre aplicaciones, archivos y enlaces, y espera a que estén listas."""

import ctypes
import json
import logging
import os
import subprocess
import time
from ctypes import wintypes
from dataclasses import dataclass, field

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


@dataclass
class ResultadoApertura:
    fallidos: list[str] = field(default_factory=list)
    # Ejecutables que aparecieron al abrir (en minúsculas), para poder cerrarlos luego.
    procesos_nuevos: set[str] = field(default_factory=set)


def _es_web(destino: str) -> bool:
    return normalizar_destino(destino).lower().startswith(("http://", "https://"))


def abrir_y_esperar(destinos: list[str], tiempo_maximo: float = 12.0) -> ResultadoApertura:
    """Abre todos los destinos, espera a que estén listos para usarse y anota qué
    procesos nuevos aparecieron. Las webs se abren al final y no se anotan: se
    abren en el navegador que ya podía estar en uso."""
    resultado = ResultadoApertura()
    programas = [d for d in destinos if not _es_web(d)]
    webs = [d for d in destinos if _es_web(d)]

    antes = procesos_en_ejecucion()
    procesos: list[int] = []
    sin_proceso = False
    for destino in programas:
        try:
            handle = abrir(destino)
        except OSError as error:
            log.warning("%s", error)
            resultado.fallidos.append(destino)
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

    despues = procesos_en_ejecucion()
    resultado.procesos_nuevos = {
        nombre for pid, nombre in despues.items() if pid not in antes and nombre not in _NO_CERRAR
    }

    for destino in webs:
        try:
            abrir(destino)
        except OSError as error:
            log.warning("%s", error)
            resultado.fallidos.append(destino)
    return resultado


# --- Procesos ---------------------------------------------------------------------

# Procesos de Windows (o de Notivoz) que pueden aparecer al abrir algo, pero que
# nunca se deben cerrar.
_NO_CERRAR = {
    "explorer.exe", "conhost.exe", "runtimebroker.exe", "svchost.exe", "backgroundtaskhost.exe",
    "werfault.exe", "searchprotocolhost.exe", "searchfilterhost.exe", "dllhost.exe", "sihost.exe",
    "taskhostw.exe", "applicationframehost.exe", "textinputhost.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "searchhost.exe", "python.exe", "pythonw.exe", "notivoz.exe",
    "smartscreen.exe", "consent.exe", "audiodg.exe", "ctfmon.exe", "wmiprvse.exe", "msiexec.exe",
    "mousocoreworker.exe", "compattelrunner.exe", "securityhealthsystray.exe", "cmd.exe",
    "powershell.exe", "openwith.exe", "crashpad_handler.exe", "wudfhost.exe", "useroobebroker.exe",
}  # fmt: skip

_TH32CS_SNAPPROCESS = 0x00000002


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


_kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]


def procesos_en_ejecucion() -> dict[int, str]:
    """pid → nombre del ejecutable en minúsculas ('steam.exe')."""
    procesos: dict[int, str] = {}
    captura = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not captura or captura == wintypes.HANDLE(-1).value:
        return procesos
    try:
        entrada = _PROCESSENTRY32W()
        entrada.dwSize = ctypes.sizeof(entrada)
        hay = _kernel32.Process32FirstW(captura, ctypes.byref(entrada))
        while hay:
            procesos[entrada.th32ProcessID] = entrada.szExeFile.lower()
            hay = _kernel32.Process32NextW(captura, ctypes.byref(entrada))
    finally:
        _kernel32.CloseHandle(captura)
    return procesos


def cerrar_procesos(nombres: set[str]) -> int:
    """Pide cerrarse a los programas (como al pulsar la X; nunca se fuerza, así no
    se pierde trabajo sin guardar). Devuelve cuántos estaban abiertos."""
    abiertos = set(procesos_en_ejecucion().values())
    cerrados = 0
    for nombre in sorted(nombres - _NO_CERRAR):
        if nombre not in abiertos:
            continue
        subprocess.run(
            ["taskkill", "/IM", nombre, "/T"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=15,
        )
        cerrados += 1
    return cerrados


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


_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
]  # fmt: skip


def proceso_en_primer_plano() -> str | None:
    """Ejecutable de la ventana que el usuario está usando ('steam.exe'), o None."""
    ventana = _user32.GetForegroundWindow()
    if not ventana:
        return None
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(ventana, ctypes.byref(pid))
    proceso = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not proceso:
        return None
    try:
        largo = wintypes.DWORD(1024)
        ruta = ctypes.create_unicode_buffer(largo.value)
        if not _kernel32.QueryFullProcessImageNameW(proceso, 0, ruta, ctypes.byref(largo)):
            return None
        return os.path.basename(ruta.value).lower()
    finally:
        _kernel32.CloseHandle(proceso)


def apps_con_ventana() -> list[str]:
    """Ejecutables que tienen alguna ventana visible ahora (para elegir apps de ocio)."""
    nombres: set[str] = set()
    procesos = procesos_en_ejecucion()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visitar(ventana, _):
        if _user32.IsWindowVisible(ventana) and _user32.GetWindowTextLengthW(ventana) > 0:
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(ventana, ctypes.byref(pid))
            nombre = procesos.get(pid.value)
            if nombre and nombre not in _NO_CERRAR:
                nombres.add(nombre)
        return True

    _user32.EnumWindows(visitar, 0)
    return sorted(nombres)

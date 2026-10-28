"""Tecla para hablar: en vez de presionar la burbuja, pulsar una tecla (una vez).

La tecla solo se toma mientras la burbuja está a la vista (tras decir «Notivoz»,
procesando o respondiendo): el resto del tiempo sigue escribiendo normalmente en
cualquier aplicación.
"""

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QPushButton

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
_ID_ATAJO = 0x4E56  # cualquier número fijo de esta app
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x4000
_SOLO_MODIFICADORES = {
    Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
    Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock,
}  # fmt: skip
# Teclas que no se pueden asignar (del sistema o para cancelar).
_RESERVADAS = {Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace}

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None


def registrar(ventana: int, tecla: dict | None) -> bool:
    """Toma la tecla para la ventana de la burbuja (llega como WM_HOTKEY)."""
    if _user32 is None or not tecla:
        return False
    try:
        vk, mods = int(tecla["vk"]), int(tecla["mods"]) & (_MOD_ALT | _MOD_CONTROL | _MOD_SHIFT)
    except (KeyError, TypeError, ValueError):
        return False  # ajuste dañado: como si no hubiera tecla
    if not 0 < vk < 256:
        return False
    ok = bool(_user32.RegisterHotKey(wintypes.HWND(ventana), _ID_ATAJO, mods | _MOD_NOREPEAT, vk))
    if not ok:
        log.info("No se pudo usar la tecla %s (¿la usa otra aplicación?)", tecla.get("nombre"))
    return ok


def liberar(ventana: int) -> None:
    if _user32 is not None:
        _user32.UnregisterHotKey(wintypes.HWND(ventana), _ID_ATAJO)


def es_la_tecla(mensaje) -> bool:
    """¿Este mensaje de Windows es la tecla para hablar?"""
    msg = wintypes.MSG.from_address(int(mensaje))
    return msg.message == WM_HOTKEY and msg.wParam == _ID_ATAJO


class BotonTecla(QPushButton):
    """Muestra la tecla asignada; al presionarlo, la siguiente tecla que pulses
    queda asignada (Esc cancela)."""

    cambiada = Signal(object)  # dict {"vk", "mods", "nombre"} o None

    def __init__(self, tecla: dict | None, parent=None):
        super().__init__(parent)
        self._tecla = tecla
        self._esperando = False
        self.setObjectName("Secundario")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._esperar)
        self._mostrar()

    def quitar(self) -> None:
        self._tecla = None
        self._esperando = False
        self._mostrar()
        self.cambiada.emit(None)

    def _esperar(self) -> None:
        self._esperando = True
        self.setText("Pulsa una tecla…  (Esc para cancelar)")
        self.grabKeyboard()

    def _mostrar(self) -> None:
        self.setText(f"Tecla: {self._tecla['nombre']}" if self._tecla else "Sin asignar: presiona para elegir")

    def event(self, evento) -> bool:
        if self._esperando and evento.type() == QEvent.Type.KeyPress:
            self._al_pulsar(evento)
            return True
        if self._esperando and evento.type() == QEvent.Type.FocusOut:
            self._terminar()
        return super().event(evento)

    def _al_pulsar(self, evento) -> None:
        tecla = Qt.Key(evento.key())
        if tecla in _SOLO_MODIFICADORES:
            return  # esperar la tecla de verdad (por ejemplo Ctrl + Espacio)
        if tecla in _RESERVADAS or not evento.nativeVirtualKey():
            self._terminar()
            return
        modificadores = evento.modifiers()
        mods = 0
        if modificadores & Qt.KeyboardModifier.ControlModifier:
            mods |= _MOD_CONTROL
        if modificadores & Qt.KeyboardModifier.AltModifier:
            mods |= _MOD_ALT
        if modificadores & Qt.KeyboardModifier.ShiftModifier:
            mods |= _MOD_SHIFT
        nombre = QKeySequence(evento.keyCombination()).toString(QKeySequence.SequenceFormat.NativeText)
        self._tecla = {"vk": int(evento.nativeVirtualKey()), "mods": mods, "nombre": nombre.upper() if len(nombre) == 1 else nombre}
        self._terminar()
        self.cambiada.emit(self._tecla)

    def _terminar(self) -> None:
        self._esperando = False
        self.releaseKeyboard()
        self._mostrar()

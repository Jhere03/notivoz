"""Aplica el tema elegido a toda la app: hoja de estilos, barra de título y
efecto acrílico de Windows 11 (tema translúcido), y anima la aparición de los
diálogos."""

import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from app.ui import theme

log = logging.getLogger(__name__)

# DwmSetWindowAttribute
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMSBT_NINGUNO = 1
_DWMSBT_ACRILICO = 3  # "transient window": deja ver, desenfocado, lo que hay detrás
_BUILD_ACRILICO = 22621  # Windows 11 22H2


class _MARGINS(ctypes.Structure):
    _fields_ = [("izq", ctypes.c_int), ("der", ctypes.c_int), ("arr", ctypes.c_int), ("aba", ctypes.c_int)]


def acrilico_disponible() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= _BUILD_ACRILICO


def _aplicar_dwm(ventana: QWidget, oscura: bool, acrilico: bool) -> None:
    """Barra de título clara u oscura y fondo acrílico (o ninguno)."""
    if sys.platform != "win32":
        return
    try:
        dwm = ctypes.windll.dwmapi
        hwnd = wintypes.HWND(int(ventana.winId()))
        valor = ctypes.c_int(1 if oscura else 0)
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(valor), 4)
        if not acrilico_disponible():
            return
        fondo = ctypes.c_int(_DWMSBT_ACRILICO if acrilico else _DWMSBT_NINGUNO)
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(fondo), 4)
        # El acrílico solo se ve en la parte del marco: se extiende a toda la ventana.
        margen = _MARGINS(-1, -1, -1, -1) if acrilico else _MARGINS(0, 0, 0, 0)
        dwm.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margen))
    except (OSError, AttributeError):
        log.debug("No se pudo aplicar el efecto de ventana", exc_info=True)


def _es_ventana_tematizable(widget: QObject) -> bool:
    return isinstance(widget, (QMainWindow, QDialog)) and widget.isWindow()


class _Apariencia(QObject):
    """Filtro global: cada ventana o diálogo que se muestra recibe el tema y,
    los diálogos, una pequeña animación de entrada."""

    tema_cambiado = Signal(str)

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app
        self._animaciones: dict[QWidget, QPropertyAnimation] = {}
        app.installEventFilter(self)

    @property
    def translucido(self) -> bool:
        return theme.tema_actual == theme.TRANSLUCIDO and acrilico_disponible()

    def aplicar(self, nombre: str) -> None:
        if nombre == theme.TRANSLUCIDO and not acrilico_disponible():
            nombre = theme.OSCURO  # sin acrílico (Windows 10) se vería mal
        theme._activar(nombre)
        self._app.setStyleSheet(theme.QSS)
        for ventana in self._app.topLevelWidgets():
            if _es_ventana_tematizable(ventana) and ventana.isVisible():
                _aplicar_dwm(ventana, theme.es_oscuro(), self.translucido)
        self.tema_cambiado.emit(theme.tema_actual)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        tipo = event.type()
        if tipo == QEvent.Type.Polish and isinstance(obj, QDialog) and obj.isWindow():
            # Debe ponerse antes de que el diálogo aparezca para que el fondo
            # pueda ser semitransparente.
            obj.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, self.translucido)
        elif tipo == QEvent.Type.Show and _es_ventana_tematizable(obj):
            _aplicar_dwm(obj, theme.es_oscuro(), self.translucido)
            if isinstance(obj, QDialog):
                self._animar_entrada(obj)
        return False

    def _animar_entrada(self, dialogo: QDialog) -> None:
        """Aparece con un fundido corto."""
        if dialogo in self._animaciones:
            return
        animacion = QPropertyAnimation(dialogo, b"windowOpacity", self)
        animacion.setDuration(170)
        animacion.setStartValue(0.0)
        animacion.setEndValue(1.0)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.finished.connect(lambda: self._animaciones.pop(dialogo, None))
        dialogo.destroyed.connect(lambda: self._animaciones.pop(dialogo, None))
        self._animaciones[dialogo] = animacion
        dialogo.setWindowOpacity(0.0)
        animacion.start()


_instancia: _Apariencia | None = None


def instalar(app: QApplication, nombre: str) -> "_Apariencia":
    """Llamar una vez, con la QApplication creada, antes de mostrar ventanas."""
    global _instancia
    _instancia = _Apariencia(app)
    _instancia.aplicar(nombre)
    return _instancia


def apariencia() -> _Apariencia:
    assert _instancia is not None, "Llama a apariencia.instalar() al iniciar la app"
    return _instancia


def preparar_ventana_principal(ventana: QMainWindow) -> None:
    """La ventana principal se crea siempre capaz de transparencia, así el tema
    translúcido se puede activar y desactivar sin reiniciar."""
    ventana.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

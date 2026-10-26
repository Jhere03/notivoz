"""Avisos flotantes breves ("Tarea guardada", "Nota eliminada"…) en la parte
inferior de la ventana principal."""

from enum import Enum

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

_VISIBLE_MS = 2200
_ENTRADA_MS = 220
_SALIDA_MS = 260
_MARGEN_INFERIOR = 26
_SUBIDA = 14  # px que sube el aviso al aparecer


class Tipo(Enum):
    EXITO = ("✓", "#34d399")
    ELIMINADO = ("🗑", "#f87171")
    INFO = ("ℹ", "#a996ff")


class _Aviso(QFrame):
    def __init__(self, anfitrion: QWidget, texto: str, tipo: Tipo):
        super().__init__(anfitrion)
        self.setObjectName("Aviso")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        simbolo, color = tipo.value
        icono = QLabel(simbolo)
        icono.setObjectName("AvisoIcono")
        icono.setStyleSheet(f"color: {color};")
        mensaje = QLabel(texto)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 20, 10)
        layout.setSpacing(10)
        layout.addWidget(icono)
        layout.addWidget(mensaje)
        self.adjustSize()

        # Un widget admite un solo efecto: fundido al entrar y salir, y sombra
        # mientras está quieto.
        self._opacidad = QGraphicsOpacityEffect(self)
        self._opacidad.setOpacity(0.0)
        self.setGraphicsEffect(self._opacidad)
        self._grupo: QParallelAnimationGroup | None = None

    def posicion_final(self) -> QPoint:
        anfitrion = self.parentWidget()
        x = (anfitrion.width() - self.width()) // 2
        y = anfitrion.height() - self.height() - _MARGEN_INFERIOR
        return QPoint(x, y)

    def entrar(self) -> None:
        final = self.posicion_final()
        self.move(final + QPoint(0, _SUBIDA))
        self.show()
        self.raise_()
        self._animar(final + QPoint(0, _SUBIDA), final, 0.0, 1.0, _ENTRADA_MS, self._al_entrar)

    def _al_entrar(self) -> None:
        # Ya visible del todo: cambiar el fundido por una sombra suave.
        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(24)
        sombra.setOffset(0, 4)
        sombra.setColor(QColor(0, 0, 0, 110))
        self.setGraphicsEffect(sombra)
        QTimer.singleShot(_VISIBLE_MS, self.salir)

    def salir(self) -> None:
        if self._grupo is not None and self._grupo.property("salida"):
            return
        if self._grupo is not None:
            self._grupo.stop()
        self._opacidad = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacidad)
        actual = self.pos()
        self._animar(actual, actual + QPoint(0, _SUBIDA // 2), 1.0, 0.0, _SALIDA_MS, self.deleteLater)
        self._grupo.setProperty("salida", True)

    def _animar(self, desde: QPoint, hasta: QPoint, op_desde: float, op_hasta: float, ms: int, fin) -> None:
        grupo = QParallelAnimationGroup(self)
        movimiento = QPropertyAnimation(self, b"pos")
        movimiento.setStartValue(desde)
        movimiento.setEndValue(hasta)
        opacidad = QPropertyAnimation(self._opacidad, b"opacity")
        opacidad.setStartValue(op_desde)
        opacidad.setEndValue(op_hasta)
        for animacion in (movimiento, opacidad):
            animacion.setDuration(ms)
            animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
            grupo.addAnimation(animacion)
        grupo.finished.connect(fin)
        self._grupo = grupo
        grupo.start()


class _Anfitrion(QObject):
    """Muestra los avisos sobre un widget y los recoloca si este cambia de tamaño."""

    def __init__(self, widget: QWidget):
        super().__init__(widget)
        self._widget = widget
        self._actual: _Aviso | None = None
        widget.installEventFilter(self)

    def mostrar(self, texto: str, tipo: Tipo) -> None:
        if self._actual is not None:
            try:
                self._actual.salir()
            except RuntimeError:  # ya se borró
                pass
        aviso = _Aviso(self._widget, texto, tipo)
        aviso.destroyed.connect(lambda: self._olvidar(aviso))
        self._actual = aviso
        aviso.entrar()

    def _olvidar(self, aviso: _Aviso) -> None:
        if self._actual is aviso:
            self._actual = None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Resize and self._actual is not None:
            try:
                self._actual.move(self._actual.posicion_final())
            except RuntimeError:
                self._actual = None
        return False


_anfitrion: _Anfitrion | None = None


def registrar(widget: QWidget) -> None:
    """Widget sobre el que aparecerán los avisos (el central de la ventana)."""
    global _anfitrion
    _anfitrion = _Anfitrion(widget)


def avisar(texto: str, tipo: Tipo = Tipo.EXITO) -> None:
    if _anfitrion is not None:
        _anfitrion.mostrar(texto, tipo)

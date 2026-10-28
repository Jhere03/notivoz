"""Animaciones reutilizables: cambio de vista, aparición y desaparición de widgets."""

from collections.abc import Callable

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QStackedWidget, QWidget

_DURACION_VISTA = 220
_DESPLAZAMIENTO_VISTA = 18  # px que recorre la vista nueva al entrar


def _efecto_opacidad(widget: QWidget, inicial: float) -> QGraphicsOpacityEffect:
    efecto = QGraphicsOpacityEffect(widget)
    efecto.setOpacity(inicial)
    widget.setGraphicsEffect(efecto)
    return efecto


def _animacion_opacidad(efecto, desde: float, hasta: float, ms: int) -> QPropertyAnimation:
    animacion = QPropertyAnimation(efecto, b"opacity", efecto)
    animacion.setDuration(ms)
    animacion.setStartValue(desde)
    animacion.setEndValue(hasta)
    animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
    return animacion


def aparecer(widget: QWidget, ms: int = 200) -> None:
    """Fundido de entrada. Al terminar se quita el efecto (pintar con él es más lento)."""
    efecto = _efecto_opacidad(widget, 0.0)
    animacion = _animacion_opacidad(efecto, 0.0, 1.0, ms)
    animacion.finished.connect(lambda: widget.setGraphicsEffect(None))
    animacion.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def desvanecer(widget: QWidget, al_terminar: Callable[[], None], ms: int = 180) -> None:
    """Fundido de salida y después `al_terminar` (por ejemplo, borrar y recargar)."""
    if not widget.isVisible():
        al_terminar()
        return
    efecto = _efecto_opacidad(widget, 1.0)
    animacion = _animacion_opacidad(efecto, 1.0, 0.0, ms)
    # Salida que frena (no que arranca lento): se siente inmediata.
    animacion.setEasingCurve(QEasingCurve.Type.OutQuad)
    animacion.finished.connect(al_terminar)
    animacion.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


class PilaAnimada(QStackedWidget):
    """QStackedWidget cuya vista nueva entra con un fundido y un leve deslizamiento."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._grupo: QParallelAnimationGroup | None = None
        self.animar = True

    def setCurrentIndex(self, indice: int) -> None:
        if indice == self.currentIndex() or not self.animar or not self.isVisible():
            super().setCurrentIndex(indice)
            return
        self._terminar_animacion()
        super().setCurrentIndex(indice)
        vista = self.currentWidget()
        if vista is None:
            return
        destino = vista.pos()
        efecto = _efecto_opacidad(vista, 0.0)
        opacidad = _animacion_opacidad(efecto, 0.0, 1.0, _DURACION_VISTA)
        movimiento = QPropertyAnimation(vista, b"pos")
        movimiento.setDuration(_DURACION_VISTA)
        movimiento.setStartValue(destino + QPoint(0, _DESPLAZAMIENTO_VISTA))
        movimiento.setEndValue(destino)
        movimiento.setEasingCurve(QEasingCurve.Type.OutCubic)

        grupo = QParallelAnimationGroup(self)
        grupo.addAnimation(opacidad)
        grupo.addAnimation(movimiento)
        grupo.finished.connect(lambda: self._al_terminar(vista, destino))
        self._grupo = grupo
        grupo.start()

    def _al_terminar(self, vista: QWidget, destino: QPoint) -> None:
        vista.setGraphicsEffect(None)
        vista.move(destino)
        self._grupo = None

    def _terminar_animacion(self) -> None:
        """Si se cambia de vista a mitad de una animación, se salta al final."""
        if self._grupo is not None:
            grupo = self._grupo
            grupo.setCurrentTime(grupo.totalDuration())
            grupo.stop()
            if self._grupo is grupo:
                # stop() no emite finished: limpiar a mano.
                for vista in (self.widget(i) for i in range(self.count())):
                    if vista.graphicsEffect() is not None:
                        vista.setGraphicsEffect(None)
                self._grupo = None

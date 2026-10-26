"""Iconos de línea del menú lateral, dibujados por código (mismo estilo entre sí).

Cada icono tiene dos versiones: gris en reposo y blanca cuando el módulo está
seleccionado.
"""

import math
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from app.ui import theme

_LIENZO = 48  # se dibuja grande y Qt lo reduce: queda nítido
_GROSOR = 3.4


def _pendientes(p: QPainter) -> None:
    for i, y in enumerate((12, 24, 36)):
        # ✓ pequeño y una línea, como una lista de tareas.
        p.drawPolyline([QPointF(6, y), QPointF(9.5, y + 3.5), QPointF(16, y - 3)])
        p.drawLine(QPointF(22, y), QPointF(42, y))


def _notas(p: QPainter) -> None:
    hoja = QPainterPath()
    hoja.moveTo(10, 5)
    hoja.lineTo(30, 5)
    hoja.lineTo(39, 14)
    hoja.lineTo(39, 43)
    hoja.lineTo(10, 43)
    hoja.closeSubpath()
    p.drawPath(hoja)
    p.drawPolyline([QPointF(30, 5), QPointF(30, 14), QPointF(39, 14)])
    for y in (22, 29, 36):
        p.drawLine(QPointF(16, y), QPointF(33, y))


def _microfono(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(17, 4, 14, 24), 7, 7)
    p.drawArc(QRectF(10, 13, 28, 24), 200 * 16, 140 * 16)
    p.drawLine(QPointF(24, 37), QPointF(24, 44))
    p.drawLine(QPointF(16, 44), QPointF(32, 44))


def _reloj(p: QPainter) -> None:
    p.drawEllipse(QPointF(24, 25), 18, 18)
    p.drawPolyline([QPointF(24, 13), QPointF(24, 25), QPointF(32, 30)])


def _engranaje(p: QPainter) -> None:
    centro = QPointF(24, 24)
    dientes = 8
    contorno = QPainterPath()
    for i in range(dientes * 4):
        # Alterna radio exterior (diente) e interior (hueco).
        angulo = math.radians(i * 360 / (dientes * 4) - 90)
        radio = 20 if (i % 4) in (0, 1) else 15
        punto = QPointF(centro.x() + radio * math.cos(angulo), centro.y() + radio * math.sin(angulo))
        if i == 0:
            contorno.moveTo(punto)
        else:
            contorno.lineTo(punto)
    contorno.closeSubpath()
    p.drawPath(contorno)
    p.drawEllipse(centro, 6, 6)


def _chat(p: QPainter) -> None:
    globo = QPainterPath()
    globo.addRoundedRect(QRectF(5, 7, 38, 26), 9, 9)
    p.drawPath(globo)
    p.drawPolyline([QPointF(14, 33), QPointF(12, 42), QPointF(23, 33)])
    for x in (16, 24, 32):
        p.drawPoint(QPointF(x, 20))


ICONOS: dict[str, Callable[[QPainter], None]] = {
    "pendientes": _pendientes,
    "notas": _notas,
    "comandos": _microfono,
    "rutinas": _reloj,
    "chat": _chat,
    "configuracion": _engranaje,
}


def _dibujar(dibujo: Callable[[QPainter], None], color: str) -> QPixmap:
    pixmap = QPixmap(_LIENZO, _LIENZO)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    lapiz = QPen(QColor(color), _GROSOR)
    lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
    lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(lapiz)
    p.setBrush(Qt.BrushStyle.NoBrush)
    dibujo(p)
    p.end()
    return pixmap


def icono_menu(nombre: str) -> QIcon:
    dibujo = ICONOS[nombre]
    icono = QIcon()
    icono.addPixmap(_dibujar(dibujo, theme.TEXTO_SUAVE), QIcon.Mode.Normal)
    icono.addPixmap(_dibujar(dibujo, "#ffffff"), QIcon.Mode.Selected)
    return icono

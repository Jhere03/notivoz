"""Iconos de línea dibujados por código, todos con el mismo trazo: los del menú
lateral (gris en reposo, blanco al seleccionar), los de los botones (siguen al
tema) y los glifos de la hoja de estilos (casillas y listas desplegables).
"""

import math
import weakref
from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QAbstractButton

from app.config import data_dir
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


# --- Iconos de botones (mismo trazo que el menú) ---


def _mas(p: QPainter) -> None:
    p.drawLine(QPointF(24, 9), QPointF(24, 39))
    p.drawLine(QPointF(9, 24), QPointF(39, 24))


def _play(p: QPainter) -> None:
    triangulo = QPainterPath()
    triangulo.moveTo(15, 9)
    triangulo.lineTo(38, 24)
    triangulo.lineTo(15, 39)
    triangulo.closeSubpath()
    p.drawPath(triangulo)


def _stop(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(11, 11, 26, 26), 5, 5)


def _lapiz(p: QPainter) -> None:
    cuerpo = QPainterPath()
    cuerpo.moveTo(31, 8)
    cuerpo.lineTo(40, 17)
    cuerpo.lineTo(17, 40)
    cuerpo.lineTo(7, 41)
    cuerpo.lineTo(8, 31)
    cuerpo.closeSubpath()
    p.drawPath(cuerpo)
    p.drawLine(QPointF(26, 13), QPointF(35, 22))


def _refrescar(p: QPainter) -> None:
    p.drawArc(QRectF(9, 9, 30, 30), 30 * 16, 290 * 16)
    p.drawPolyline([QPointF(38, 6), QPointF(37.5, 16.5), QPointF(27, 15)])


def _cerrar(p: QPainter) -> None:
    p.drawLine(QPointF(12, 12), QPointF(36, 36))
    p.drawLine(QPointF(36, 12), QPointF(12, 36))


def _campana(p: QPainter) -> None:
    cuerpo = QPainterPath()
    cuerpo.moveTo(9, 35)
    cuerpo.cubicTo(13, 31, 13, 26, 13, 21)
    cuerpo.cubicTo(13, 12, 18, 8, 24, 8)
    cuerpo.cubicTo(30, 8, 35, 12, 35, 21)
    cuerpo.cubicTo(35, 26, 35, 31, 39, 35)
    cuerpo.closeSubpath()
    p.drawPath(cuerpo)
    p.drawArc(QRectF(19, 35, 10, 8), 180 * 16, 180 * 16)


def _check(p: QPainter) -> None:
    p.drawPolyline([QPointF(10, 25), QPointF(20, 35), QPointF(38, 14)])


def _flecha_abajo(p: QPainter) -> None:
    p.drawPolyline([QPointF(13, 19), QPointF(24, 30), QPointF(35, 19)])


ICONOS: dict[str, Callable[[QPainter], None]] = {
    "pendientes": _pendientes,
    "notas": _notas,
    "comandos": _microfono,
    "rutinas": _reloj,
    "chat": _chat,
    "configuracion": _engranaje,
    "mas": _mas,
    "play": _play,
    "stop": _stop,
    "microfono": _microfono,
    "lapiz": _lapiz,
    "refrescar": _refrescar,
    "cerrar": _cerrar,
    "campana": _campana,
    "check": _check,
    "flecha_abajo": _flecha_abajo,
}


def _pintar(destino, dibujo: Callable[[QPainter], None], color: str, grosor: float = _GROSOR) -> None:
    p = QPainter(destino)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Dibujado en un lienzo de 48 y escalado al tamaño del destino.
    p.scale(destino.width() / _LIENZO, destino.height() / _LIENZO)
    lapiz = QPen(QColor(color), grosor)
    lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
    lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(lapiz)
    p.setBrush(Qt.BrushStyle.NoBrush)
    dibujo(p)
    p.end()


def _dibujar(dibujo: Callable[[QPainter], None], color: str) -> QPixmap:
    pixmap = QPixmap(_LIENZO, _LIENZO)
    pixmap.fill(Qt.GlobalColor.transparent)
    _pintar(pixmap, dibujo, color)
    return pixmap


def icono_menu(nombre: str) -> QIcon:
    dibujo = ICONOS[nombre]
    icono = QIcon()
    icono.addPixmap(_dibujar(dibujo, theme.TEXTO_SUAVE), QIcon.Mode.Normal)
    icono.addPixmap(_dibujar(dibujo, "#ffffff"), QIcon.Mode.Selected)
    return icono


# --- Botones con icono que siguen al tema ---

# Color del icono según el estilo del botón (se lee al pintar: sigue al tema).
_COLOR_POR_ROL: dict[str, Callable[[], str]] = {
    "primario": lambda: "#ffffff",
    "secundario": lambda: theme.ACENTO_TEXTO,
    "normal": lambda: theme.TEXTO,
    "suave": lambda: theme.TEXTO_SUAVE,
}
_registrados: "weakref.WeakKeyDictionary[QAbstractButton, tuple[str, str]]" = weakref.WeakKeyDictionary()


def icono(nombre: str, color: str) -> QIcon:
    return QIcon(_dibujar(ICONOS[nombre], color))


def poner_icono(boton: QAbstractButton, nombre: str, rol: str = "normal") -> None:
    """Pone un icono de línea al botón, del color de su estilo; al cambiar de
    tema se vuelve a pintar solo (ver `recolorear`)."""
    _registrados[boton] = (nombre, rol)
    if boton.text() and not boton.text().startswith(" "):
        boton.setText(f" {boton.text()}")  # aire entre el icono y el texto
    boton.setIcon(icono(nombre, _COLOR_POR_ROL[rol]()))
    boton.setIconSize(QSize(14, 14))


def recolorear() -> None:
    """Vuelve a pintar los iconos de botones con los colores del tema activo."""
    for boton, (nombre, rol) in list(_registrados.items()):
        boton.setIcon(icono(nombre, _COLOR_POR_ROL[rol]()))


def glifo(nombre: str, color: str, tamano: int = 32, grosor: float = 5.0) -> str:
    """Ruta a un PNG del icono para la hoja de estilos (casilla marcada, flecha
    de las listas). Se crea una vez por color en la carpeta de datos."""
    carpeta = data_dir() / "ui"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{nombre}-{color.lstrip('#')}-{tamano}.png"
    if not ruta.exists():
        imagen = QImage(tamano, tamano, QImage.Format.Format_ARGB32_Premultiplied)
        imagen.fill(Qt.GlobalColor.transparent)
        _pintar(imagen, ICONOS[nombre], color, grosor)
        imagen.save(str(ruta))
    return ruta.as_posix()

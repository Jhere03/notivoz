"""Logo de Notivoz.

Se carga desde assets/logo.png (reemplaza ese archivo para cambiar el logo).
Si no existe, se usa el dibujado por código: cuadro morado con ondas de voz.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap

from app.config import ruta_recurso

RUTA_LOGO = "assets/logo.png"

_TAMANOS = (16, 20, 24, 32, 40, 48, 64, 128, 256)
_ALTURAS_BARRAS = (0.26, 0.48, 0.66, 0.48, 0.26)


def _dibujar(n: int) -> QPixmap:
    pixmap = QPixmap(n, n)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    margen = n * 0.04
    cuadro = QRectF(margen, margen, n - 2 * margen, n - 2 * margen)
    degradado = QLinearGradient(cuadro.topLeft(), cuadro.bottomRight())
    degradado.setColorAt(0, QColor("#9a82ff"))
    degradado.setColorAt(1, QColor("#5b3df5"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(degradado)
    p.drawRoundedRect(cuadro, n * 0.23, n * 0.23)

    # Barras de ecualizador: la "voz" de Notivoz.
    ancho = n * 0.095
    espacio = n * 0.055
    total = len(_ALTURAS_BARRAS) * ancho + (len(_ALTURAS_BARRAS) - 1) * espacio
    x = (n - total) / 2
    p.setBrush(QColor("white"))
    for altura in _ALTURAS_BARRAS:
        alto = n * altura
        p.drawRoundedRect(QRectF(x, (n - alto) / 2, ancho, alto), ancho / 2, ancho / 2)
        x += ancho + espacio
    p.end()
    return pixmap


def icono_app() -> QIcon:
    """Logo de la app: assets/logo.png si existe; si no, el dibujado por código."""
    archivo = ruta_recurso(RUTA_LOGO)
    if archivo.exists():
        icono = QIcon(str(archivo))
        if not icono.isNull():
            return icono
    icono = QIcon()
    for n in _TAMANOS:
        icono.addPixmap(_dibujar(n))
    return icono


def exportar_logo_dibujado(destino: str, tamano: int = 512) -> None:
    """Guarda el logo dibujado por código como imagen PNG."""
    _dibujar(tamano).save(destino, "PNG")

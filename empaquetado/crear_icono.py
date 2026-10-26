"""Crea assets/notivoz.ico (varios tamaños) a partir de assets/logo.png.

Uso: python empaquetado/crear_icono.py
"""

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage

_TAMANOS = (16, 24, 32, 48, 64, 128, 256)


def crear(origen: Path, destino: Path) -> None:
    imagen = QImage(str(origen))
    if imagen.isNull():
        raise SystemExit(f"No se pudo leer {origen}")
    imagenes = []
    for tamano in _TAMANOS:
        escalada = imagen.scaled(
            tamano, tamano, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        datos = QByteArray()
        buffer = QBuffer(datos)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        escalada.save(buffer, "PNG")
        imagenes.append((tamano, bytes(datos)))

    # Formato ICO con imágenes PNG dentro (Windows Vista y posteriores).
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    desplazamiento = 6 + 16 * len(imagenes)
    entradas, cuerpo = b"", b""
    for tamano, png in imagenes:
        lado = 0 if tamano >= 256 else tamano  # 0 significa 256 en el formato ICO
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), desplazamiento)
        desplazamiento += len(png)
        cuerpo += png
    destino.write_bytes(cabecera + entradas + cuerpo)
    print(f"Icono creado: {destino}")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    raiz = Path(__file__).resolve().parents[1]
    crear(raiz / "assets" / "logo.png", raiz / "assets" / "notivoz.ico")

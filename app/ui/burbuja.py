"""Burbuja flotante que aparece al decir «Notivoz», encima de todo.

- Escuchando: crece y brilla con el volumen de tu voz. Si en 3 segundos no
  llega un comando, desaparece.
- Ejecutando: un anillo gira mientras se abren las aplicaciones.
- Hablando: palpita mientras Notivoz dice la respuesta y luego se desvanece.
"""

import math
import time
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.services.voz import voz

_TAMANO = 120  # ventana (incluye el halo)
_RADIO = 21  # burbuja en reposo
_MARGEN_DERECHO = 12
_ESPERA_COMANDO_MS = 3000
_MAXIMO_EJECUCION = 45  # segundos: por si algo falla, nunca queda pegada
_COLOR = QColor("#7c5cff")
_COLOR_CLARO = QColor("#a996ff")


class _Estado(Enum):
    OCULTA = auto()
    ESCUCHANDO = auto()
    EJECUTANDO = auto()
    HABLANDO = auto()


class BurbujaVoz(QWidget):
    def __init__(self, nivel_voz: Callable[[], float]):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(_TAMANO, _TAMANO)

        self._nivel_voz = nivel_voz
        self._estado = _Estado.OCULTA
        self._nivel = 0.0  # suavizado, 0 a 1
        self._fase = 0.0
        self._limite_ejecucion = 0.0

        self._reloj = QTimer(self, interval=30)
        self._reloj.timeout.connect(self._animar)
        self._espera_comando = QTimer(self, singleShot=True, interval=_ESPERA_COMANDO_MS)
        self._espera_comando.timeout.connect(self._sin_comando)

        self._fundido = QPropertyAnimation(self, b"windowOpacity", self)
        self._fundido.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fundido.finished.connect(self._al_terminar_fundido)

    # --- API ---------------------------------------------------------------

    def escuchar(self) -> None:
        """Se dijo «Notivoz»: aparecer y esperar el comando 3 segundos."""
        if self._estado in (_Estado.EJECUTANDO, _Estado.HABLANDO):
            return
        self._estado = _Estado.ESCUCHANDO
        self._espera_comando.start()
        self._aparecer()

    def ejecutar(self) -> None:
        """Se reconoció un comando: girar hasta que Notivoz responda."""
        self._espera_comando.stop()
        self._estado = _Estado.EJECUTANDO
        self._limite_ejecucion = time.monotonic() + _MAXIMO_EJECUCION
        self._aparecer()

    # --- Interno -----------------------------------------------------------

    def _aparecer(self) -> None:
        pantalla = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            pantalla.right() - _TAMANO - _MARGEN_DERECHO,
            pantalla.center().y() - _TAMANO // 2,
        )
        if not self.isVisible() or self._fundido.endValue() == 0.0:
            self._fundido.stop()
            if not self.isVisible():
                self.setWindowOpacity(0.0)
                self.show()
            self._fundido.setDuration(180)
            self._fundido.setStartValue(self.windowOpacity())
            self._fundido.setEndValue(1.0)
            self._fundido.start()
        self.raise_()
        self._reloj.start()

    def _desaparecer(self) -> None:
        self._estado = _Estado.OCULTA
        self._espera_comando.stop()
        self._fundido.stop()
        self._fundido.setDuration(450)
        self._fundido.setStartValue(self.windowOpacity())
        self._fundido.setEndValue(0.0)
        self._fundido.start()

    def _al_terminar_fundido(self) -> None:
        if self._fundido.endValue() == 0.0:
            self.hide()
            self._reloj.stop()
            self._nivel = 0.0

    def _sin_comando(self) -> None:
        if self._estado == _Estado.ESCUCHANDO:
            self._desaparecer()

    def _animar(self) -> None:
        self._fase += 0.03
        match self._estado:
            case _Estado.ESCUCHANDO:
                objetivo = self._nivel_voz()
            case _Estado.EJECUTANDO:
                objetivo = 0.12 + 0.06 * math.sin(self._fase * 4)
                if voz().hablando:
                    self._estado = _Estado.HABLANDO
                elif time.monotonic() > self._limite_ejecucion:
                    self._desaparecer()
            case _Estado.HABLANDO:
                # Palpitar al ritmo aproximado del habla.
                objetivo = 0.45 + 0.35 * abs(math.sin(self._fase * 9)) * abs(math.sin(self._fase * 2.3))
                if not voz().ocupada():
                    self._desaparecer()
            case _:
                objetivo = 0.0
        self._nivel += (objetivo - self._nivel) * 0.3
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        centro = QPointF(_TAMANO / 2, _TAMANO / 2)
        nivel = max(0.0, min(1.0, self._nivel))
        radio = _RADIO * (1 + 0.55 * nivel)

        # Halo que crece con la voz.
        # El halo nunca pasa del borde de la ventana: si no, se ve un cuadrado.
        radio_halo = min(radio * 2.3, _TAMANO / 2)
        halo = QRadialGradient(centro, radio_halo)
        color_halo = QColor(_COLOR)
        color_halo.setAlpha(int(70 + 120 * nivel))
        halo.setColorAt(0.0, color_halo)
        color_halo.setAlpha(0)
        halo.setColorAt(1.0, color_halo)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(centro, radio_halo, radio_halo)

        # Burbuja.
        cuerpo = QRadialGradient(centro - QPointF(radio * 0.35, radio * 0.35), radio * 1.4)
        cuerpo.setColorAt(0.0, _COLOR_CLARO)
        cuerpo.setColorAt(1.0, QColor("#5b3df5"))
        p.setBrush(cuerpo)
        p.drawEllipse(centro, radio, radio)

        # Anillo girando mientras se abren las aplicaciones.
        if self._estado == _Estado.EJECUTANDO:
            anillo = QPen(QColor(255, 255, 255, 220), 3)
            anillo.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(anillo)
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = radio + 8
            inicio = int(-self._fase * 16 * 360) % (360 * 16)
            p.drawArc(QRectF(centro.x() - r, centro.y() - r, 2 * r, 2 * r), inicio, 110 * 16)
            p.setPen(Qt.PenStyle.NoPen)

        # Barras de ecualizador (como el icono), moviéndose con el nivel.
        p.setBrush(QColor("white"))
        ancho = radio * 0.16
        espacio = radio * 0.11
        alturas = (0.45, 0.75, 1.0, 0.75, 0.45)
        x = centro.x() - (len(alturas) * ancho + (len(alturas) - 1) * espacio) / 2
        for i, base in enumerate(alturas):
            vaiven = 0.55 + 0.45 * abs(math.sin(self._fase * 7 + i * 1.3))
            alto = radio * 0.95 * base * (0.35 + 0.65 * nivel * vaiven + 0.25 * (1 - nivel))
            p.drawRoundedRect(
                QRectF(x, centro.y() - alto / 2, ancho, alto), ancho / 2, ancho / 2
            )
            x += ancho + espacio
        p.end()

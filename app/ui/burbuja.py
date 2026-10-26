"""Burbuja flotante que aparece al decir «Notivoz», encima de todo.

- Escuchando: crece y brilla con el volumen de tu voz. Si en 5 segundos no
  llega un comando, desaparece.
- Ejecutando: un anillo gira mientras se abren las aplicaciones.
- Hablando: palpita mientras Notivoz dice la respuesta. Si la conversación
  sigue (puedes contestar sin decir «Notivoz»), vuelve a escuchar; si no, se
  desvanece.
- Nube: a su lado se lee lo que dice Notivoz (o un emoji cuando le agradeces).
"""

import math
import random
import time
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.services.voz import voz

_TAMANO = 120  # ventana (incluye el halo)
_RADIO = 21  # burbuja en reposo
_MARGEN_DERECHO = 12
_ESPERA_COMANDO_MS = 5000
_MAXIMO_EJECUCION = 45  # segundos: por si algo falla, nunca queda pegada
# Al terminar de hablar, un instante escuchando por si la conversación sigue.
_GRACIA_TRAS_HABLAR_MS = 1200
_ANCHO_NUBE = 340
_LECTURA_TRAS_HABLAR_MS = 1500  # la nube queda un poco más tras la última palabra
_COLOR = QColor("#7c5cff")
_COLOR_CLARO = QColor("#a996ff")


class _Estado(Enum):
    OCULTA = auto()
    ESCUCHANDO = auto()
    EJECUTANDO = auto()
    HABLANDO = auto()


_BANDERAS_FLOTANTE = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.WindowTransparentForInput
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


_GESTOS = ("😊", "👍", "🙌", "✨", "😄", "👌", "💜", "🙂")


class _Nube(QWidget):
    """Globo de texto a la izquierda de la burbuja, con lo que dice Notivoz."""

    def __init__(self) -> None:
        super().__init__(None, _BANDERAS_FLOTANTE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._texto = QLabel()
        self._texto.setWordWrap(True)
        self._texto.setTextFormat(Qt.TextFormat.PlainText)  # nunca interpretar HTML
        self._texto.setStyleSheet("color: white; background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.addWidget(self._texto)
        self._ocultar = QTimer(self, singleShot=True)
        self._ocultar.timeout.connect(self._desvanecer)
        self._fundido = QPropertyAnimation(self, b"windowOpacity", self)
        self._fundido.finished.connect(lambda: self.hide() if self._fundido.endValue() == 0.0 else None)

    def mostrar(self, texto: str, burbuja: QRect, emoji: bool = False) -> None:
        fuente = QFont("Segoe UI Emoji" if emoji else "Segoe UI", 26 if emoji else 10)
        self._texto.setFont(fuente)
        self._texto.setText(texto)
        # Ancho justo para el texto (una frase corta no deja una nube enorme).
        ancho = QFontMetrics(fuente).horizontalAdvance(texto) + 6
        self._texto.setFixedWidth(min(ancho, _ANCHO_NUBE - 32))
        self.adjustSize()
        self.colocar(burbuja)
        self._fundido.stop()
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        # Tiempo para leerlo: unos 15 caracteres por segundo, mínimo 3 s.
        self._ocultar.start(2500 if emoji else int(max(3.0, len(texto) / 15 + 2) * 1000))

    def colocar(self, burbuja: QRect) -> None:
        self.move(burbuja.left() - self.width() + 14, burbuja.center().y() - self.height() // 2)

    def ocultar_pronto(self) -> None:
        if self.isVisible() and self._ocultar.remainingTime() > 1500:
            self._ocultar.start(1500)

    def _desvanecer(self) -> None:
        if voz().ocupada():
            # Sigue hablando: la nube espera (y luego queda un momento para leerla).
            self._ocultar.start(_LECTURA_TRAS_HABLAR_MS)
            return
        self._fundido.stop()
        self._fundido.setDuration(400)
        self._fundido.setStartValue(self.windowOpacity())
        self._fundido.setEndValue(0.0)
        self._fundido.start()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(124, 92, 255, 150), 1.5))
        p.setBrush(QColor(28, 31, 38, 238))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)
        p.end()


class BurbujaVoz(QWidget):
    def __init__(self, nivel_voz: Callable[[], float]):
        super().__init__(None, _BANDERAS_FLOTANTE)
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
        self._nube = _Nube()

    # --- API ---------------------------------------------------------------

    def escuchar(self, milisegundos: int = _ESPERA_COMANDO_MS) -> None:
        """Te está escuchando (dijiste «Notivoz» o la conversación sigue):
        aparecer y esperar unos segundos."""
        if self._estado == _Estado.EJECUTANDO or (self._estado == _Estado.HABLANDO and voz().ocupada()):
            return
        self._estado = _Estado.ESCUCHANDO
        self._espera_comando.start(max(milisegundos, self._espera_comando.remainingTime()))
        self._aparecer()

    def decir(self, texto: str) -> None:
        """Muestra en la nube lo que dice Notivoz (no gasta nada: es el mismo texto
        que se lee en voz alta). La burbuja acompaña hasta que termine de hablar."""
        self._espera_comando.stop()
        self._estado = _Estado.EJECUTANDO  # pasa a «hablando» cuando empiece a sonar
        self._limite_ejecucion = time.monotonic() + _MAXIMO_EJECUCION
        self._aparecer()
        self._nube.mostrar(texto, self.geometry())

    def gesto(self) -> None:
        """Una sonrisa o un 👍 sin hablar (le agradeciste o cerraste el pedido)."""
        self._aparecer()
        self._estado = _Estado.ESCUCHANDO
        self._espera_comando.start(2500)
        self._nube.mostrar(random.choice(_GESTOS), self.geometry(), emoji=True)

    def ejecutar(self) -> None:
        """Se reconoció un comando: girar hasta que Notivoz responda."""
        self._espera_comando.stop()
        self._estado = _Estado.EJECUTANDO
        self._limite_ejecucion = time.monotonic() + _MAXIMO_EJECUCION
        self._aparecer()

    def ocultar(self) -> None:
        if self._estado != _Estado.OCULTA:
            self._desaparecer()

    # --- Interno -----------------------------------------------------------

    def _aparecer(self) -> None:
        pantalla = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            pantalla.right() - _TAMANO - _MARGEN_DERECHO,
            pantalla.center().y() - _TAMANO // 2,
        )
        if self._nube.isVisible():
            self._nube.colocar(self.geometry())
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
        self._nube.ocultar_pronto()
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
                if voz().hablando:
                    # Notivoz empezó a hablar (respuesta): acompañarlo hasta el final.
                    self._espera_comando.stop()
                    self._estado = _Estado.HABLANDO
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
                    # Un instante escuchando: si la conversación sigue, la escucha
                    # avisa y se alarga; si no, se desvanece sola.
                    self._estado = _Estado.ESCUCHANDO
                    self._espera_comando.start(_GRACIA_TRAS_HABLAR_MS)
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

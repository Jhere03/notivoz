"""Burbuja flotante de Notivoz, encima de todo, y su nube de texto.

Cómo se habla con Notivoz:
- Al decir «Notivoz» aparece la burbuja unos segundos («Presióname para hablar»).
  Todavía no escucha tu pedido.
- Al presionarla (o pulsar la tecla para hablar), te escucha («Escuchándote…»):
  la burbuja pone carita de oír, con ondas que crecen con tu voz. Cuando dejas
  de hablar pasa sola a «Procesando…»: piensa mirando a los lados, con tres
  lucecitas girando, y no desaparece hasta que Notivoz termina.
- La respuesta se lee en la nube mientras Notivoz habla. Después, la burbuja
  queda unos segundos: si la tocas, sigues la conversación. Si hizo algo (crear,
  editar, eliminar…) o le agradeces, se despide con una carita: sonrisa, guiño,
  lengua afuera, ojos de estrella, risa o sonrojo.
- Mientras procesa o habla, tocarla también vuelve a escucharte.
"""

import math
import random
import time
from collections import deque
from collections.abc import Callable
from enum import Enum, auto

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.services import ajustes
from app.services.voz import voz
from app.ui import tecla_hablar
from app.ui.formato import partible

_TAMANO = 120  # ventana (incluye el halo)
_RADIO = 21  # burbuja en reposo
_MARGEN_DERECHO = 12
_ESPERA_TOQUE_MS = 3000  # tras «Notivoz», tiempo para tocarla
_TRAS_RESPONDER_MS = 4000  # tras la respuesta, tiempo para tocarla y seguir
_ANTES_DEL_GESTO_MS = 2500  # si va a despedirse con una carita, espera menos
_GESTO_MS = 2600  # cuánto dura la carita
_EXPRESIONES = ("sonrisa", "guino", "lengua", "estrellas", "risa", "sonrojo")
_OSCURO = QColor("#2b1d6b")
_ROSADO = QColor("#ff7aa8")
_MAXIMO_ESCUCHANDO_MS = 40000
_MAXIMO_PROCESANDO = 45  # segundos: por si algo falla, nunca queda pegada
_ANCHO_NUBE = 340
_LECTURA_TRAS_HABLAR_MS = 1500  # la nube queda un poco más tras la última palabra
_COLOR = QColor("#7c5cff")
_COLOR_CLARO = QColor("#a996ff")


class _Estado(Enum):
    OCULTA = auto()
    ESPERANDO = auto()  # dijiste «Notivoz»: presiónala para hablar
    ESCUCHANDO = auto()  # la tocaste: te está escuchando
    PROCESANDO = auto()  # pensando tu pedido o abriendo un modo
    HABLANDO = auto()  # diciendo la respuesta
    RESPONDIO = auto()  # terminó: unos segundos por si quieres seguir
    GESTO = auto()  # una carita (guiño, sonrisa…) antes de irse


_BANDERAS_FLOTANTE = (
    Qt.WindowType.Tool
    | Qt.WindowType.FramelessWindowHint
    | Qt.WindowType.WindowStaysOnTopHint
    | Qt.WindowType.WindowDoesNotAcceptFocus
)


class _Nube(QWidget):
    """Globo de texto a la izquierda de la burbuja."""

    def __init__(self) -> None:
        super().__init__(None, _BANDERAS_FLOTANTE | Qt.WindowType.WindowTransparentForInput)
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

    def mostrar(self, texto: str, burbuja: QRect, emoji: bool = False, fija: bool = False) -> None:
        """`fija`: queda hasta que se cambie (estados como «Escuchándote…»);
        si no, se oculta sola tras el tiempo de lectura."""
        fuente = QFont("Segoe UI Emoji" if emoji else "Segoe UI", 26 if emoji else 10)
        self._texto.setFont(fuente)
        self._texto.setText(partible(texto))
        # Ancho justo para el texto (una frase corta no deja una nube enorme).
        ancho = QFontMetrics(fuente).horizontalAdvance(texto) + 6
        self._texto.setFixedWidth(min(ancho, _ANCHO_NUBE - 32))
        self.adjustSize()
        self.colocar(burbuja)
        self._fundido.stop()
        self.setWindowOpacity(1.0)
        self.show()
        self.raise_()
        if fija:
            self._ocultar.stop()
        else:
            # Tiempo para leerlo: unos 15 caracteres por segundo, mínimo 3 s.
            self._ocultar.start(2500 if emoji else int(max(3.0, len(texto) / 15 + 2) * 1000))

    def colocar(self, burbuja: QRect) -> None:
        self.move(burbuja.left() - self.width() + 14, burbuja.center().y() - self.height() // 2)

    def ocultar_ya(self) -> None:
        if self.isVisible():
            self._ocultar.start(0)

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
    # La tocaste: quieres hablarle.
    tocada = Signal()

    def __init__(self, nivel_voz: Callable[[], float]):
        super().__init__(None, _BANDERAS_FLOTANTE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(_TAMANO, _TAMANO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Toca para hablarle a Notivoz")

        self._nivel_voz = nivel_voz
        self._estado = _Estado.OCULTA
        self._nivel = 0.0  # suavizado, 0 a 1
        self._fase = 0.0
        self._limite_procesando = 0.0
        self._puntos = 0  # «Procesando…» animado
        self._texto_estado = ""
        self._expresion = "sonrisa"
        self._expresiones_recientes: deque[str] = deque(maxlen=3)
        self._gesto_pendiente = False  # despedirse con una carita al terminar
        self._inicio_gesto = 0.0
        self._tecla: dict | None = None  # tecla para hablar (en vez de presionarla)
        self._tecla_tomada = False

        self._reloj = QTimer(self, interval=30)
        self._reloj.timeout.connect(self._animar)
        self._caducar = QTimer(self, singleShot=True)
        self._caducar.timeout.connect(self._al_caducar)
        self._reloj_puntos = QTimer(self, interval=400)
        self._reloj_puntos.timeout.connect(self._animar_puntos)

        self._fundido = QPropertyAnimation(self, b"windowOpacity", self)
        self._fundido.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fundido.finished.connect(self._al_terminar_fundido)
        self._nube = _Nube()

    # --- API ---------------------------------------------------------------

    def esperar_toque(self) -> None:
        """Dijiste «Notivoz»: aparecer unos segundos para que la toques."""
        if self._estado in (_Estado.ESCUCHANDO, _Estado.PROCESANDO, _Estado.HABLANDO):
            return
        self._cambiar(_Estado.ESPERANDO, _ESPERA_TOQUE_MS)
        self._nube.mostrar("Presióname para hablar", self.geometry(), fija=True)

    def escuchando(self) -> None:
        """La tocaste: te está escuchando hasta que dejes de hablar."""
        # (Por si la escucha se detiene sin avisar: nunca queda pegada.)
        self._gesto_pendiente = False
        self._cambiar(_Estado.ESCUCHANDO, _MAXIMO_ESCUCHANDO_MS)
        self._mostrar_estado("escuchando")

    def procesando(self, con_nube: bool = True) -> None:
        """Pensando tu pedido (o abriendo un modo). No desaparece hasta terminar."""
        self._cambiar(_Estado.PROCESANDO)
        self._limite_procesando = time.monotonic() + _MAXIMO_PROCESANDO
        if con_nube:
            self._mostrar_estado("procesando")
        else:
            self._nube.ocultar_ya()

    def decir(self, texto: str) -> None:
        """Muestra en la nube lo que dice Notivoz (no gasta nada: es el mismo texto
        que se lee en voz alta). La burbuja acompaña hasta que termine de hablar."""
        self._cambiar(_Estado.PROCESANDO)  # pasa a «hablando» cuando empiece a sonar
        self._limite_procesando = time.monotonic() + _MAXIMO_PROCESANDO
        self._nube.mostrar(texto, self.geometry())

    def mensaje(self, texto: str) -> None:
        """Un aviso breve («No te escuché»…) y luego se oculta."""
        self._cambiar(_Estado.RESPONDIO, int(max(3.0, len(texto) / 15 + 2) * 1000))
        self._nube.mostrar(texto, self.geometry())

    def gesto(self) -> None:
        """Una carita sin hablar (le agradeciste o cerraste el pedido)."""
        self._gesto_pendiente = False
        self._expresion = random.choice([e for e in _EXPRESIONES if e not in self._expresiones_recientes])
        self._expresiones_recientes.append(self._expresion)
        self._inicio_gesto = self._fase
        self._nube.ocultar_ya()
        self._cambiar(_Estado.GESTO, _GESTO_MS)

    def gesto_al_terminar(self) -> None:
        """Hizo lo que pediste: al terminar de hablar (si no le vuelves a hablar),
        se despide con una carita."""
        self._gesto_pendiente = True

    def ocultar(self) -> None:
        if self._estado != _Estado.OCULTA:
            self._desaparecer()

    def set_tecla(self, tecla: dict | None) -> None:
        """La tecla que hace lo mismo que presionar la burbuja (None = ninguna)."""
        self._soltar_tecla()
        self._tecla = tecla
        if self.isVisible():
            self._tomar_tecla()

    def escuchar(self, _milisegundos: int = 0) -> None:
        """Se oyó «Notivoz» (o lo interrumpiste con «espera»): como esperar_toque."""
        self.esperar_toque()

    def ejecutar(self) -> None:
        """Un comando de voz exacto («modo relax»): girar hasta que Notivoz hable."""
        self.procesando(con_nube=False)

    # --- Interno -----------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._presionada()

    def nativeEvent(self, tipo, mensaje):
        if tipo == b"windows_generic_MSG" and tecla_hablar.es_la_tecla(mensaje):
            self._presionada()
            return True, 0
        return super().nativeEvent(tipo, mensaje)

    def _presionada(self) -> None:
        if self._estado not in (_Estado.OCULTA, _Estado.ESCUCHANDO):
            self.tocada.emit()

    def _tomar_tecla(self) -> None:
        # Solo mientras se ve la burbuja: el resto del tiempo la tecla escribe normal.
        if self._tecla and not self._tecla_tomada:
            self._tecla_tomada = tecla_hablar.registrar(int(self.winId()), self._tecla)

    def _soltar_tecla(self) -> None:
        if self._tecla_tomada:
            tecla_hablar.liberar(int(self.winId()))
            self._tecla_tomada = False

    def _mostrar_estado(self, clave: str) -> None:
        self._texto_estado = ajustes.frases_actuales().estado(clave)
        self._puntos = 0
        self._nube.mostrar(self._texto_estado, self.geometry(), fija=True)
        self._reloj_puntos.start()

    def _cambiar(self, estado: _Estado, caduca_ms: int = 0) -> None:
        self._estado = estado
        self._reloj_puntos.stop()
        if caduca_ms:
            self._caducar.start(caduca_ms)
        else:
            self._caducar.stop()
        self._aparecer()

    def _al_caducar(self) -> None:
        if self._estado == _Estado.RESPONDIO and self._gesto_pendiente:
            self.gesto()
        elif self._estado in (_Estado.ESPERANDO, _Estado.ESCUCHANDO, _Estado.RESPONDIO, _Estado.GESTO):
            self._desaparecer()

    def _animar_puntos(self) -> None:
        self._puntos = (self._puntos + 1) % 4
        self._nube.mostrar(self._texto_estado + "." * self._puntos, self.geometry(), fija=True)

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
        self._tomar_tecla()
        if self._nube.isVisible():
            self._nube.colocar(self.geometry())

    def _desaparecer(self) -> None:
        self._estado = _Estado.OCULTA
        self._gesto_pendiente = False
        self._caducar.stop()
        self._reloj_puntos.stop()
        self._nube.ocultar_ya()
        self._fundido.stop()
        self._fundido.setDuration(450)
        self._fundido.setStartValue(self.windowOpacity())
        self._fundido.setEndValue(0.0)
        self._fundido.start()

    def _al_terminar_fundido(self) -> None:
        if self._fundido.endValue() == 0.0:
            self._soltar_tecla()
            self.hide()
            self._reloj.stop()
            self._nivel = 0.0

    def _animar(self) -> None:
        self._fase += 0.03
        match self._estado:
            case _Estado.ESCUCHANDO:
                objetivo = self._nivel_voz()
            case _Estado.ESPERANDO:
                # Late suave: «tócame».
                objetivo = 0.15 + 0.15 * abs(math.sin(self._fase * 3))
            case _Estado.PROCESANDO:
                objetivo = 0.12 + 0.06 * math.sin(self._fase * 4)
                if voz().hablando:
                    self._cambiar(_Estado.HABLANDO)
                elif time.monotonic() > self._limite_procesando:
                    self._desaparecer()
            case _Estado.HABLANDO:
                # Palpitar al ritmo aproximado del habla.
                objetivo = 0.45 + 0.35 * abs(math.sin(self._fase * 9)) * abs(math.sin(self._fase * 2.3))
                if not voz().ocupada():
                    # Terminó de hablar: queda unos segundos por si quieres seguir.
                    espera = _ANTES_DEL_GESTO_MS if self._gesto_pendiente else _TRAS_RESPONDER_MS
                    self._cambiar(_Estado.RESPONDIO, espera)
            case _Estado.GESTO:
                objetivo = 0.45  # un poco más grande, para que se vea la carita
            case _Estado.RESPONDIO:
                objetivo = 0.1
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
        if self._estado == _Estado.GESTO:
            # Un saltito al aparecer la carita.
            pasado = self._fase - self._inicio_gesto
            if pasado < 0.6:
                centro -= QPointF(0, 6 * abs(math.sin(pasado * math.pi / 0.3)) * (1 - pasado / 0.6))

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

        if self._estado == _Estado.ESCUCHANDO:
            self._dibujar_ondas(p, centro, radio, nivel)

        # Burbuja (mientras piensa, se estira y encoge como gelatina).
        ancho_cuerpo = alto_cuerpo = radio
        if self._estado == _Estado.PROCESANDO:
            estirar = 0.07 * math.sin(self._fase * 7)
            ancho_cuerpo, alto_cuerpo = radio * (1 + estirar), radio * (1 - estirar)
        cuerpo = QRadialGradient(centro - QPointF(radio * 0.35, radio * 0.35), radio * 1.4)
        cuerpo.setColorAt(0.0, _COLOR_CLARO)
        cuerpo.setColorAt(1.0, QColor("#5b3df5"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(cuerpo)
        p.drawEllipse(centro, ancho_cuerpo, alto_cuerpo)

        if self._estado == _Estado.ESCUCHANDO:
            self._dibujar_cara(p, centro, radio, pensando=False, boca=nivel)
        elif self._estado == _Estado.PROCESANDO:
            self._dibujar_cara(p, centro, radio, pensando=True, boca=0.0)
            self._dibujar_lucecitas(p, centro, radio)
        elif self._estado == _Estado.GESTO:
            self._dibujar_expresion(p, centro, radio)
        else:
            self._dibujar_barras(p, centro, radio, nivel)
        p.end()

    def _dibujar_ondas(self, p: QPainter, centro: QPointF, radio: float, nivel: float) -> None:
        """Ondas que salen de la burbuja, más rápidas y fuertes cuanto más alto hablas."""
        p.setBrush(Qt.BrushStyle.NoBrush)
        maximo = _TAMANO / 2 - 2
        for k in range(3):
            avance = (self._fase * (0.7 + 1.6 * nivel) + k / 3) % 1.0
            r = radio + avance * (maximo - radio)
            color = QColor(255, 255, 255, int((1 - avance) * (70 + 160 * nivel)))
            p.setPen(QPen(color, 2))
            p.drawEllipse(centro, r, r)
        p.setPen(Qt.PenStyle.NoPen)

    def _dibujar_cara(self, p: QPainter, centro: QPointF, radio: float, pensando: bool, boca: float) -> None:
        """Ojitos y boca: al escuchar parpadea y abre la boca con tu voz; al
        pensar mira hacia arriba, de un lado a otro."""
        parpadeo = (self._fase % 2.6) < 0.12 and not pensando
        ojo_x, ojo_y = radio * 0.34, centro.y() - radio * 0.15
        ancho_ojo, alto_ojo = radio * 0.2, radio * (0.04 if parpadeo else 0.27)
        if pensando:
            mirada = QPointF(math.sin(self._fase * 2.2) * radio * 0.08, -radio * 0.1)
        else:
            mirada = QPointF(math.sin(self._fase * 0.9) * radio * 0.03, radio * 0.02)
        for lado in (-1, 1):
            ojo = QPointF(centro.x() + lado * ojo_x, ojo_y)
            p.setBrush(QColor("white"))
            p.drawEllipse(ojo, ancho_ojo, alto_ojo)
            if not parpadeo:
                p.setBrush(QColor("#2b1d6b"))
                p.drawEllipse(ojo + mirada, radio * 0.1, radio * 0.12)
        boca_centro = QPointF(centro.x(), centro.y() + radio * 0.42)
        if pensando:
            # Boquita de «mmm…» que se mueve de lado.
            trazo = QPen(QColor("white"), max(2.0, radio * 0.09))
            trazo.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(trazo)
            desvio = math.sin(self._fase * 2.2) * radio * 0.1
            p.drawLine(
                QPointF(boca_centro.x() - radio * 0.14 + desvio, boca_centro.y()),
                QPointF(boca_centro.x() + radio * 0.14 + desvio, boca_centro.y() - radio * 0.04),
            )
            p.setPen(Qt.PenStyle.NoPen)
        else:
            # «Oh»: se abre con tu voz.
            p.setBrush(QColor("#2b1d6b"))
            p.drawEllipse(boca_centro, radio * (0.1 + 0.12 * boca), radio * (0.07 + 0.22 * boca))

    def _dibujar_expresion(self, p: QPainter, centro: QPointF, radio: float) -> None:
        """La carita del gesto: ojos y boca según la expresión elegida."""
        ojos = [QPointF(centro.x() + lado * radio * 0.34, centro.y() - radio * 0.15) for lado in (-1, 1)]
        boca = QPointF(centro.x(), centro.y() + radio * 0.3)
        trazo = QPen(QColor("white"), max(2.0, radio * 0.1))
        trazo.setCapStyle(Qt.PenCapStyle.RoundCap)
        e = self._expresion
        brillo = 0.85 + 0.15 * math.sin(self._fase * 8)

        def ojo_feliz(punto: QPointF) -> None:  # «^»
            p.setPen(trazo)
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = radio * 0.15
            p.drawArc(QRectF(punto.x() - r, punto.y() - r * 0.6, 2 * r, 2 * r), 20 * 16, 140 * 16)
            p.setPen(Qt.PenStyle.NoPen)

        def ojo_abierto(punto: QPointF) -> None:
            p.setBrush(QColor("white"))
            p.drawEllipse(punto, radio * 0.2, radio * 0.25)
            p.setBrush(_OSCURO)
            p.drawEllipse(punto + QPointF(0, radio * 0.03), radio * 0.1, radio * 0.12)

        def sonrisa(abierta: bool = False) -> None:
            ancho, alto = radio * 0.62, radio * 0.42
            caja = QRectF(boca.x() - ancho / 2, boca.y() - alto / 2, ancho, alto)
            if abierta:
                p.setBrush(_OSCURO)
                p.drawChord(caja, 180 * 16, 180 * 16)
                p.setBrush(_ROSADO)
                p.drawEllipse(QPointF(boca.x(), boca.y() + alto * 0.3), ancho * 0.2, alto * 0.14)
            else:
                p.setPen(trazo)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(caja, 200 * 16, 140 * 16)
                p.setPen(Qt.PenStyle.NoPen)

        if e == "sonrisa":
            for punto in ojos:
                ojo_feliz(punto)
            sonrisa()
        elif e == "guino":
            ojo_abierto(ojos[0])
            ojo_feliz(ojos[1])
            sonrisa()
        elif e == "lengua":
            ojo_feliz(ojos[0])
            ojo_abierto(ojos[1])
            # Lengua afuera: cuelga del centro de la sonrisa (que la tapa arriba,
            # como si saliera de la boca) y se mueve un poquito de lado.
            ancho, alto = radio * 0.3, radio * 0.34
            arriba = boca.y() + radio * 0.12
            vaiven = math.sin(self._fase * 9) * radio * 0.04
            izquierda = boca.x() - ancho / 2 + vaiven
            lengua = QPainterPath(QPointF(izquierda, arriba))
            lengua.lineTo(izquierda, arriba + alto - ancho / 2)
            lengua.arcTo(QRectF(izquierda, arriba + alto - ancho, ancho, ancho), 180, 180)
            lengua.lineTo(izquierda + ancho, arriba)
            lengua.closeSubpath()
            p.setBrush(_ROSADO)
            p.drawPath(lengua)
            raya = QPen(QColor("#d94f80"), max(1.0, radio * 0.04))
            raya.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(raya)
            p.drawLine(QPointF(boca.x() + vaiven, arriba + radio * 0.06), QPointF(boca.x() + vaiven, arriba + alto * 0.6))
            p.setPen(Qt.PenStyle.NoPen)
            sonrisa()
        elif e == "estrellas":
            for punto in ojos:
                self._estrella(p, punto, radio * 0.25 * brillo, self._fase * 2)
            sonrisa(abierta=True)
        elif e == "risa":
            # «> <» y boca abierta.
            p.setPen(trazo)
            r = radio * 0.11
            for lado, punto in zip((1, -1), ojos):
                p.drawLine(QPointF(punto.x() - lado * r, punto.y() - r), QPointF(punto.x() + lado * r, punto.y()))
                p.drawLine(QPointF(punto.x() + lado * r, punto.y()), QPointF(punto.x() - lado * r, punto.y() + r))
            p.setPen(Qt.PenStyle.NoPen)
            sonrisa(abierta=True)
        else:  # sonrojo
            for punto in ojos:
                ojo_feliz(punto)
            mejilla = QColor(_ROSADO)
            mejilla.setAlpha(150)
            p.setBrush(mejilla)
            for lado in (-1, 1):
                p.drawEllipse(QPointF(centro.x() + lado * radio * 0.55, centro.y() + radio * 0.15), radio * 0.16, radio * 0.09)
            sonrisa()

    @staticmethod
    def _estrella(p: QPainter, punto: QPointF, tamano: float, giro: float) -> None:
        puntas = []
        for i in range(10):
            r = tamano if i % 2 == 0 else tamano * 0.45
            angulo = giro + i * math.pi / 5 - math.pi / 2
            puntas.append(QPointF(punto.x() + r * math.cos(angulo), punto.y() + r * math.sin(angulo)))
        p.setBrush(QColor("#ffd166"))
        p.drawPolygon(QPolygonF(puntas))

    def _dibujar_lucecitas(self, p: QPainter, centro: QPointF, radio: float) -> None:
        """Tres lucecitas que giran alrededor, rebotando, mientras piensa."""
        colores = (QColor("white"), QColor("#ffd166"), QColor("#6ee7f9"))
        for i, color in enumerate(colores):
            angulo = self._fase * 3.2 + i * 2 * math.pi / 3
            r = radio + 10 + 4 * math.sin(self._fase * 8 + i * 2)
            punto = QPointF(centro.x() + r * math.cos(angulo), centro.y() + r * math.sin(angulo))
            p.setBrush(color)
            tamano = 3.5 + 1.3 * math.sin(self._fase * 6 + i)
            p.drawEllipse(punto, tamano, tamano)

    def _dibujar_barras(self, p: QPainter, centro: QPointF, radio: float, nivel: float) -> None:
        """Barras de ecualizador (como el icono), moviéndose con el nivel."""
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

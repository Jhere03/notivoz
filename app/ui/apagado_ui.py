"""Cuenta regresiva del apagado programado (barra lateral) y aviso un minuto
antes, encima de cualquier aplicación, con «Cancelar apagado»."""

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services import ajustes, apagado
from app.services.voz import voz

_AVISO_SEGUNDOS = 60
_ESPERA_DESPEDIDA = 15  # segundos como mucho esperando a que termine de hablar


def _reloj(segundos: int) -> str:
    horas, resto = divmod(max(0, segundos), 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas}:{minutos:02d}:{segundos:02d}" if horas else f"{minutos:02d}:{segundos:02d}"


class AlertaApagado(QWidget):
    """Aviso sin bordes, siempre encima, con la cuenta de los últimos segundos."""

    cancelar = Signal()
    ya = Signal()

    def __init__(self, accion: str):
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self._accion = accion
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedWidth(420)

        marco = QFrame()
        marco.setObjectName("Alerta")
        sombra = QGraphicsDropShadowEffect(marco)
        sombra.setBlurRadius(28)
        sombra.setOffset(0, 6)
        sombra.setColor(QColor(0, 0, 0, 160))
        marco.setGraphicsEffect(sombra)

        etiqueta = QLabel(f"⏻  {'APAGADO' if accion == apagado.APAGAR else 'REINICIO'} PROGRAMADO")
        etiqueta.setObjectName("AlertaEtiqueta")
        self.titulo = QLabel()
        self.titulo.setObjectName("AlertaTitulo")
        self.titulo.setWordWrap(True)
        ayuda = QLabel("Guarda tu trabajo. Los programas con cambios sin guardar te pedirán guardar.")
        ayuda.setObjectName("AlertaContenido")
        ayuda.setWordWrap(True)

        ya = QPushButton("Apagar ya" if accion == apagado.APAGAR else "Reiniciar ya")
        ya.setCursor(Qt.CursorShape.PointingHandCursor)
        ya.clicked.connect(self.ya)
        cancelar = QPushButton("Cancelar " + ("apagado" if accion == apagado.APAGAR else "reinicio"))
        cancelar.setObjectName("Primario")
        cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        cancelar.clicked.connect(self.cancelar)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(ya)
        botones.addWidget(cancelar)

        interior = QVBoxLayout(marco)
        interior.setContentsMargins(18, 14, 14, 16)
        interior.setSpacing(8)
        interior.addWidget(etiqueta)
        interior.addWidget(self.titulo)
        interior.addWidget(ayuda)
        interior.addSpacing(4)
        interior.addLayout(botones)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(marco)
        self.actualizar(_AVISO_SEGUNDOS)

    def actualizar(self, segundos: int) -> None:
        verbo = "se apagará" if self._accion == apagado.APAGAR else "se reiniciará"
        self.titulo.setText(f"Tu PC {verbo} en {max(0, segundos)} s")
        self.adjustSize()
        pantalla = QGuiApplication.primaryScreen().availableGeometry()
        self.move(pantalla.right() - self.width() - 8, pantalla.bottom() - self.height() - 8)


class ControladorApagado(QObject):
    """Revisa cada segundo lo programado: muestra la cuenta, avisa y apaga."""

    # Texto para la barra lateral («⏻ Se apaga en 04:59») o "" si no hay nada.
    cambiado = Signal(str)

    def __init__(self, parent=None, ejecutar: Callable[[str], None] = apagado.ejecutar):
        super().__init__(parent)
        self._ejecutar = ejecutar  # (las pruebas lo cambian: nunca apagan de verdad)
        self._alerta: AlertaApagado | None = None
        self._texto = ""
        self._reloj = QTimer(self, interval=1000)
        self._reloj.timeout.connect(self.revisar)
        self._reloj.start()

    def cancelar(self) -> None:
        """Clic en la barra lateral o en «Cancelar apagado»."""
        if apagado.cancelar() is not None:
            voz().hablar(ajustes.frases_actuales().frase("apagado_cancelado"))
        self.revisar()

    def ya(self) -> None:
        programado = apagado.cancelar()
        self._cerrar_alerta()
        if programado is not None:
            self._ejecutar(programado.accion)

    def revisar(self) -> None:
        programado = apagado.actual()
        if programado is None:
            self._cerrar_alerta()
            self._mostrar("")
            return
        restante = int((programado.cuando - datetime.now()).total_seconds())
        if programado.confirmado:
            # Lo confirmaste: apenas termina de despedirse (como mucho 15 s más).
            self._mostrar("⏻ Apagando…" if programado.accion == apagado.APAGAR else "⏻ Reiniciando…")
            if restante > 0 or (voz().ocupada() and restante > -_ESPERA_DESPEDIDA):
                return
            apagado.cancelar()
            self._mostrar("")
            self._ejecutar(programado.accion)
            return
        if restante <= 0:
            apagado.cancelar()
            self._cerrar_alerta()
            self._mostrar("")
            self._ejecutar(programado.accion)
            return
        verbo = "Se apaga" if programado.accion == apagado.APAGAR else "Se reinicia"
        if restante > 3600:
            self._mostrar(f"⏻ {verbo} a las {programado.cuando:%H:%M}")
        else:
            self._mostrar(f"⏻ {verbo} en {_reloj(restante)}")
        if restante <= _AVISO_SEGUNDOS:
            if self._alerta is None:
                self._alerta = AlertaApagado(programado.accion)
                self._alerta.cancelar.connect(self.cancelar)
                self._alerta.ya.connect(self.ya)
                self._alerta.show()
                clave = "apagado_aviso" if programado.accion == apagado.APAGAR else "reinicio_aviso"
                voz().hablar(ajustes.frases_actuales().frase(clave))
            self._alerta.actualizar(restante)
        else:
            self._cerrar_alerta()

    def _mostrar(self, texto: str) -> None:
        if texto != self._texto:
            self._texto = texto
            self.cambiado.emit(texto)

    def _cerrar_alerta(self) -> None:
        if self._alerta is not None:
            self._alerta.close()
            self._alerta.deleteLater()
            self._alerta = None

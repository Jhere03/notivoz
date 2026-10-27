"""Alertas de recordatorio siempre encima y el programador que las lanza."""

import winsound
from collections.abc import Callable
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Nota
from app.services import notas as servicio
from app.services.voz import voz
from app.ui.formato import fecha_hora_corta, partible

_MARGEN = 16
_SEPARACION = 4
_MAX_VOZ = 300
_OPCIONES_POSPONER = ((5, "5 minutos"), (10, "10 minutos"), (30, "30 minutos"), (60, "1 hora"))


def texto_voz(nota: Nota) -> str:
    texto = f"Recuerda: {nota.titulo.rstrip('.')}."
    if nota.contenido:
        contenido = nota.contenido[:_MAX_VOZ]
        texto += f" {contenido}"
    return texto


class AlertaRecordatorio(QWidget):
    """Ventana sin bordes, siempre encima de cualquier aplicación."""

    cerrada = Signal(object)
    posponer = Signal(int, int)  # nota_id, minutos

    def __init__(self, nota: Nota):
        super().__init__(
            None,
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.nota_id = nota.id
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedWidth(420)

        marco = QFrame()
        marco.setObjectName("Alerta")
        sombra = QGraphicsDropShadowEffect(marco)
        sombra.setBlurRadius(28)
        sombra.setOffset(0, 6)
        sombra.setColor(QColor(0, 0, 0, 160))
        marco.setGraphicsEffect(sombra)

        cuando = fecha_hora_corta(nota.recordatorio)
        if datetime.now() - nota.recordatorio > timedelta(minutes=2):
            cuando += "  (atrasado)"
        etiqueta = QLabel(f"🔔  RECORDATORIO  ·  {cuando}")
        etiqueta.setObjectName("AlertaEtiqueta")
        cerrar = QPushButton("✕")
        cerrar.setObjectName("AlertaCerrar")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.setToolTip("Cerrar")
        cerrar.clicked.connect(self.close)

        cabecera = QHBoxLayout()
        cabecera.addWidget(etiqueta, stretch=1)
        cabecera.addWidget(cerrar)

        titulo = QLabel(partible(nota.titulo))
        titulo.setObjectName("AlertaTitulo")
        titulo.setWordWrap(True)

        btn_posponer = QPushButton("Posponer  ▾")
        btn_posponer.setCursor(Qt.CursorShape.PointingHandCursor)
        menu = QMenu(btn_posponer)
        for minutos, texto in _OPCIONES_POSPONER:
            menu.addAction(texto, lambda m=minutos: self._posponer(m))
        btn_posponer.setMenu(menu)

        btn_listo = QPushButton("Listo")
        btn_listo.setObjectName("Primario")
        btn_listo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_listo.clicked.connect(self.close)

        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(btn_posponer)
        botones.addWidget(btn_listo)

        interior = QVBoxLayout(marco)
        interior.setContentsMargins(18, 14, 14, 16)
        interior.setSpacing(8)
        interior.addLayout(cabecera)
        interior.addWidget(titulo)
        if nota.contenido:
            contenido = QLabel(partible(nota.contenido))
            contenido.setObjectName("AlertaContenido")
            contenido.setWordWrap(True)
            contenido.setMaximumHeight(160)
            contenido.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            interior.addWidget(contenido)
        interior.addSpacing(4)
        interior.addLayout(botones)

        layout = QVBoxLayout(self)
        # Espacio alrededor para que se vea la sombra.
        layout.setContentsMargins(14, 14, 14, 14)
        layout.addWidget(marco)
        self.adjustSize()

    def _posponer(self, minutos: int) -> None:
        self.posponer.emit(self.nota_id, minutos)
        self.close()

    def closeEvent(self, event) -> None:
        self.cerrada.emit(self)
        super().closeEvent(event)


class ProgramadorRecordatorios(QObject):
    """Revisa cada pocos segundos si llegó la hora de algún recordatorio."""

    notas_cambiaron = Signal()

    def __init__(self, parent=None, intervalo_ms: int = 10_000):
        super().__init__(parent)
        self._alertas: list[AlertaRecordatorio] = []
        # Mientras devuelva True (modo enfoque), los avisos esperan; al terminar
        # se muestran todos, marcados como atrasados.
        self.en_pausa: Callable[[], bool] = lambda: False
        self._timer = QTimer(self, interval=intervalo_ms)
        self._timer.timeout.connect(self.revisar)
        self._timer.start()
        # Al abrir la app, avisar enseguida de lo que venció mientras estaba cerrada.
        QTimer.singleShot(1500, self.revisar)

    def revisar(self) -> None:
        if self.en_pausa():
            return
        vencidas = servicio.vencidas()
        for nota in vencidas:
            servicio.marcar_notificada(nota.id)
            self._mostrar(nota)
        if vencidas:
            self.notas_cambiaron.emit()

    def _mostrar(self, nota: Nota) -> None:
        alerta = AlertaRecordatorio(nota)
        alerta.cerrada.connect(self._al_cerrar)
        alerta.posponer.connect(self._posponer)
        self._alertas.append(alerta)
        self._reubicar()
        alerta.show()
        alerta.raise_()
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        voz().hablar(texto_voz(nota))

    def _posponer(self, nota_id: int, minutos: int) -> None:
        servicio.posponer(nota_id, minutos)
        self.notas_cambiaron.emit()

    def _al_cerrar(self, alerta: AlertaRecordatorio) -> None:
        if alerta in self._alertas:
            self._alertas.remove(alerta)
            self._reubicar()

    def _reubicar(self) -> None:
        """Apila las alertas en la esquina inferior derecha, la más antigua abajo."""
        pantalla = QGuiApplication.primaryScreen().availableGeometry()
        y = pantalla.bottom() - _MARGEN
        for alerta in self._alertas:
            alerta.adjustSize()
            y -= alerta.height()
            alerta.move(pantalla.right() - _MARGEN - alerta.width(), y)
            y -= _SEPARACION

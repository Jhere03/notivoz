"""Chateemos: escribirle a Notivoz. Es el mismo asistente que por voz (mismas
acciones, mismos límites y la misma seguridad), pero responde por escrito."""

import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services import ajustes
from app.services.asistente import ErrorAsistente, Respuesta
from app.ui.asistente_voz import ControladorIA, es_cierre
from app.ui.formato import partible

_LARGO_MAXIMO = 1000


class _Mensaje(QFrame):
    def __init__(self, texto: str, de_usuario: bool, error: bool = False):
        super().__init__()
        self.setObjectName("Fila")
        etiqueta = QLabel(partible(texto))
        etiqueta.setWordWrap(True)
        etiqueta.setTextFormat(Qt.TextFormat.PlainText)  # nunca interpretar HTML
        etiqueta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        etiqueta.setObjectName("MensajeUsuario" if de_usuario else ("MensajeError" if error else "MensajeNotivoz"))
        if len(texto) <= 2:  # un emoji: más grande
            fuente = etiqueta.font()
            fuente.setPointSize(20)
            etiqueta.setFont(fuente)
        # Ancho según el texto (sin pasar de 560): las frases cortas en una línea.
        ancho = QFontMetrics(etiqueta.font()).horizontalAdvance(texto) + 30
        etiqueta.setMinimumWidth(min(ancho, 560))
        etiqueta.setMaximumWidth(560)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if de_usuario:
            layout.addStretch()
        layout.addWidget(etiqueta)
        if not de_usuario:
            layout.addStretch()


class ChatView(QWidget):
    _respuesta = Signal(object)  # Respuesta
    _error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Lo conecta la ventana principal cuando crea el asistente de voz.
        self._controlador: ControladorIA | None = None
        self._esperando = False

        titulo = QLabel("Chateemos")
        titulo.setObjectName("TituloVista")
        resumen = QLabel(
            "Escríbele a Notivoz lo mismo que le dirías por voz: crear o eliminar tareas, "
            "recordatorios, consultar tus pendientes, abrir apps…"
        )
        resumen.setObjectName("Resumen")
        resumen.setWordWrap(True)

        self.aviso = QLabel("Activa el asistente con IA en Configuración para chatear con Notivoz.")
        self.aviso.setObjectName("Vacio")
        self.aviso.setWordWrap(True)

        self._lista = QWidget()
        self._lista.setObjectName("ListaNotas")
        self._columna = QVBoxLayout(self._lista)
        self._columna.setContentsMargins(4, 4, 10, 4)
        self._columna.setSpacing(10)
        self._columna.addStretch()
        self._scroll = QScrollArea()
        self._scroll.setObjectName("ScrollNotas")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(self._lista)

        self.escribiendo = QLabel("Notivoz está pensando…")
        self.escribiendo.setObjectName("Escribiendo")
        self.escribiendo.hide()

        self.entrada = QLineEdit()
        self.entrada.setPlaceholderText("Escribe aquí y pulsa Enter…")
        self.entrada.setMaxLength(_LARGO_MAXIMO)
        self.entrada.returnPressed.connect(self.enviar)
        self.btn_enviar = QPushButton("Enviar")
        self.btn_enviar.setObjectName("Primario")
        self.btn_enviar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_enviar.clicked.connect(self.enviar)
        fila = QHBoxLayout()
        fila.addWidget(self.entrada, stretch=1)
        fila.addWidget(self.btn_enviar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)
        layout.addWidget(titulo)
        layout.addWidget(resumen)
        layout.addWidget(self.aviso)
        layout.addWidget(self._scroll, stretch=1)
        layout.addWidget(self.escribiendo)
        layout.addLayout(fila)

        self._respuesta.connect(self._al_responder)
        self._error.connect(self._al_fallar)
        self._agregar("¡Hola! Soy Notivoz. ¿Qué hacemos hoy?", de_usuario=False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.actualizar()
        self.entrada.setFocus()

    def conectar(self, controlador: ControladorIA) -> None:
        self._controlador = controlador
        self.actualizar()

    def actualizar(self) -> None:
        disponible = self._controlador is not None and self._controlador.asistente.disponible()
        self.aviso.setVisible(not disponible)
        self.entrada.setEnabled(disponible and not self._esperando)
        self.btn_enviar.setEnabled(disponible and not self._esperando)

    # --- Envío ---

    def enviar(self) -> None:
        texto = " ".join(self.entrada.text().split())
        if not texto or self._esperando:
            return
        self.entrada.clear()
        self._agregar(texto, de_usuario=True)
        if es_cierre(texto):
            # «Gracias», «ok»…: una sonrisa, sin gastar IA.
            self._agregar(ajustes.frases_actuales().gesto(), de_usuario=False)
            return
        self._esperando = True
        self.escribiendo.show()
        self.actualizar()
        threading.Thread(target=self._pedir, args=(texto,), name="Chat", daemon=True).start()

    def _pedir(self, texto: str) -> None:
        try:
            asistente = self._controlador.asistente
            self._respuesta.emit(asistente.resolver_pendiente(texto) or asistente.responder(texto))
        except ErrorAsistente as error:
            self._error.emit(str(error))
        except Exception:
            self._error.emit("Algo falló al procesar tu mensaje.")

    def _al_responder(self, respuesta: Respuesta) -> None:
        self._terminar_espera()
        self._controlador.aplicar_efectos(respuesta)
        if respuesta.gesto == "gesto":
            self._agregar(ajustes.frases_actuales().gesto(), de_usuario=False)
        elif respuesta.texto and respuesta.efectos.hizo_algo:
            # Terminó lo que pediste: la confirmación con un emoji de su personalidad.
            self._agregar(f"{respuesta.texto} {ajustes.frases_actuales().gesto()}", de_usuario=False)
        elif respuesta.texto:
            self._agregar(respuesta.texto, de_usuario=False)
        elif respuesta.efectos.comandos_activados:
            self._agregar("Listo, activé el modo.", de_usuario=False)

    def _al_fallar(self, mensaje: str) -> None:
        self._terminar_espera()
        self._agregar(mensaje, de_usuario=False, error=True)

    def _terminar_espera(self) -> None:
        self._esperando = False
        self.escribiendo.hide()
        self.actualizar()
        self.entrada.setFocus()

    def _agregar(self, texto: str, de_usuario: bool, error: bool = False) -> None:
        self._columna.insertWidget(self._columna.count() - 1, _Mensaje(texto, de_usuario, error))
        # Bajar al último mensaje cuando ya se haya acomodado.
        QTimer.singleShot(30, lambda: self._scroll.verticalScrollBar().setValue(self._scroll.verticalScrollBar().maximum()))

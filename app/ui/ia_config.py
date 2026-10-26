"""Sección «Asistente con IA» de Configuración: clave, modelo de Whisper y gasto."""

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.services import ajustes, credenciales, transcripcion
from app.services.ajustes import Clave
from app.services.asistente import probar_clave
from app.services.escucha import NOMBRE_ACTIVACION


def _ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("Ayuda")
    etiqueta.setWordWrap(True)
    etiqueta.setTextFormat(Qt.TextFormat.PlainText)
    return etiqueta


def _boton(texto: str, objeto: str = "Secundario") -> QPushButton:
    boton = QPushButton(texto)
    boton.setObjectName(objeto)
    boton.setCursor(Qt.CursorShape.PointingHandCursor)
    return boton


class SeccionIA(QFrame):
    # Cambió algo que afecta a si la IA puede usarse (activación, clave, modelo).
    cambiada = Signal()
    _clave_probada = Signal(str, str)  # clave, error ("" si es válida)
    _descarga_progreso = Signal(int, int)
    _descarga_terminada = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Seccion")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 18)
        layout.setSpacing(12)
        titulo = QLabel("Asistente con IA")
        titulo.setObjectName("SeccionTitulo")
        descripcion = QLabel(
            f"Pide cosas con tus palabras: «{NOMBRE_ACTIVACION}, recuérdame pagar el internet el viernes "
            "a las 9», «¿qué tengo pendiente con ACME?», «abre Spotify». Usa Claude (Anthropic) "
            "para entender el pedido; tu voz se convierte en texto en tu propio equipo."
        )
        descripcion.setObjectName("Resumen")
        descripcion.setWordWrap(True)
        layout.addWidget(titulo)
        layout.addWidget(descripcion)

        self.activa = QCheckBox("Activar el asistente con IA")
        self.activa.setChecked(ajustes.obtener(Clave.IA_ACTIVA))
        self.activa.toggled.connect(self._cambiar_activa)
        layout.addWidget(self.activa)

        # --- Clave del API ---
        layout.addWidget(QLabel("Clave del API de Anthropic"))
        self.estado_clave = QLabel()
        self.estado_clave.setTextFormat(Qt.TextFormat.PlainText)
        self.clave = QLineEdit()
        self.clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.clave.setPlaceholderText("Pega aquí tu clave (sk-ant-…)")
        # Que no quede en el portapapeles ni se pueda copiar desde el campo.
        self.clave.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.btn_guardar_clave = _boton("Guardar clave", "Primario")
        self.btn_guardar_clave.clicked.connect(self._guardar_clave)
        self.clave.returnPressed.connect(self._guardar_clave)
        self.btn_borrar_clave = _boton("Borrar clave")
        self.btn_borrar_clave.clicked.connect(self._borrar_clave)
        fila_clave = QHBoxLayout()
        fila_clave.addWidget(self.clave, stretch=1)
        fila_clave.addWidget(self.btn_guardar_clave)
        fila_clave.addWidget(self.btn_borrar_clave)
        layout.addWidget(self.estado_clave)
        layout.addLayout(fila_clave)
        layout.addWidget(
            _ayuda(
                "Créala en console.anthropic.com → API Keys, solo para Notivoz, y pon allí un "
                "límite de gasto mensual. Se guarda cifrada en el Administrador de credenciales "
                "de Windows (solo tu cuenta puede leerla) y solo se envía a Anthropic. "
                "Notivoz no muestra la clave guardada."
            )
        )

        # --- Whisper ---
        layout.addWidget(QLabel("Reconocimiento de voz (Whisper)"))
        self.estado_whisper = QLabel()
        self.estado_whisper.setWordWrap(True)
        self.btn_whisper = _boton(f"Descargar Whisper (≈{transcripcion.TAMANO_APROX_MB} MB)")
        self.btn_whisper.clicked.connect(self._descargar_whisper)
        self.progreso = QProgressBar()
        self.progreso.hide()
        fila_whisper = QHBoxLayout()
        fila_whisper.addWidget(self.btn_whisper)
        fila_whisper.addWidget(self.progreso, stretch=1)
        layout.addWidget(self.estado_whisper)
        layout.addLayout(fila_whisper)

        layout.addWidget(
            _ayuda(
                "Si Notivoz te hace una pregunta, puedes contestarle sin decir «Notivoz», incluso "
                "mientras habla. Para eliminar algo siempre te pide confirmación: di «sí» o «no»."
            )
        )

        self._clave_probada.connect(self._al_probar_clave)
        self._descarga_progreso.connect(self._al_progresar)
        self._descarga_terminada.connect(self._al_terminar_descarga)
        self.actualizar()

    def actualizar(self) -> None:
        if credenciales.hay_clave():
            self.estado_clave.setText(f"✓  Clave guardada: {credenciales.pista()}")
            self.btn_borrar_clave.show()
        else:
            self.estado_clave.setText("Sin clave: el asistente no puede usarse.")
            self.btn_borrar_clave.hide()
        if transcripcion.instalado():
            self.estado_whisper.setText("✓  Whisper instalado (funciona sin internet).")
            self.btn_whisper.hide()
        else:
            self.estado_whisper.setText(
                "Notivoz necesita descargar una sola vez el modelo de Whisper para entender lo que dices."
            )
            self.btn_whisper.show()

    # --- Activación ---

    def _cambiar_activa(self, activa: bool) -> None:
        ajustes.guardar(Clave.IA_ACTIVA, activa)
        self.cambiada.emit()

    # --- Clave ---

    def _guardar_clave(self) -> None:
        clave = self.clave.text().strip()
        if not credenciales.formato_valido(clave):
            QMessageBox.warning(
                self, "Clave no válida", "Pega la clave completa de Anthropic; empieza con «sk-ant-»."
            )
            return
        self.btn_guardar_clave.setEnabled(False)
        self.btn_guardar_clave.setText("Comprobando…")

        def trabajar() -> None:
            try:
                error = probar_clave(clave) or ""
            except Exception:
                error = "No se pudo comprobar la clave."
            self._clave_probada.emit(clave, error)

        threading.Thread(target=trabajar, name="ProbarClave", daemon=True).start()

    def _al_probar_clave(self, clave: str, error: str) -> None:
        self.btn_guardar_clave.setEnabled(True)
        self.btn_guardar_clave.setText("Guardar clave")
        if error:
            QMessageBox.warning(self, "No se guardó la clave", error)
            return
        try:
            credenciales.guardar(clave)
        except Exception as fallo:
            QMessageBox.warning(self, "No se guardó la clave", str(fallo))
            return
        self.clave.clear()
        self.actualizar()
        self.cambiada.emit()

    def _borrar_clave(self) -> None:
        respuesta = QMessageBox.question(
            self,
            "Borrar clave",
            "¿Borrar la clave del API de este equipo? El asistente dejará de funcionar hasta que pongas otra.",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            credenciales.borrar()
            self.actualizar()
            self.cambiada.emit()

    # --- Whisper ---

    def _descargar_whisper(self) -> None:
        self.btn_whisper.setEnabled(False)
        self.btn_whisper.setText("Descargando…")
        self.progreso.setValue(0)
        self.progreso.show()

        def trabajar() -> None:
            try:
                transcripcion.descargar(lambda leidos, total: self._descarga_progreso.emit(leidos, total))
                self._descarga_terminada.emit("")
            except Exception as error:
                self._descarga_terminada.emit(str(error) or error.__class__.__name__)

        threading.Thread(target=trabajar, name="DescargaWhisper", daemon=True).start()

    def _al_progresar(self, leidos: int, total: int) -> None:
        if total:
            self.progreso.setValue(int(leidos * 100 / total))

    def _al_terminar_descarga(self, error: str) -> None:
        self.progreso.hide()
        self.btn_whisper.setEnabled(True)
        self.btn_whisper.setText(f"Descargar Whisper (≈{transcripcion.TAMANO_APROX_MB} MB)")
        if error:
            QMessageBox.warning(self, "No se pudo descargar", f"Inténtalo de nuevo.\n\n{error}")
        self.actualizar()
        self.cambiada.emit()

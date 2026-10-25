"""Modal con el correo de "tarea realizada" listo para copiar y pegar."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.data.models import Pendiente
from app.services import ajustes
from app.services.ajustes import Clave
from app.services.redaccion import RedactorCorreo


class CorreoDialog(QDialog):
    def __init__(self, pendiente: Pendiente, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correo de tarea realizada")
        self.setMinimumSize(600, 520)

        titulo = QLabel("Correo de tarea realizada")
        titulo.setObjectName("TituloVista")
        ayuda = QLabel("Revisa el texto, cópialo y pégalo en tu correo. Puedes editarlo aquí mismo.")
        ayuda.setObjectName("Resumen")
        ayuda.setWordWrap(True)

        # La firma usa el nombre de Configuración; si no hay, se pide aquí.
        self.firma = QLineEdit(ajustes.obtener(Clave.NOMBRE))
        self.firma.setPlaceholderText("Tu nombre para la firma")
        self.firma.editingFinished.connect(self._guardar_firma)
        fila_firma = QHBoxLayout()
        etiqueta_firma = QLabel("Firma")
        etiqueta_firma.setFixedWidth(60)
        fila_firma.addWidget(etiqueta_firma)
        fila_firma.addWidget(self.firma, stretch=1)
        self._fila_firma_visible = not self.firma.text().strip()

        self.asunto = QLineEdit()
        self.btn_copiar_asunto = self._boton_copiar(lambda: self.asunto.text())
        fila_asunto = QHBoxLayout()
        fila_asunto.addWidget(self.asunto, stretch=1)
        fila_asunto.addWidget(self.btn_copiar_asunto)

        self.cuerpo = QPlainTextEdit()
        self.btn_copiar_cuerpo = self._boton_copiar(lambda: self.cuerpo.toPlainText())
        fila_copiar_cuerpo = QHBoxLayout()
        fila_copiar_cuerpo.addStretch()
        fila_copiar_cuerpo.addWidget(self.btn_copiar_cuerpo)

        otra = QPushButton("↻  Otra versión")
        otra.setObjectName("Secundario")
        otra.setCursor(Qt.CursorShape.PointingHandCursor)
        otra.clicked.connect(self._generar)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addWidget(otra)
        botones.addStretch()
        botones.addWidget(cerrar)

        etiqueta_asunto = QLabel("Asunto")
        etiqueta_asunto.setObjectName("SeccionTitulo")
        etiqueta_cuerpo = QLabel("Mensaje")
        etiqueta_cuerpo.setObjectName("SeccionTitulo")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        layout.addWidget(titulo)
        layout.addWidget(ayuda)
        if self._fila_firma_visible:
            layout.addLayout(fila_firma)
        layout.addSpacing(4)
        layout.addWidget(etiqueta_asunto)
        layout.addLayout(fila_asunto)
        layout.addWidget(etiqueta_cuerpo)
        layout.addWidget(self.cuerpo, stretch=1)
        layout.addLayout(fila_copiar_cuerpo)
        layout.addLayout(botones)

        self._redactor = RedactorCorreo(pendiente, self.firma.text())
        self._pendiente = pendiente
        self._generar()

    def _boton_copiar(self, obtener_texto) -> QPushButton:
        boton = QPushButton("Copiar")
        boton.setCursor(Qt.CursorShape.PointingHandCursor)
        boton.setAutoDefault(False)
        boton.setFixedWidth(110)

        def copiar() -> None:
            QApplication.clipboard().setText(obtener_texto())
            boton.setText("✓ Copiado")
            QTimer.singleShot(1500, lambda: boton.setText("Copiar"))

        boton.clicked.connect(copiar)
        return boton

    def _guardar_firma(self) -> None:
        ajustes.guardar(Clave.NOMBRE, self.firma.text().strip())
        # La firma va al final del mensaje: rearmarlo con el nombre nuevo.
        self._redactor = RedactorCorreo(self._pendiente, self.firma.text())
        self._generar()

    def _generar(self) -> None:
        correo = self._redactor.otra_version()
        self.asunto.setText(correo.asunto)
        self.cuerpo.setPlainText(correo.cuerpo)

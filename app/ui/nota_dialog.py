"""Formulario para crear o editar una nota con recordatorio opcional."""

from datetime import datetime, timedelta

from PySide6.QtCore import QDate, QRegularExpression, Qt, QTime
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Nota
from app.services.notas import DatosNota
from app.ui.widgets import FechaEdit


class HoraEdit(QLineEdit):
    """Campo de hora HH:MM (24 horas)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setInputMask("00:00")
        self.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^([01]\d|2[0-3]):[0-5]\d$"), self)
        )
        self.setFixedWidth(90)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip("Hora en formato 24 h, por ejemplo 15:30")

    def hora(self) -> QTime | None:
        hora = QTime.fromString(self.text(), "HH:mm")
        return hora if hora.isValid() else None

    def setHora(self, hora: QTime) -> None:
        self.setText(hora.toString("HH:mm"))


class NotaDialog(QDialog):
    def __init__(self, nota: Nota | None = None, parent=None):
        super().__init__(parent)
        self._id = nota.id if nota else None
        self._recordatorio_original = nota.recordatorio if nota else None
        self.setWindowTitle("Editar nota" if nota else "Nueva nota")
        self.setMinimumWidth(500)

        self.titulo = QLineEdit()
        self.titulo.setPlaceholderText("Título de la nota")
        self.titulo.setMaxLength(200)

        self.contenido = QPlainTextEdit()
        self.contenido.setPlaceholderText("Escribe tu nota…")
        self.contenido.setFixedHeight(140)

        self.recordar = QCheckBox("Recordarme")
        self.recordar.toggled.connect(self._activar_recordatorio)

        self.fecha = FechaEdit()
        self.hora = HoraEdit()
        rapidos = QHBoxLayout()
        rapidos.setSpacing(6)
        for texto, minutos in (("En 10 min", 10), ("En 1 hora", 60)):
            boton = QPushButton(texto)
            boton.setObjectName("Rapido")
            boton.setAutoDefault(False)
            boton.clicked.connect(lambda _=False, m=minutos: self._en_minutos(m))
            rapidos.addWidget(boton)
        manana = QPushButton("Mañana 9:00")
        manana.setObjectName("Rapido")
        manana.setAutoDefault(False)
        manana.clicked.connect(self._manana)
        rapidos.addWidget(manana)
        rapidos.addStretch()

        fila_fecha = QHBoxLayout()
        fila_fecha.setSpacing(8)
        fila_fecha.addWidget(self.fecha, stretch=1)
        fila_fecha.addWidget(self.hora)

        aviso = QLabel("A esa hora Notivoz mostrará una alerta encima de todo y dirá «Recuerda: …».")
        aviso.setObjectName("Resumen")
        aviso.setWordWrap(True)

        self._bloque_recordatorio = QWidget()
        bloque = QVBoxLayout(self._bloque_recordatorio)
        bloque.setContentsMargins(0, 0, 0, 0)
        bloque.setSpacing(8)
        bloque.addLayout(fila_fecha)
        bloque.addLayout(rapidos)
        bloque.addWidget(aviso)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Título *", self.titulo)
        form.addRow("Nota", self.contenido)
        form.addRow("", self.recordar)
        form.addRow("Fecha y hora", self._bloque_recordatorio)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        guardar = botones.button(QDialogButtonBox.StandardButton.Save)
        guardar.setText("Guardar")
        guardar.setObjectName("Primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(botones)

        self._cargar(nota)
        self.titulo.setFocus()

    def _cargar(self, nota: Nota | None) -> None:
        if nota is not None:
            self.titulo.setText(nota.titulo)
            self.contenido.setPlainText(nota.contenido)
        if nota is not None and nota.recordatorio is not None:
            self._poner(nota.recordatorio)
            self.recordar.setChecked(True)
        else:
            self._en_minutos(60, redondear=True)
            self.recordar.setChecked(False)
        self._activar_recordatorio(self.recordar.isChecked())

    def _activar_recordatorio(self, activo: bool) -> None:
        self._bloque_recordatorio.setEnabled(activo)

    def _poner(self, dt: datetime) -> None:
        self.fecha.setDate(QDate(dt.year, dt.month, dt.day))
        self.hora.setHora(QTime(dt.hour, dt.minute))

    def _en_minutos(self, minutos: int, redondear: bool = False) -> None:
        dt = datetime.now() + timedelta(minutes=minutos)
        if redondear:
            # Siguiente múltiplo de 5 minutos, más cómodo para leer.
            dt += timedelta(minutes=(5 - dt.minute % 5) % 5)
        self._poner(dt)
        self.recordar.setChecked(True)

    def _manana(self) -> None:
        manana = datetime.now() + timedelta(days=1)
        self._poner(manana.replace(hour=9, minute=0))
        self.recordar.setChecked(True)

    def _recordatorio(self) -> datetime | None:
        if not self.recordar.isChecked():
            return None
        hora = self.hora.hora()
        if hora is None:
            return None
        q = self.fecha.date()
        return datetime(q.year(), q.month(), q.day(), hora.hour(), hora.minute())

    def _validar(self) -> None:
        if not self.titulo.text().strip():
            QMessageBox.warning(self, "Falta el título", "Escribe un título para la nota.")
            self.titulo.setFocus()
            return
        if self.recordar.isChecked():
            recordatorio = self._recordatorio()
            if recordatorio is None:
                QMessageBox.warning(self, "Hora no válida", "Escribe la hora en formato 24 h, por ejemplo 15:30.")
                self.hora.setFocus()
                return
            cambio = recordatorio != self._recordatorio_original
            if cambio and recordatorio <= datetime.now():
                QMessageBox.warning(
                    self, "La hora ya pasó", "Elige una fecha y hora futuras para el recordatorio."
                )
                self.hora.setFocus()
                return
        self.accept()

    def datos(self) -> DatosNota:
        return DatosNota(
            id=self._id,
            titulo=self.titulo.text(),
            contenido=self.contenido.toPlainText(),
            recordatorio=self._recordatorio(),
        )

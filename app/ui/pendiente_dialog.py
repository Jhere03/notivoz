"""Formulario para crear o editar una tarea (pendiente)."""

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.data.models import Cliente, Estado, Importancia, Pendiente
from app.services.pendientes import DatosPendiente
from app.ui.widgets import FechaEdit


class PendienteDialog(QDialog):
    def __init__(self, clientes: list[Cliente], pendiente: Pendiente | None = None, parent=None):
        super().__init__(parent)
        self._id = pendiente.id if pendiente else None
        self.setWindowTitle("Editar tarea" if pendiente else "Nueva tarea")
        self.setMinimumWidth(460)

        self.cliente = QComboBox()
        self.cliente.addItem("Sin cliente", None)
        for cliente in clientes:
            self.cliente.addItem(cliente.nombre, cliente.id)
        if not clientes:
            self.cliente.setToolTip("Agrega clientes con el botón «Clientes».")

        self.titulo = QLineEdit()
        self.titulo.setPlaceholderText("¿Qué hay que hacer?")
        self.titulo.setMaxLength(200)

        self.descripcion = QPlainTextEdit()
        self.descripcion.setPlaceholderText("Detalles, notas, enlaces…")
        self.descripcion.setFixedHeight(110)

        self.importancia = QComboBox()
        for nivel in Importancia:
            self.importancia.addItem(nivel.etiqueta, nivel)

        self.fecha = FechaEdit()

        self.estado = QComboBox()
        for estado in Estado:
            self.estado.addItem(estado.value, estado)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Cliente", self.cliente)
        form.addRow("Tarea *", self.titulo)
        form.addRow("Descripción", self.descripcion)
        form.addRow("Importancia", self.importancia)
        form.addRow("Fecha de ingreso", self.fecha)
        form.addRow("Estado", self.estado)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)

        nota = QLabel("* Campo obligatorio")
        nota.setObjectName("Resumen")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(nota)
        layout.addWidget(botones)

        self._cargar(pendiente)
        self.titulo.setFocus()

    def _cargar(self, p: Pendiente | None) -> None:
        if p is None:
            self.importancia.setCurrentIndex(self.importancia.findData(Importancia.MEDIA))
            self.fecha.setDate(QDate.currentDate())
            return
        self.cliente.setCurrentIndex(max(self.cliente.findData(p.cliente_id), 0))
        self.titulo.setText(p.titulo)
        self.descripcion.setPlainText(p.descripcion)
        self.importancia.setCurrentIndex(self.importancia.findData(Importancia(p.importancia)))
        self.fecha.setDate(QDate(p.fecha_ingreso.year, p.fecha_ingreso.month, p.fecha_ingreso.day))
        self.estado.setCurrentIndex(self.estado.findData(Estado(p.estado)))

    def _validar(self) -> None:
        if not self.titulo.text().strip():
            QMessageBox.warning(self, "Falta el título", "Escribe la tarea antes de guardar.")
            self.titulo.setFocus()
            return
        self.accept()

    def datos(self) -> DatosPendiente:
        q = self.fecha.date()
        return DatosPendiente(
            id=self._id,
            titulo=self.titulo.text(),
            descripcion=self.descripcion.toPlainText(),
            cliente_id=self.cliente.currentData(),
            importancia=self.importancia.currentData(),
            fecha_ingreso=date(q.year(), q.month(), q.day()),
            estado=self.estado.currentData(),
        )

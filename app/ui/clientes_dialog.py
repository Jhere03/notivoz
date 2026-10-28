"""Modal para agregar, editar y eliminar clientes."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services import clientes as servicio
from app.ui.iconos_menu import poner_icono

ID_ROLE = Qt.ItemDataRole.UserRole


class ClientesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clientes")
        self.setMinimumSize(480, 460)

        titulo = QLabel("Clientes")
        titulo.setObjectName("TituloVista")
        subtitulo = QLabel("Agrega, edita o elimina los clientes que asignas a tus tareas.")
        subtitulo.setObjectName("Resumen")

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Nombre del nuevo cliente")
        self.nombre.setMaxLength(120)
        self.nombre.returnPressed.connect(self.agregar)
        btn_agregar = QPushButton("Agregar")
        btn_agregar.setObjectName("Primario")
        poner_icono(btn_agregar, "mas", "primario")
        btn_agregar.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_agregar.setAutoDefault(False)
        btn_agregar.clicked.connect(self.agregar)

        fila_nuevo = QHBoxLayout()
        fila_nuevo.setSpacing(8)
        fila_nuevo.addWidget(self.nombre, stretch=1)
        fila_nuevo.addWidget(btn_agregar)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Cliente", "Tareas"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(38)
        header = self.tabla.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tabla.setColumnWidth(1, 80)
        self.tabla.doubleClicked.connect(lambda _: self.editar())
        self.tabla.itemSelectionChanged.connect(self._actualizar_botones)

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.clicked.connect(self.editar)
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.clicked.connect(self.eliminar)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        for boton in (self.btn_editar, self.btn_eliminar, btn_cerrar):
            boton.setAutoDefault(False)

        acciones = QHBoxLayout()
        acciones.addWidget(self.btn_editar)
        acciones.addWidget(self.btn_eliminar)
        acciones.addStretch()
        acciones.addWidget(btn_cerrar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(4)
        layout.addLayout(fila_nuevo)
        layout.addWidget(self.tabla, stretch=1)
        layout.addLayout(acciones)

        atajo = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.tabla)
        atajo.setContext(Qt.ShortcutContext.WidgetShortcut)
        atajo.activated.connect(self.eliminar)

        self.recargar()
        self.nombre.setFocus()

    def recargar(self, seleccionar: int | None = None) -> None:
        filas = servicio.listar_con_total()
        self.tabla.setRowCount(len(filas))
        for fila, (cliente, total) in enumerate(filas):
            item_nombre = QTableWidgetItem(cliente.nombre)
            item_nombre.setData(ID_ROLE, cliente.id)
            item_total = QTableWidgetItem(str(total))
            self.tabla.setItem(fila, 0, item_nombre)
            self.tabla.setItem(fila, 1, item_total)
            if cliente.id == seleccionar:
                self.tabla.selectRow(fila)
        self._actualizar_botones()

    def _seleccionado(self) -> tuple[int, str, int] | None:
        filas = self.tabla.selectionModel().selectedRows()
        if not filas:
            return None
        fila = filas[0].row()
        item = self.tabla.item(fila, 0)
        return item.data(ID_ROLE), item.text(), int(self.tabla.item(fila, 1).text())

    def _actualizar_botones(self) -> None:
        hay = self._seleccionado() is not None
        self.btn_editar.setEnabled(hay)
        self.btn_eliminar.setEnabled(hay)

    def agregar(self) -> None:
        try:
            nuevo_id = servicio.crear(self.nombre.text())
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo agregar", str(error))
            self.nombre.setFocus()
            return
        self.nombre.clear()
        self.recargar(seleccionar=nuevo_id)
        self.nombre.setFocus()

    def editar(self) -> None:
        seleccionado = self._seleccionado()
        if seleccionado is None:
            return
        cliente_id, nombre_actual, _ = seleccionado
        nombre, ok = QInputDialog.getText(
            self, "Editar cliente", "Nombre del cliente:", text=nombre_actual
        )
        if not ok:
            return
        try:
            servicio.renombrar(cliente_id, nombre)
        except ValueError as error:
            QMessageBox.warning(self, "No se pudo editar", str(error))
            return
        self.recargar(seleccionar=cliente_id)

    def eliminar(self) -> None:
        seleccionado = self._seleccionado()
        if seleccionado is None:
            return
        cliente_id, nombre, total = seleccionado
        mensaje = f"¿Eliminar al cliente «{nombre}»?"
        if total == 1:
            mensaje += "\nSu tarea quedará sin cliente, pero no se borra."
        elif total > 1:
            mensaje += f"\nSus {total} tareas quedarán sin cliente, pero no se borran."
        respuesta = QMessageBox.question(
            self,
            "Eliminar cliente",
            mensaje,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            servicio.eliminar(cliente_id)
            self.recargar()

"""Vista principal de pendientes: filtros, tabla y acciones."""

from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Estado, Importancia
from app.services import clientes as servicio_clientes
from app.services import pendientes as servicio
from app.services.pendientes import FiltroPendientes
from app.ui import theme
from app.ui.clientes_dialog import ClientesDialog
from app.ui.pendiente_dialog import PendienteDialog
from app.ui.widgets import EstadoChip
from app.ui.pendientes_model import (
    COL_CLIENTE,
    COL_DESCRIPCION,
    COL_ESTADO,
    COL_IMPORTANCIA,
    COL_INGRESO,
    COL_TITULO,
    ID_ROLE,
    SORT_ROLE,
    EtiquetaDelegate,
    PendientesModel,
)


class PendientesView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Pendientes")
        titulo.setObjectName("TituloVista")

        # Contadores por estado; clic en uno filtra la tabla por ese estado.
        etiquetas = {
            Estado.PENDIENTE: ("Pendiente", "Pendientes"),
            Estado.EN_PROCESO: ("En proceso", "En proceso"),
            Estado.REALIZADO: ("Realizado", "Realizados"),
        }
        self.chips: dict[Estado, EstadoChip] = {}
        contadores = QHBoxLayout()
        contadores.setSpacing(8)
        for estado, (singular, plural) in etiquetas.items():
            chip = EstadoChip(singular, plural, theme.COLOR_ESTADO[estado])
            chip.clicked.connect(lambda e=estado: self._filtrar_por_estado(e))
            self.chips[estado] = chip
            contadores.addWidget(chip)
        contadores.addStretch()

        self.btn_clientes = QPushButton("Clientes")
        self.btn_clientes.setObjectName("Secundario")
        self.btn_clientes.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clientes.setToolTip("Agregar, editar o eliminar clientes")
        self.btn_clientes.clicked.connect(self.gestionar_clientes)

        self.btn_nuevo = QPushButton("+  Nueva tarea")
        self.btn_nuevo.setObjectName("Primario")
        self.btn_nuevo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nuevo.setToolTip("Nueva tarea (Ctrl+N)")
        self.btn_nuevo.clicked.connect(self.nuevo)

        encabezado = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(10)
        textos.addWidget(titulo)
        textos.addLayout(contadores)
        encabezado.addLayout(textos)
        encabezado.addStretch()
        encabezado.addWidget(self.btn_clientes, alignment=Qt.AlignmentFlag.AlignBottom)
        encabezado.addSpacing(8)
        encabezado.addWidget(self.btn_nuevo, alignment=Qt.AlignmentFlag.AlignBottom)

        # Filtros
        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar por pendiente, descripción o cliente…")
        self.buscar.setClearButtonEnabled(True)
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.recargar)
        self.buscar.textChanged.connect(self._debounce.start)

        self.f_estado = QComboBox()
        self.f_estado.addItem("Todos los estados", None)
        for estado in Estado:
            self.f_estado.addItem(estado.value, estado)

        self.f_importancia = QComboBox()
        self.f_importancia.addItem("Toda importancia", None)
        for nivel in reversed(Importancia):
            self.f_importancia.addItem(nivel.etiqueta, nivel)

        self.f_cliente = QComboBox()
        self.f_cliente.setMinimumWidth(170)

        for combo in (self.f_estado, self.f_importancia, self.f_cliente):
            combo.currentIndexChanged.connect(self.recargar)

        filtros = QHBoxLayout()
        filtros.setSpacing(8)
        filtros.addWidget(self.buscar, stretch=1)
        filtros.addWidget(self.f_estado)
        filtros.addWidget(self.f_importancia)
        filtros.addWidget(self.f_cliente)

        # Tabla
        self.modelo = PendientesModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.modelo)
        self.proxy.setSortRole(SORT_ROLE)

        self.tabla = QTableView()
        self.tabla.setModel(self.proxy)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        self.tabla.setShowGrid(False)
        self.tabla.setWordWrap(False)
        self.tabla.verticalHeader().hide()
        self.tabla.verticalHeader().setDefaultSectionSize(42)
        self.tabla.setSortingEnabled(True)
        self.tabla.horizontalHeader().setSortIndicatorClearable(True)
        self.tabla.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.tabla.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabla.customContextMenuRequested.connect(self._menu_contextual)
        self.tabla.doubleClicked.connect(lambda _: self.editar())

        self.tabla.setItemDelegateForColumn(
            COL_IMPORTANCIA, EtiquetaDelegate(theme.COLOR_IMPORTANCIA, self.tabla)
        )
        self.tabla.setItemDelegateForColumn(
            COL_ESTADO, EtiquetaDelegate(theme.COLOR_ESTADO, self.tabla)
        )

        header = self.tabla.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_DESCRIPCION, QHeaderView.ResizeMode.Stretch)
        for col, ancho in (
            (COL_CLIENTE, 170),
            (COL_TITULO, 280),
            (COL_IMPORTANCIA, 120),
            (COL_INGRESO, 110),
            (COL_ESTADO, 130),
        ):
            self.tabla.setColumnWidth(col, ancho)

        self.vacio = QLabel()
        self.vacio.setObjectName("Vacio")
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)

        contenedor = QWidget()
        self._pila = QStackedLayout(contenedor)
        self._pila.addWidget(self.tabla)
        self._pila.addWidget(self.vacio)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)
        layout.addLayout(encabezado)
        layout.addLayout(filtros)
        layout.addWidget(contenedor, stretch=1)

        QShortcut(QKeySequence.StandardKey.New, self, activated=self.nuevo)
        for tecla, accion in (
            (QKeySequence(QKeySequence.StandardKey.Delete), self.eliminar),
            (QKeySequence(Qt.Key.Key_Return), self.editar),
        ):
            atajo = QShortcut(tecla, self.tabla, activated=accion)
            atajo.setContext(Qt.ShortcutContext.WidgetShortcut)

        self._recargar_clientes()
        self.recargar()

    # --- Datos ---------------------------------------------------------------

    def _filtro(self) -> FiltroPendientes:
        return FiltroPendientes(
            texto=self.buscar.text(),
            estado=self.f_estado.currentData(),
            importancia=self.f_importancia.currentData(),
            cliente_id=self.f_cliente.currentData(),
        )

    def recargar(self) -> None:
        seleccionado = self._id_seleccionado()
        filtro = self._filtro()
        filas = servicio.listar(filtro)
        self.modelo.set_pendientes(filas)
        self._actualizar_resumen()

        if filas:
            self._pila.setCurrentWidget(self.tabla)
        else:
            self.vacio.setText(
                "Ningún pendiente coincide con los filtros."
                if filtro.activo
                else "Aún no tienes pendientes.\nPulsa «+ Nueva tarea» para agregar la primera."
            )
            self._pila.setCurrentWidget(self.vacio)

        if seleccionado is not None:
            self._seleccionar(seleccionado)

    def _recargar_clientes(self) -> None:
        actual = self.f_cliente.currentData()
        self.f_cliente.blockSignals(True)
        self.f_cliente.clear()
        self.f_cliente.addItem("Todos los clientes", None)
        for cliente in servicio_clientes.listar():
            self.f_cliente.addItem(cliente.nombre, cliente.id)
        indice = self.f_cliente.findData(actual)
        self.f_cliente.setCurrentIndex(max(indice, 0))
        self.f_cliente.blockSignals(False)

    def _actualizar_resumen(self) -> None:
        conteo = servicio.resumen()
        filtrado = self.f_estado.currentData()
        for estado, chip in self.chips.items():
            chip.set_valor(conteo[estado])
            chip.set_activo(filtrado == estado)

    def _filtrar_por_estado(self, estado: Estado) -> None:
        """Clic en un contador: filtra por ese estado, o quita el filtro si ya estaba."""
        indice = 0 if self.f_estado.currentData() == estado else self.f_estado.findData(estado)
        self.f_estado.setCurrentIndex(indice)

    # --- Selección -----------------------------------------------------------

    def _id_seleccionado(self) -> int | None:
        filas = self.tabla.selectionModel().selectedRows()
        return filas[0].data(ID_ROLE) if filas else None

    def _seleccionar(self, pendiente_id: int) -> None:
        for fila in range(self.proxy.rowCount()):
            indice = self.proxy.index(fila, 0)
            if indice.data(ID_ROLE) == pendiente_id:
                self.tabla.selectRow(fila)
                self.tabla.scrollTo(indice)
                return

    # --- Acciones ------------------------------------------------------------

    def nuevo(self) -> None:
        self._abrir_formulario(None)

    def editar(self) -> None:
        pendiente_id = self._id_seleccionado()
        if pendiente_id is not None:
            self._abrir_formulario(pendiente_id)

    def _abrir_formulario(self, pendiente_id: int | None) -> None:
        pendiente = servicio.obtener(pendiente_id) if pendiente_id is not None else None
        dialogo = PendienteDialog(servicio_clientes.listar(), pendiente, self)
        if dialogo.exec():
            try:
                nuevo_id = servicio.guardar(dialogo.datos())
            except ValueError as error:
                QMessageBox.warning(self, "No se pudo guardar", str(error))
                return
            self.recargar()
            self._seleccionar(nuevo_id)

    def gestionar_clientes(self) -> None:
        ClientesDialog(self).exec()
        # Los nombres pudieron cambiar o borrarse: refrescar filtro y tabla.
        self._recargar_clientes()
        self.recargar()

    def cambiar_estado(self, estado: Estado) -> None:
        pendiente_id = self._id_seleccionado()
        if pendiente_id is not None:
            servicio.cambiar_estado(pendiente_id, estado)
            self.recargar()

    def eliminar(self) -> None:
        pendiente_id = self._id_seleccionado()
        if pendiente_id is None:
            return
        pendiente = servicio.obtener(pendiente_id)
        if pendiente is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Eliminar pendiente",
            f"¿Eliminar «{pendiente.titulo}»?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            servicio.eliminar(pendiente_id)
            self.recargar()

    def _menu_contextual(self, pos) -> None:
        indice = self.tabla.indexAt(pos)
        if not indice.isValid():
            return
        self.tabla.selectRow(indice.row())

        menu = QMenu(self)
        menu.addAction("Editar…", self.editar)
        marcar = menu.addMenu("Marcar como")
        for estado in Estado:
            accion = QAction(estado.value, marcar)
            accion.triggered.connect(lambda _=False, e=estado: self.cambiar_estado(e))
            marcar.addAction(accion)
        menu.addSeparator()
        menu.addAction("Eliminar", self.eliminar)
        menu.exec(self.tabla.viewport().mapToGlobal(pos))

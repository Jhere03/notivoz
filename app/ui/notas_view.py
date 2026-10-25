"""Vista de notas: tarjetas con su recordatorio, búsqueda y filtros."""

from datetime import date

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Nota
from app.services import notas as servicio
from app.services.notas import FiltroNotas
from app.ui.formato import fecha_hora_corta, tiempo_restante
from app.ui.nota_dialog import NotaDialog
from app.ui.widgets import FechaEdit

_MAX_VISTA_PREVIA = 260


class NotaCard(QFrame):
    editar = Signal(int)
    eliminar = Signal(int)

    def __init__(self, nota: Nota, parent=None):
        super().__init__(parent)
        self.nota_id = nota.id
        self.setObjectName("NotaCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Doble clic para editar")

        titulo = QLabel(nota.titulo)
        titulo.setObjectName("NotaTitulo")
        titulo.setWordWrap(True)

        arriba = QHBoxLayout()
        arriba.setSpacing(10)
        arriba.addWidget(titulo, stretch=1)
        arriba.addWidget(self._badge(nota), alignment=Qt.AlignmentFlag.AlignTop)
        for texto, senal in (("Editar", self.editar), ("Eliminar", self.eliminar)):
            boton = QPushButton(texto)
            boton.setObjectName("Enlace")
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(lambda _=False, s=senal: s.emit(self.nota_id))
            arriba.addWidget(boton, alignment=Qt.AlignmentFlag.AlignTop)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 14)
        layout.setSpacing(6)
        layout.addLayout(arriba)

        if nota.contenido:
            vista = nota.contenido
            if len(vista) > _MAX_VISTA_PREVIA:
                vista = vista[:_MAX_VISTA_PREVIA].rstrip() + "…"
            contenido = QLabel(vista)
            contenido.setObjectName("NotaContenido")
            contenido.setWordWrap(True)
            layout.addWidget(contenido)

    @staticmethod
    def _badge(nota: Nota) -> QLabel:
        if nota.recordatorio is None:
            badge = QLabel(f"Creada · {fecha_hora_corta(nota.creado_en)}")
            badge.setObjectName("BadgeCreada")
        elif servicio.es_proxima(nota):
            badge = QLabel(f"🔔  {fecha_hora_corta(nota.recordatorio)}")
            badge.setObjectName("BadgeProximo")
            badge.setToolTip(f"Te avisará {tiempo_restante(nota.recordatorio)}")
        else:
            badge = QLabel(f"✓  Avisada · {fecha_hora_corta(nota.recordatorio)}")
            badge.setObjectName("BadgeAvisado")
        return badge

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.editar.emit(self.nota_id)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Editar…", lambda: self.editar.emit(self.nota_id))
        menu.addSeparator()
        menu.addAction("Eliminar", lambda: self.eliminar.emit(self.nota_id))
        menu.exec(event.globalPos())


class NotasView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Notas")
        titulo.setObjectName("TituloVista")
        self.resumen = QLabel()
        self.resumen.setObjectName("Resumen")

        self.btn_nueva = QPushButton("+  Nueva nota")
        self.btn_nueva.setObjectName("Primario")
        self.btn_nueva.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nueva.clicked.connect(self.nueva)

        encabezado = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo)
        textos.addWidget(self.resumen)
        encabezado.addLayout(textos)
        encabezado.addStretch()
        encabezado.addWidget(self.btn_nueva, alignment=Qt.AlignmentFlag.AlignBottom)

        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar en tus notas…")
        self.buscar.setClearButtonEnabled(True)
        self._debounce = QTimer(self, singleShot=True, interval=250)
        self._debounce.timeout.connect(self.recargar)
        self.buscar.textChanged.connect(self._debounce.start)

        self.filtro = QComboBox()
        for opcion in FiltroNotas:
            self.filtro.addItem(opcion.value, opcion)
        self.filtro.currentIndexChanged.connect(self.recargar)

        # Fecha del recordatorio o, si no tiene, la de creación.
        self.f_fecha = FechaEdit(opcional=True, placeholder="Cualquier fecha")
        self.f_fecha.setToolTip("Filtra por la fecha del recordatorio o, si no tiene, la de creación")
        self.f_fecha.setFixedWidth(190)
        self.f_fecha.fechaCambiada.connect(self.recargar)

        filtros = QHBoxLayout()
        filtros.setSpacing(8)
        filtros.addWidget(self.buscar, stretch=1)
        filtros.addWidget(self.f_fecha)
        filtros.addWidget(self.filtro)

        self._lista = QWidget()
        self._lista.setObjectName("ListaNotas")
        self._layout_lista = QVBoxLayout(self._lista)
        self._layout_lista.setContentsMargins(0, 0, 6, 0)
        self._layout_lista.setSpacing(10)

        scroll = QScrollArea()
        scroll.setObjectName("ScrollNotas")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._lista)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)
        layout.addLayout(encabezado)
        layout.addLayout(filtros)
        layout.addWidget(scroll, stretch=1)

        # Refresca cada minuto los textos relativos ("Hoy", "en 5 min"…).
        self._reloj = QTimer(self, interval=60_000)
        self._reloj.timeout.connect(self.recargar)
        self._reloj.start()

        self.recargar()

    def recargar(self) -> None:
        q = self.f_fecha.date()
        fecha = date(q.year(), q.month(), q.day()) if q.isValid() else None
        notas = servicio.listar(self.buscar.text(), self.filtro.currentData(), fecha)

        while self._layout_lista.count():
            item = self._layout_lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Ocultarlo ya: deleteLater lo borra después y se vería encimado.
                widget.hide()
                widget.deleteLater()

        for nota in notas:
            card = NotaCard(nota)
            card.editar.connect(self.editar)
            card.eliminar.connect(self.eliminar)
            self._layout_lista.addWidget(card)

        if not notas:
            filtrando = (
                bool(self.buscar.text().strip())
                or self.filtro.currentIndex() > 0
                or fecha is not None
            )
            vacio = QLabel(
                "Ninguna nota coincide con la búsqueda."
                if filtrando
                else "Aún no tienes notas.\nPulsa «+ Nueva nota» para escribir la primera."
            )
            vacio.setObjectName("Vacio")
            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vacio.setMinimumHeight(260)
            self._layout_lista.addWidget(vacio)
        self._layout_lista.addStretch()

        self._actualizar_resumen()

    def _actualizar_resumen(self) -> None:
        todas = servicio.listar()
        proximas = [n for n in todas if servicio.es_proxima(n)]
        texto = f"{len(todas)} nota{'s' if len(todas) != 1 else ''}"
        if proximas:
            siguiente = proximas[0].recordatorio
            texto += (
                f"  ·  {len(proximas)} recordatorio{'s' if len(proximas) != 1 else ''} pendiente"
                f"{'s' if len(proximas) != 1 else ''}  ·  el próximo {tiempo_restante(siguiente)}"
            )
        self.resumen.setText(texto)

    def nueva(self) -> None:
        self._abrir_formulario(None)

    def editar(self, nota_id: int) -> None:
        self._abrir_formulario(nota_id)

    def _abrir_formulario(self, nota_id: int | None) -> None:
        nota = servicio.obtener(nota_id) if nota_id is not None else None
        dialogo = NotaDialog(nota, self)
        if dialogo.exec():
            try:
                servicio.guardar(dialogo.datos())
            except ValueError as error:
                QMessageBox.warning(self, "No se pudo guardar", str(error))
                return
            self.recargar()

    def eliminar(self, nota_id: int) -> None:
        nota = servicio.obtener(nota_id)
        if nota is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Eliminar nota",
            f"¿Eliminar la nota «{nota.titulo}»?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            servicio.eliminar(nota_id)
            self.recargar()

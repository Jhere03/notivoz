"""Modelo de tabla de pendientes y delegados que dibujan las etiquetas de color."""

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QToolTip,
)

from app.data.models import Estado, Importancia, Pendiente
from app.ui import theme
from app.ui.ver_dialog import dibujar_ojo

COLUMNAS = ["Cliente", "Pendiente", "Descripción", "Importancia", "Ingreso", "Estado", "Culminado", ""]
(
    COL_CLIENTE,
    COL_TITULO,
    COL_DESCRIPCION,
    COL_IMPORTANCIA,
    COL_INGRESO,
    COL_ESTADO,
    COL_CULMINADO,
    COL_VER,  # botón con un ojo: ver la tarea completa
) = range(len(COLUMNAS))

ID_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
# Importancia que Notivoz sugiere (etiqueta) o None.
SUGERENCIA_ROLE = Qt.ItemDataRole.UserRole + 2

_ORDEN_ESTADO = {Estado.EN_PROCESO: 0, Estado.PENDIENTE: 1, Estado.REALIZADO: 2}

type _Index = QModelIndex | QPersistentModelIndex


class PendientesModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas: list[Pendiente] = []
        self._sugerencias: dict[int, Importancia] = {}

    def set_pendientes(
        self, filas: list[Pendiente], sugerencias: dict[int, Importancia] | None = None
    ) -> None:
        self.beginResetModel()
        self._filas = filas
        self._sugerencias = sugerencias or {}
        self.endResetModel()

    def rowCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._filas)

    def columnCount(self, parent: _Index = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNAS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNAS[section]
        return None

    def data(self, index: _Index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        p = self._filas[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._texto(p, col)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._ayuda(p, col)
        if role == SORT_ROLE:
            return self._orden(p, col)
        if role == ID_ROLE:
            return p.id
        if role == SUGERENCIA_ROLE and col == COL_IMPORTANCIA:
            sugerida = self._sugerencias.get(p.id)
            return sugerida.etiqueta if sugerida else None
        realizado = p.estado == Estado.REALIZADO
        if role == Qt.ItemDataRole.ForegroundRole and realizado:
            return QColor(theme.TEXTO_SUAVE)
        if role == Qt.ItemDataRole.FontRole and realizado and col == COL_TITULO:
            font = QFont()
            font.setStrikeOut(True)
            return font
        return None

    def _ayuda(self, p: Pendiente, col: int) -> str | None:
        if col == COL_DESCRIPCION and p.descripcion:
            return p.descripcion
        if col == COL_TITULO:
            return p.titulo
        if col == COL_VER:
            return "Ver la tarea completa"
        if col == COL_IMPORTANCIA and p.id in self._sugerencias:
            return (
                f"Notivoz sugiere subirla a «{self._sugerencias[p.id].etiqueta}»: "
                "lleva tiempo esperando. Clic derecho → Subir importancia."
            )
        return None

    @staticmethod
    def _texto(p: Pendiente, col: int) -> str:
        match col:
            case 0:
                return p.cliente.nombre if p.cliente else "—"
            case 1:
                return p.titulo
            case 2:
                return p.descripcion.splitlines()[0] if p.descripcion else ""
            case 3:
                return Importancia(p.importancia).etiqueta
            case 4:
                return p.fecha_ingreso.strftime("%d/%m/%Y")
            case 5:
                return p.estado
            case 6:
                return p.fecha_realizado.strftime("%d/%m/%Y") if p.fecha_realizado else ""
        return ""

    @staticmethod
    def _orden(p: Pendiente, col: int):
        match col:
            case 0:
                return p.cliente.nombre.lower() if p.cliente else "￿"
            case 1:
                return p.titulo.lower()
            case 2:
                return p.descripcion.lower()
            case 3:
                return p.importancia
            case 4:
                return p.fecha_ingreso.toordinal()
            case 5:
                return _ORDEN_ESTADO[Estado(p.estado)]
            case 6:
                return p.fecha_realizado.timestamp() if p.fecha_realizado else 0.0
        return None


class EtiquetaDelegate(QStyledItemDelegate):
    """Dibuja el texto de la celda como una etiqueta redondeada de color."""

    def __init__(self, colores: dict[str, str], parent=None):
        super().__init__(parent)
        self._colores = colores

    def _rect_etiqueta(self, option: QStyleOptionViewItem, texto: str) -> QRectF:
        fm = option.fontMetrics
        ancho = fm.horizontalAdvance(texto) + 22
        alto = fm.height() + 8
        return QRectF(option.rect.x() + 8, option.rect.center().y() - alto / 2 + 1, ancho, alto)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        texto = index.data(Qt.ItemDataRole.DisplayRole) or ""

        # Fondo de la celda (selección, filas alternas) sin el texto.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        color = QColor(self._colores.get(texto, theme.TEXTO_SUAVE))
        fondo = QColor(color)
        fondo.setAlpha(38)
        rect = self._rect_etiqueta(option, texto)
        alto = rect.height()

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fondo)
        painter.drawRoundedRect(rect, alto / 2, alto / 2)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, texto)
        self.dibujar_extra(painter, option, index, rect)
        painter.restore()

    def dibujar_extra(self, painter: QPainter, option, index, etiqueta: QRectF) -> None:
        """Para que las subclases dibujen algo junto a la etiqueta."""


class ImportanciaDelegate(EtiquetaDelegate):
    """Etiqueta de importancia + una flecha ⬆ si Notivoz sugiere subirla."""

    def dibujar_extra(self, painter: QPainter, option, index, etiqueta: QRectF) -> None:
        if not index.data(SUGERENCIA_ROLE):
            return
        painter.setPen(QColor(theme.ACENTO_HOVER))
        fuente = painter.font()
        fuente.setBold(True)
        painter.setFont(fuente)
        flecha = QRectF(etiqueta.right() + 6, etiqueta.top(), 16, etiqueta.height())
        painter.drawText(flecha, Qt.AlignmentFlag.AlignCenter, "↑")


class EstadoDelegate(EtiquetaDelegate):
    """Etiqueta de estado + icono de correo ✉ en las tareas realizadas.
    Al pasar el cursor el sobre se rellena y crece; al hacer clic emite
    `correo_pedido` con el índice de la fila."""

    correo_pedido = Signal(QModelIndex)

    _ANCHO_ICONO = 18
    _ALTO_ICONO = 13
    _ESCALA_HOVER = 1.3

    def __init__(self, colores: dict[str, str], vista: QAbstractItemView):
        super().__init__(colores, vista)
        self._vista = vista
        self._fila_hover: int | None = None
        # Para saber cuándo el cursor está sobre el sobre (y cuándo se va).
        vista.setMouseTracking(True)
        vista.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Leave):
            fila = None
            if event.type() == QEvent.Type.MouseMove:
                fila = self._fila_bajo_cursor(event.position())
            if fila != self._fila_hover:
                self._fila_hover = fila
                cursor = Qt.CursorShape.PointingHandCursor if fila is not None else Qt.CursorShape.ArrowCursor
                self._vista.viewport().setCursor(cursor)
                self._vista.viewport().update()
        return False

    def _fila_bajo_cursor(self, posicion: QPointF) -> int | None:
        indice = self._vista.indexAt(posicion.toPoint())
        if not indice.isValid() or indice.column() != COL_ESTADO:
            return None
        opcion = QStyleOptionViewItem()
        opcion.rect = self._vista.visualRect(indice)
        opcion.fontMetrics = self._vista.fontMetrics()
        rect = self._rect_icono(opcion, indice)
        return indice.row() if rect is not None and rect.adjusted(-4, -4, 4, 4).contains(posicion) else None

    def _rect_icono(self, option: QStyleOptionViewItem, index) -> QRectF | None:
        texto = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if texto != Estado.REALIZADO:
            return None
        etiqueta = self._rect_etiqueta(option, texto)
        return QRectF(
            etiqueta.right() + 10,
            etiqueta.center().y() - self._ALTO_ICONO / 2,
            self._ANCHO_ICONO,
            self._ALTO_ICONO,
        )

    def dibujar_extra(self, painter: QPainter, option, index, etiqueta: QRectF) -> None:
        rect = self._rect_icono(option, index)
        if rect is None:
            return
        hover = index.row() == self._fila_hover
        if hover:
            # Más grande, desde el centro.
            centro = rect.center()
            ancho, alto = rect.width() * self._ESCALA_HOVER, rect.height() * self._ESCALA_HOVER
            rect = QRectF(centro.x() - ancho / 2, centro.y() - alto / 2, ancho, alto)
        lapiz = QPen(QColor(theme.ACENTO_HOVER), 1.6)
        lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(lapiz)
        painter.setBrush(QColor(theme.ACENTO) if hover else Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 2, 2)
        # La "V" de la solapa del sobre (blanca sobre el relleno morado).
        if hover:
            lapiz.setColor(QColor("white"))
            painter.setPen(lapiz)
        vertice = QPointF(rect.center().x(), rect.center().y() + 1)
        painter.drawLine(rect.topLeft(), vertice)
        painter.drawLine(rect.topRight(), vertice)

    def editorEvent(self, event, model, option, index) -> bool:
        rect = self._rect_icono(option, index)
        if (
            rect is not None
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and rect.adjusted(-4, -4, 4, 4).contains(event.position())
        ):
            self.correo_pedido.emit(QModelIndex(index))
            return True
        return super().editorEvent(event, model, option, index)

    def helpEvent(self, event, view, option, index) -> bool:
        rect = self._rect_icono(option, index)
        if rect is not None and rect.adjusted(-4, -4, 4, 4).contains(event.pos()):
            QToolTip.showText(event.globalPos(), "Redactar correo de tarea realizada", view)
            return True
        return super().helpEvent(event, view, option, index)


class VerDelegate(QStyledItemDelegate):
    """El botón con un ojo de cada fila: al pasar el cursor se rellena y crece;
    al hacer clic emite `ver_pedido` con el índice de la fila."""

    ver_pedido = Signal(QModelIndex)

    _TAMANO = 20
    _ESCALA_HOVER = 1.2

    def __init__(self, vista: QAbstractItemView):
        super().__init__(vista)
        self._vista = vista
        self._fila_hover: int | None = None
        vista.setMouseTracking(True)
        vista.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.Leave):
            fila = None
            if event.type() == QEvent.Type.MouseMove:
                indice = self._vista.indexAt(event.position().toPoint())
                if indice.isValid() and indice.column() == COL_VER:
                    fila = indice.row()
            if fila != self._fila_hover:
                # (Si el cursor salió de esta columna, el delegado del estado decide el cursor.)
                if fila is not None or self._fila_hover is not None:
                    cursor = Qt.CursorShape.PointingHandCursor if fila is not None else Qt.CursorShape.ArrowCursor
                    self._vista.viewport().setCursor(cursor)
                self._fila_hover = fila
                self._vista.viewport().update()
        return False

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        hover = index.row() == self._fila_hover
        tamano = self._TAMANO * (self._ESCALA_HOVER if hover else 1)
        centro = QRectF(option.rect).center()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if hover:
            painter.setPen(Qt.PenStyle.NoPen)
            fondo = QColor(theme.ACENTO)
            fondo.setAlpha(45)
            painter.setBrush(fondo)
            painter.drawEllipse(centro, tamano * 0.85, tamano * 0.85)
        rect = QRectF(centro.x() - tamano / 2, centro.y() - tamano / 2, tamano, tamano)
        dibujar_ojo(painter, rect, QColor(theme.ACENTO_HOVER), relleno=hover)
        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self.ver_pedido.emit(QModelIndex(index))
            return True
        return super().editorEvent(event, model, option, index)

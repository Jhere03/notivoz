"""Modelo de tabla de pendientes y delegado que dibuja las etiquetas de color."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from app.data.models import Estado, Importancia, Pendiente
from app.ui import theme

COLUMNAS = ["Cliente", "Pendiente", "Descripción", "Importancia", "Ingreso", "Estado"]
COL_CLIENTE, COL_TITULO, COL_DESCRIPCION, COL_IMPORTANCIA, COL_INGRESO, COL_ESTADO = range(6)

ID_ROLE = Qt.ItemDataRole.UserRole
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

_ORDEN_ESTADO = {Estado.EN_PROCESO: 0, Estado.PENDIENTE: 1, Estado.REALIZADO: 2}

type _Index = QModelIndex | QPersistentModelIndex


class PendientesModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._filas: list[Pendiente] = []

    def set_pendientes(self, filas: list[Pendiente]) -> None:
        self.beginResetModel()
        self._filas = filas
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
            if col == COL_DESCRIPCION and p.descripcion:
                return p.descripcion
            if col == COL_TITULO:
                return p.titulo
            return None
        if role == SORT_ROLE:
            return self._orden(p, col)
        if role == ID_ROLE:
            return p.id
        realizado = p.estado == Estado.REALIZADO
        if role == Qt.ItemDataRole.ForegroundRole and realizado:
            return QColor(theme.TEXTO_SUAVE)
        if role == Qt.ItemDataRole.FontRole and realizado and col == COL_TITULO:
            font = QFont()
            font.setStrikeOut(True)
            return font
        return None

    @staticmethod
    def _texto(p: Pendiente, col: int) -> str:
        match col:
            case 0:
                return p.cliente.nombre if p.cliente else "—"
            case 1:
                return p.titulo
            case 2:
                primera_linea = p.descripcion.splitlines()[0] if p.descripcion else ""
                return primera_linea
            case 3:
                return Importancia(p.importancia).etiqueta
            case 4:
                return p.fecha_ingreso.strftime("%d/%m/%Y")
            case 5:
                return p.estado
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
        return None


class EtiquetaDelegate(QStyledItemDelegate):
    """Dibuja el texto de la celda como una etiqueta redondeada de color."""

    def __init__(self, colores: dict[str, str], parent=None):
        super().__init__(parent)
        self._colores = colores

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

        fm = option.fontMetrics
        ancho = fm.horizontalAdvance(texto) + 22
        alto = fm.height() + 8
        rect = QRectF(option.rect.x() + 8, option.rect.center().y() - alto / 2 + 1, ancho, alto)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fondo)
        painter.drawRoundedRect(rect, alto / 2, alto / 2)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, texto)
        painter.restore()

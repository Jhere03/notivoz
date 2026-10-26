"""Widgets reutilizables: campo de fecha con calendario y contador de estado."""

from PySide6.QtCore import QDate, QEvent, QObject, QPoint, QRectF, QRegularExpression, Qt, QTime, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QRegularExpressionValidator,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QCalendarWidget,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QToolButton,
    QVBoxLayout,
)

from app.ui import theme


def _icono_calendario() -> QIcon:
    """Dibuja un pequeño icono de calendario en el color de acento."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(theme.ACENTO_HOVER)
    p.setPen(QPen(color, 2.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(4, 7, 24, 21), 4, 4)
    p.drawLine(4, 13, 28, 13)
    p.drawLine(11, 3, 11, 9)
    p.drawLine(21, 3, 21, 9)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    for x in (9, 15, 21):
        for y in (17, 22):
            p.drawRect(QRectF(x - 1, y - 1, 3, 3))
    p.end()
    return QIcon(pixmap)


def _icono_limpiar() -> QIcon:
    """Una ✕ discreta para borrar el campo."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    lapiz = QPen(QColor(theme.TEXTO_SUAVE), 2.6)
    lapiz.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(lapiz)
    p.drawLine(10, 10, 22, 22)
    p.drawLine(22, 10, 10, 22)
    p.end()
    return QIcon(pixmap)


def configurar_calendario(cal: QCalendarWidget) -> None:
    """Aplica el aspecto oscuro de la app a un QCalendarWidget."""
    cal.setGridVisible(False)
    cal.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    cal.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
    cal.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)

    # Fines de semana con el mismo color que el resto (por defecto salen en rojo).
    normal = QTextCharFormat()
    normal.setForeground(QColor(theme.TEXTO))
    for dia in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        cal.setWeekdayTextFormat(dia, normal)

    encabezado = QTextCharFormat()
    encabezado.setForeground(QColor(theme.TEXTO_SUAVE))
    encabezado.setBackground(QColor(theme.SUPERFICIE))
    encabezado.setFontWeight(QFont.Weight.DemiBold)
    cal.setHeaderTextFormat(encabezado)

    hoy = QTextCharFormat()
    hoy.setForeground(QColor(theme.ACENTO_HOVER))
    hoy.setFontWeight(QFont.Weight.Bold)
    cal.setDateTextFormat(QDate.currentDate(), hoy)

    # Las flechas por defecto son oscuras e invisibles sobre el tema: usar texto.
    for nombre, texto in (("qt_calendar_prevmonth", "‹"), ("qt_calendar_nextmonth", "›")):
        boton = cal.findChild(QToolButton, nombre)
        if boton is not None:
            boton.setIcon(QIcon())
            boton.setText(texto)
            boton.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)


class FechaEdit(QLineEdit):
    """Campo de fecha de solo lectura que abre un calendario al hacer clic.

    Teclado: Espacio, Enter, F4 o Alt+Abajo también abren el calendario.
    """

    FORMATO = "dd/MM/yyyy"

    fechaCambiada = Signal()

    def __init__(self, parent=None, opcional: bool = False, placeholder: str = ""):
        """Con `opcional=True` el campo puede quedar vacío (date() devuelve una
        QDate inválida) y muestra una ✕ para borrarlo; útil para filtros."""
        super().__init__(parent)
        self._opcional = opcional
        self._fecha = QDate() if opcional else QDate.currentDate()
        self.setReadOnly(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clic para elegir la fecha")
        self.setPlaceholderText(placeholder)
        accion = self.addAction(_icono_calendario(), QLineEdit.ActionPosition.TrailingPosition)
        accion.triggered.connect(self.abrir_calendario)
        self._accion_limpiar = None
        if opcional:
            self._accion_limpiar = self.addAction(
                _icono_limpiar(), QLineEdit.ActionPosition.TrailingPosition
            )
            self._accion_limpiar.setToolTip("Quitar fecha")
            self._accion_limpiar.triggered.connect(self.limpiar)
        self._mostrar()

    def date(self) -> QDate:
        return self._fecha

    def setDate(self, fecha: QDate) -> None:
        if fecha.isValid() and fecha != self._fecha:
            self._fecha = fecha
            self._mostrar()
            self.fechaCambiada.emit()

    def limpiar(self) -> None:
        if self._opcional and self._fecha.isValid():
            self._fecha = QDate()
            self._mostrar()
            self.fechaCambiada.emit()

    def _mostrar(self) -> None:
        self.setText(self._fecha.toString(self.FORMATO) if self._fecha.isValid() else "")
        if self._accion_limpiar is not None:
            self._accion_limpiar.setVisible(self._fecha.isValid())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.abrir_calendario()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        tecla = event.key()
        abrir = tecla in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F4) or (
            tecla == Qt.Key.Key_Down and event.modifiers() & Qt.KeyboardModifier.AltModifier
        )
        if abrir:
            self.abrir_calendario()
            return
        if tecla in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.limpiar()
            return
        super().keyPressEvent(event)

    def abrir_calendario(self) -> None:
        popup = QFrame(self, Qt.WindowType.Popup)
        popup.setObjectName("CalendarioPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        cal = QCalendarWidget(popup)
        cal.setMinimumSize(300, 240)
        configurar_calendario(cal)
        cal.setSelectedDate(self._fecha if self._fecha.isValid() else QDate.currentDate())

        def elegir(fecha: QDate) -> None:
            self.setDate(fecha)
            popup.close()

        cal.clicked.connect(elegir)
        cal.activated.connect(elegir)

        layout = QVBoxLayout(popup)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(cal)
        popup.adjustSize()

        # Debajo del campo; si no cabe en la pantalla, encima.
        pos = self.mapToGlobal(QPoint(0, self.height() + 4))
        pantalla = (self.screen() or QApplication.primaryScreen()).availableGeometry()
        if pos.y() + popup.height() > pantalla.bottom():
            pos.setY(self.mapToGlobal(QPoint(0, 0)).y() - popup.height() - 4)
        pos.setX(min(pos.x(), pantalla.right() - popup.width()))
        popup.move(pos)
        popup.show()
        cal.setFocus()


class EstadoChip(QFrame):
    """Cuadro de color con el número de tareas de un estado. Clic para filtrar."""

    clicked = Signal()

    def __init__(self, singular: str, plural: str, color: str, parent=None):
        super().__init__(parent)
        self._singular = singular
        self._plural = plural
        self._color = QColor(color)
        self.setObjectName("EstadoChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.numero = QLabel("0")
        fuente = self.numero.font()
        fuente.setPointSize(13)
        fuente.setBold(True)
        self.numero.setFont(fuente)
        self.texto = QLabel(plural)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 14, 5)
        layout.setSpacing(8)
        layout.addWidget(self.numero)
        layout.addWidget(self.texto)

        self.set_activo(False)

    def set_valor(self, n: int) -> None:
        self.numero.setText(str(n))
        self.texto.setText(self._singular if n == 1 else self._plural)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.set_activo(self._activo)

    def set_activo(self, activo: bool) -> None:
        self._activo = activo
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        fondo = 0.28 if activo else 0.13
        borde = 0.95 if activo else 0.4
        self.setStyleSheet(
            f"#EstadoChip {{ background: rgba({r}, {g}, {b}, {fondo});"
            f" border: 1px solid rgba({r}, {g}, {b}, {borde}); border-radius: 8px; }}"
            f" QLabel {{ background: transparent; color: {self._color.name()}; }}"
        )
        self.setToolTip("Clic para quitar el filtro" if activo else "Clic para ver solo estas")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class SinRuedaAccidental(QObject):
    """Filtro para toda la app: la rueda del mouse sobre listas desplegables,
    deslizadores y campos numéricos no cambia su valor, sino que desplaza la
    página que los contiene (como en un navegador)."""

    # QSlider y no QAbstractSlider: las barras de desplazamiento sí deben usar la rueda.
    _TIPOS = (QComboBox, QSlider, QAbstractSpinBox)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel or not isinstance(obj, self._TIPOS):
            return False
        area = obj.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QApplication.sendEvent(area.verticalScrollBar(), event)
        return True


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

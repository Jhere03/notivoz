"""Ver una tarea o una nota completa, sin editarla: la ventana se ajusta a su
texto para leerlo todo de una vez (solo si no cabe en la pantalla aparece el
desplazamiento)."""

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Importancia, Nota, Pendiente
from app.ui import theme
from app.ui.formato import fecha_hora_corta

_ANCHO_MINIMO = 460
_ANCHO_ETIQUETAS = 130
_EDITAR = 2  # resultado de exec() si pidió editar


def dibujar_ojo(p: QPainter, rect: QRectF, color: QColor, relleno: bool = False) -> None:
    """Icono de ojo dentro de `rect` (con `relleno`, el ojo lleno y la pupila blanca)."""
    centro = rect.center()
    ancho, alto = rect.width() / 2, rect.height() * 0.36
    ojo = QPainterPath(QPointF(centro.x() - ancho, centro.y()))
    ojo.quadTo(QPointF(centro.x(), centro.y() - alto * 2), QPointF(centro.x() + ancho, centro.y()))
    ojo.quadTo(QPointF(centro.x(), centro.y() + alto * 2), QPointF(centro.x() - ancho, centro.y()))
    lapiz = QPen(color, max(1.4, rect.width() / 12))
    lapiz.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(lapiz)
    p.setBrush(color if relleno else Qt.BrushStyle.NoBrush)
    p.drawPath(ojo)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white") if relleno else color)
    p.drawEllipse(centro, alto * 0.75, alto * 0.75)


def icono_ojo(tamano: int = 18) -> QIcon:
    imagen = QPixmap(QSize(tamano, tamano) * 2)
    imagen.setDevicePixelRatio(2)
    imagen.fill(Qt.GlobalColor.transparent)
    p = QPainter(imagen)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    dibujar_ojo(p, QRectF(1, 1, tamano - 2, tamano - 2), QColor(theme.ACENTO_HOVER))
    p.end()
    return QIcon(imagen)


def ver_tarea(pendiente: Pendiente, parent=None) -> bool:
    """Muestra la tarea. Devuelve True si pidió editarla."""
    campos = [
        ("Cliente", pendiente.cliente.nombre if pendiente.cliente else "Sin cliente"),
        ("Tarea", pendiente.titulo),
        ("Descripción", pendiente.descripcion.strip() or "Sin descripción"),
        ("Importancia", Importancia(pendiente.importancia).etiqueta),
        ("Fecha de ingreso", pendiente.fecha_ingreso.strftime("%d/%m/%Y")),
        ("Estado", str(pendiente.estado)),
    ]
    if pendiente.fecha_realizado:
        campos.append(("Culminada", fecha_hora_corta(pendiente.fecha_realizado)))
    return VerDialog("Ver tarea", campos, parent).exec() == _EDITAR


def ver_nota(nota: Nota, parent=None) -> bool:
    """Muestra la nota. Devuelve True si pidió editarla."""
    campos = [("Título", nota.titulo), ("Contenido", nota.contenido.strip() or "Sin contenido")]
    if nota.recordatorio:
        campos.append(("Recordatorio", fecha_hora_corta(nota.recordatorio)))
    campos.append(("Creada", fecha_hora_corta(nota.creado_en)))
    return VerDialog("Ver nota", campos, parent).exec() == _EDITAR


class _Campo(QTextEdit):
    """Un valor de solo lectura (se puede seleccionar y copiar) que salta de
    línea en las palabras o, si una no cabe (un enlace larguísimo), en cualquier
    punto; su alto es el de todo su texto."""

    def __init__(self, texto: str):
        super().__init__()
        self.setObjectName("CampoLectura")
        self.setReadOnly(True)
        self.setPlainText(texto)  # nunca interpretar HTML
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().setDocumentMargin(7)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def ancho_ideal(self) -> int:
        """Lo que mide su línea más larga (sin saltos)."""
        medidas = self.fontMetrics()
        return max((medidas.horizontalAdvance(linea) for linea in self.toPlainText().splitlines()), default=0)

    def ajustar_alto(self) -> None:
        self.document().setTextWidth(self.viewport().width())
        self.setFixedHeight(int(self.document().size().height()) + 2 * self.frameWidth() + 2)

    def resizeEvent(self, evento) -> None:
        super().resizeEvent(evento)
        self.ajustar_alto()


class VerDialog(QDialog):
    def __init__(self, titulo: str, campos: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)

        contenido = QWidget()
        form = QFormLayout(contenido)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        valores = []
        for etiqueta, valor in campos:
            nombre = QLabel(etiqueta)
            nombre.setFixedWidth(_ANCHO_ETIQUETAS)
            nombre.setContentsMargins(0, 8, 0, 0)
            texto = _Campo(valor)
            form.addRow(nombre, texto)
            valores.append(texto)

        desplazable = QScrollArea()
        desplazable.setWidget(contenido)
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QScrollArea.Shape.NoFrame)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        editar = QPushButton("✎  Editar")
        editar.setObjectName("Secundario")
        editar.setAutoDefault(False)
        editar.clicked.connect(lambda: self.done(_EDITAR))
        cerrar = QPushButton("Cerrar")
        cerrar.setObjectName("Primario")
        cerrar.setDefault(True)
        cerrar.clicked.connect(self.accept)
        botones = QHBoxLayout()
        botones.addStretch()
        botones.addWidget(editar)
        botones.addWidget(cerrar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(desplazable, stretch=1)
        layout.addLayout(botones)

        self._ajustar_al_contenido(contenido, valores, layout)

    def _ajustar_al_contenido(self, contenido: QWidget, valores: list[_Campo], layout: QVBoxLayout) -> None:
        """Tan ancha como la línea más larga y tan alta como todo el texto, sin
        pasar del 70 % del ancho ni del 85 % del alto de la pantalla."""
        pantalla = (self.parentWidget().screen() if self.parentWidget() else QGuiApplication.primaryScreen())
        disponible = pantalla.availableGeometry()
        margenes = layout.contentsMargins()
        extra_ancho = margenes.left() + margenes.right() + _ANCHO_ETIQUETAS + 40
        linea_mas_larga = max((v.ancho_ideal() for v in valores), default=0)
        ancho = max(_ANCHO_MINIMO, min(linea_mas_larga + 30 + extra_ancho, int(disponible.width() * 0.7)))
        ancho_contenido = ancho - margenes.left() - margenes.right()
        ancho_campo = ancho_contenido - _ANCHO_ETIQUETAS - contenido.layout().horizontalSpacing()
        for campo in valores:
            campo.resize(ancho_campo, campo.height())
            campo.ajustar_alto()
        contenido.layout().activate()
        alto_contenido = contenido.layout().sizeHint().height()
        alto = alto_contenido + margenes.top() + margenes.bottom() + layout.spacing() + 44
        self.resize(ancho, min(alto, int(disponible.height() * 0.85)))

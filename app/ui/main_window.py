"""Ventana principal: barra lateral de navegación y vistas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION, db_path
from app.ui.pendientes_view import PendientesView


class ProximamenteView(QWidget):
    """Marcador de lugar para las vistas de fases siguientes."""

    def __init__(self, titulo: str, descripcion: str, parent=None):
        super().__init__(parent)
        encabezado = QLabel(titulo)
        encabezado.setObjectName("TituloVista")
        texto = QLabel(descripcion)
        texto.setObjectName("Proximamente")
        texto.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)
        layout.addWidget(encabezado)
        layout.addWidget(texto)
        layout.addStretch()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 740)
        self.setMinimumSize(900, 560)

        self.pendientes = PendientesView()
        vistas = [
            ("Pendientes", self.pendientes),
            (
                "Notas",
                ProximamenteView(
                    "Notas",
                    "Aquí podrás escribir notas con fecha y hora de recordatorio. "
                    "Cuando llegue el momento, Notivoz te avisará en pantalla y por voz. "
                    "Llega en la fase 2.",
                ),
            ),
            (
                "Comandos de voz",
                ProximamenteView(
                    "Comandos de voz",
                    "Aquí configurarás frases como «Modo chill» y las aplicaciones que abre "
                    "cada una. Llega en las fases 4 y 5.",
                ),
            ),
        ]

        self.stack = QStackedWidget()
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        for nombre, vista in vistas:
            self.nav.addItem(nombre)
            self.stack.addWidget(vista)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        lema = QLabel("Tus pendientes, con voz")
        lema.setObjectName("Lema")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("Version")

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        lateral = QVBoxLayout(sidebar)
        lateral.setContentsMargins(0, 0, 0, 0)
        lateral.setSpacing(0)
        lateral.addWidget(logo)
        lateral.addWidget(lema)
        lateral.addWidget(self.nav, stretch=1)
        lateral.addWidget(version)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(f"Base de datos: {db_path()}")

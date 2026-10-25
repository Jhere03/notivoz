"""Ventana principal: barra lateral de navegación y vistas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION, db_path
from app.services import ajustes
from app.services.ajustes import Clave
from app.services.saludo import texto_saludo
from app.services.voz import voz
from app.ui.bandeja import Bandeja
from app.ui.configuracion_view import ConfiguracionView
from app.ui.icono import icono_app
from app.ui.notas_view import NotasView
from app.ui.pendientes_view import PendientesView
from app.ui.recordatorios import ProgramadorRecordatorios


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

        self.setWindowIcon(icono_app())

        self.pendientes = PendientesView()
        self.notas = NotasView()
        self.configuracion = ConfiguracionView()
        self.configuracion.probar_saludo.connect(self.leer_pendientes)
        vistas = [
            ("Pendientes", self.pendientes),
            ("Notas", self.notas),
            (
                "Comandos de voz",
                ProximamenteView(
                    "Comandos de voz",
                    "Aquí configurarás frases como «Modo chill» y las aplicaciones que abre "
                    "cada una. Llega en las fases 4 y 5.",
                ),
            ),
            ("Configuración", self.configuracion),
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

        self.recordatorios = ProgramadorRecordatorios(self)
        self.recordatorios.notas_cambiaron.connect(self.notas.recargar)

        self._saliendo = False
        self.bandeja = Bandeja(self)
        self.bandeja.abrir.connect(self.mostrar)
        self.bandeja.nueva_tarea.connect(lambda: self._ir_a(self.pendientes, self.pendientes.nuevo))
        self.bandeja.nueva_nota.connect(lambda: self._ir_a(self.notas, self.notas.nueva))
        self.bandeja.leer_pendientes.connect(self.leer_pendientes)
        self.bandeja.salir.connect(self.salir)
        self.bandeja.show()

    # --- Acciones generales --------------------------------------------------

    def mostrar(self) -> None:
        """Trae la ventana al frente, aunque esté oculta en la bandeja o minimizada."""
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _ir_a(self, vista: QWidget, accion) -> None:
        self.mostrar()
        self.nav.setCurrentRow(self.stack.indexOf(vista))
        accion()

    def leer_pendientes(self) -> None:
        voz().hablar(texto_saludo(ajustes.obtener(Clave.NOMBRE)))

    def salir(self) -> None:
        self._saliendo = True
        self.bandeja.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._saliendo or not ajustes.obtener(Clave.CERRAR_A_BANDEJA):
            self.salir()
            event.accept()
            return
        # Cerrar la ventana solo la oculta: los recordatorios siguen funcionando.
        event.ignore()
        self.hide()
        if not ajustes.obtener(Clave.AVISO_BANDEJA_MOSTRADO):
            self.bandeja.avisar(
                "Notivoz sigue funcionando",
                "Está aquí, en la bandeja. Clic en el icono para abrirlo o clic derecho para salir.",
            )
            ajustes.guardar(Clave.AVISO_BANDEJA_MOSTRADO, True)

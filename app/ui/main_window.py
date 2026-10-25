"""Ventana principal: barra lateral de navegación y vistas."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.services import ajustes, modelo_voz
from app.services import comandos as servicio_comandos
from app.services.ajustes import Clave
from app.services.escucha import Escucha
from app.services.saludo import texto_saludo
from app.services.voz import voz
from app.ui.bandeja import Bandeja
from app.ui.burbuja import BurbujaVoz
from app.ui.comandos_view import ComandosView
from app.ui.configuracion_view import ConfiguracionView
from app.ui.icono import icono_app
from app.ui.notas_view import NotasView
from app.ui.pendientes_view import PendientesView
from app.ui.recordatorios import ProgramadorRecordatorios


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
        self.comandos = ComandosView()
        vistas = [
            ("Pendientes", self.pendientes),
            ("Notas", self.notas),
            ("Comandos de voz", self.comandos),
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
        # Salir de Configuración termina la prueba de micrófono, si estaba en curso.
        self.nav.currentRowChanged.connect(lambda _: self.configuracion.detener_prueba_microfono())
        self.nav.setCurrentRow(0)

        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        lema = QLabel("Tus pendientes, con voz")
        lema.setObjectName("Lema")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("Version")
        self.estado_escucha = QLabel()
        self.estado_escucha.setObjectName("EstadoEscucha")
        self.estado_escucha.setWordWrap(True)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        lateral = QVBoxLayout(sidebar)
        lateral.setContentsMargins(0, 0, 0, 0)
        lateral.setSpacing(0)
        lateral.addWidget(logo)
        lateral.addWidget(lema)
        lateral.addWidget(self.nav, stretch=1)
        lateral.addWidget(self.estado_escucha)
        lateral.addWidget(version)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

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

        # --- Comandos de voz ---
        self.escucha = Escucha(self)
        self.burbuja = BurbujaVoz(lambda: self.escucha.nivel)
        self.escucha.estado_cambiado.connect(self._al_cambiar_estado_escucha)
        self.escucha.activacion_oida.connect(self.burbuja.escuchar)
        self.escucha.comando_detectado.connect(self.burbuja.ejecutar)
        self.escucha.comando_detectado.connect(self.ejecutar_comando)
        self._escucha_antes_de_prueba = False
        self._probando_microfono = False
        self.configuracion.prueba_microfono_cambiada.connect(self._pausar_por_prueba)
        self.comandos.ejecutar.connect(self.ejecutar_comando)
        self.comandos.escucha_pedida.connect(self._pedir_escucha)
        self.comandos.comandos_cambiaron.connect(self._recargar_frases)
        self.configuracion.escucha_config_cambiada.connect(self._reiniciar_escucha)
        self.configuracion.modelo_instalado.connect(self._reiniciar_escucha)
        self._configurar_escucha()
        self._al_cambiar_estado_escucha("Micrófono apagado", False)
        if ajustes.obtener(Clave.ESCUCHA_ACTIVA):
            self.escucha.iniciar()

    # --- Comandos de voz -----------------------------------------------------

    def _configurar_escucha(self) -> None:
        self.escucha.dispositivo = ajustes.obtener(Clave.MICROFONO) or None
        self._recargar_frases()

    def _recargar_frases(self) -> None:
        self.escucha.set_frases(servicio_comandos.frases_activas())

    def _pedir_escucha(self, activar: bool) -> None:
        if activar and not modelo_voz.instalado():
            self._al_cambiar_estado_escucha("Falta el modelo de voz", False)
            QMessageBox.information(
                self,
                "Falta el modelo de voz",
                "Primero descarga el modelo de voz en español en Configuración → Comandos de voz.",
            )
            self.nav.setCurrentRow(self.stack.indexOf(self.configuracion))
            return
        ajustes.guardar(Clave.ESCUCHA_ACTIVA, activar)
        if activar:
            self.escucha.iniciar()
        else:
            self.escucha.detener()

    def _reiniciar_escucha(self) -> None:
        estaba_activa = self.escucha.activa
        self.escucha.detener()
        self._configurar_escucha()
        if estaba_activa or ajustes.obtener(Clave.ESCUCHA_ACTIVA):
            self.escucha.iniciar()

    def _pausar_por_prueba(self, probando: bool) -> None:
        """Durante la prueba de micrófono la escucha se pausa: el eco de tu voz
        no debe disparar comandos."""
        self._probando_microfono = probando
        if probando:
            self._escucha_antes_de_prueba = self.escucha.activa
            self.escucha.detener()
            self._al_cambiar_estado_escucha("En pausa (probando micrófono)", False)
        elif self._escucha_antes_de_prueba:
            self._escucha_antes_de_prueba = False
            self.escucha.iniciar()
        else:
            self._al_cambiar_estado_escucha("Micrófono apagado", False)

    def _al_cambiar_estado_escucha(self, texto: str, escuchando: bool) -> None:
        if self._probando_microfono and not escuchando:
            # El aviso «Micrófono apagado» de la escucha llega tarde: mantener la pausa.
            texto = "En pausa (probando micrófono)"
        self.comandos.set_estado_escucha(texto, escuchando)
        self.estado_escucha.setText(("🎙  " if escuchando else "🔇  ") + texto)
        self.bandeja.setToolTip(f"{APP_NAME} — {texto}")

    def ejecutar_comando(self, comando_id: int) -> None:
        comando = servicio_comandos.obtener(comando_id)
        if comando is None:
            return
        self.statusBar().showMessage(f"Ejecutando «{comando.frase}»…", 8000)
        servicio_comandos.ejecutar(comando_id)

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
        self.configuracion.detener_prueba_microfono()
        self.escucha.detener()
        self.bandeja.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._saliendo or not ajustes.obtener(Clave.CERRAR_A_BANDEJA):
            self.salir()
            event.accept()
            return
        # Cerrar la ventana solo la oculta: los recordatorios siguen funcionando.
        event.ignore()
        self.configuracion.detener_prueba_microfono()
        self.hide()
        if not ajustes.obtener(Clave.AVISO_BANDEJA_MOSTRADO):
            self.bandeja.avisar(
                "Notivoz sigue funcionando",
                "Está aquí, en la bandeja. Clic en el icono para abrirlo o clic derecho para salir.",
            )
            ajustes.guardar(Clave.AVISO_BANDEJA_MOSTRADO, True)

"""Ventana principal: barra lateral, vistas y la orquestación de voz (comandos),
recordatorios, rutinas y productividad."""

import ctypes
import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, APP_VERSION
from app.data.models import AccionRutina, Estado
from app.services import ajustes, modelo_voz
from app.services import comandos as servicio_comandos
from app.services import pendientes as servicio_pendientes
from app.services import rutinas as servicio_rutinas
from app.services.ajustes import Clave
from app.services.escucha import Escucha
from app.services.saludo import dias_texto, texto_resumen_dia, texto_saludo
from app.services.voz import voz
from app.ui.bandeja import Bandeja
from app.ui.burbuja import BurbujaVoz
from app.ui.comandos_view import ComandosView
from app.ui.configuracion_view import ConfiguracionView
from app.ui.icono import icono_app
from app.ui.iconos_menu import icono_menu
from app.ui.notas_view import NotasView
from app.ui.pendientes_view import PendientesView
from app.ui.productividad import ControladorEnfoque, MonitorOcio, ProgramadorRutinas
from app.ui.recordatorios import ProgramadorRecordatorios
from app.ui.rutinas_view import RutinasView

_MAXIMO_RESUMEN_AL_APAGAR = 20  # segundos que se retrasa el apagado como mucho


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 740)
        self.setMinimumSize(900, 560)
        self.setWindowIcon(icono_app())
        self._saliendo = False
        self._resumen_al_apagar_leido = False

        # --- Vistas ---
        self.pendientes = PendientesView()
        self.notas = NotasView()
        self.comandos = ComandosView()
        self.rutinas = RutinasView()
        self.configuracion = ConfiguracionView()
        vistas = [
            ("Mis tareas", "pendientes", self.pendientes),
            ("Notas", "notas", self.notas),
            ("Comandos de voz", "comandos", self.comandos),
            ("Rutinas", "rutinas", self.rutinas),
            ("Configuración", "configuracion", self.configuracion),
        ]

        self.stack = QStackedWidget()
        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        self.nav.setCursor(Qt.CursorShape.PointingHandCursor)
        self.nav.setIconSize(QSize(18, 18))
        for nombre, icono, vista in vistas:
            self.nav.addItem(QListWidgetItem(icono_menu(icono), nombre))
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
        self.indicador_enfoque = QPushButton()
        self.indicador_enfoque.setObjectName("IndicadorEnfoque")
        self.indicador_enfoque.setCursor(Qt.CursorShape.PointingHandCursor)
        self.indicador_enfoque.setToolTip("Clic para terminar el modo enfoque")
        self.indicador_enfoque.hide()

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        lateral = QVBoxLayout(sidebar)
        lateral.setContentsMargins(0, 0, 0, 0)
        lateral.setSpacing(0)
        lateral.addWidget(logo)
        lateral.addWidget(lema)
        lateral.addWidget(self.nav, stretch=1)
        lateral.addWidget(self.indicador_enfoque)
        lateral.addWidget(self.estado_escucha)
        lateral.addWidget(version)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        # --- Productividad ---
        self.enfoque = ControladorEnfoque(self)
        self.enfoque.cambiado.connect(self._al_cambiar_enfoque)
        self.enfoque.terminado.connect(self._al_terminar_enfoque)
        self.indicador_enfoque.clicked.connect(self._terminar_enfoque_manual)
        self.programador_rutinas = ProgramadorRutinas(self)
        self.programador_rutinas.ejecutar.connect(self.ejecutar_rutina)
        self.monitor_ocio = MonitorOcio(self)
        self.monitor_ocio.aviso.connect(self._avisar_ocio)

        self.recordatorios = ProgramadorRecordatorios(self)
        self.recordatorios.en_pausa = lambda: self.enfoque.activo
        self.recordatorios.notas_cambiaron.connect(self.notas.recargar)

        # --- Bandeja ---
        self.bandeja = Bandeja(self)
        self.bandeja.abrir.connect(self.mostrar)
        self.bandeja.nueva_tarea.connect(lambda: self._ir_a(self.pendientes, self.pendientes.nuevo))
        self.bandeja.nueva_nota.connect(lambda: self._ir_a(self.notas, self.notas.nueva))
        self.bandeja.leer_pendientes.connect(self.leer_pendientes)
        self.bandeja.resumen_dia.connect(self.decir_resumen_dia)
        self.bandeja.salir.connect(self.salir)
        self.bandeja.show()

        # --- Voz: escucha y burbuja ---
        self.escucha = Escucha(self)
        self.burbuja = BurbujaVoz(lambda: self.escucha.nivel)
        self.escucha.estado_cambiado.connect(self._al_cambiar_estado_escucha)
        self.escucha.activacion_oida.connect(self.burbuja.escuchar)
        self.escucha.comando_detectado.connect(self._comando_por_voz)
        self.escucha.cierre_detectado.connect(self._cierre_por_voz)
        self._escucha_antes_de_prueba = False
        self._probando_microfono = False

        # --- Señales de las vistas ---
        self.pendientes.tarea_realizada.connect(self._celebrar)
        self.pendientes.enfoque_pedido.connect(self._pedir_enfoque)
        self.comandos.ejecutar.connect(self.ejecutar_comando)
        self.comandos.cerrar.connect(lambda comando_id: voz().hablar(self._cerrar_comando(comando_id)))
        self.comandos.escucha_pedida.connect(self._pedir_escucha)
        self.comandos.comandos_cambiaron.connect(self._recargar_frases)
        self.rutinas.probar.connect(self.ejecutar_rutina)
        self.configuracion.probar_saludo.connect(self.leer_pendientes)
        self.configuracion.prueba_microfono_cambiada.connect(self._pausar_por_prueba)
        self.configuracion.escucha_config_cambiada.connect(self._reiniciar_escucha)
        self.configuracion.modelo_instalado.connect(self._reiniciar_escucha)
        self.configuracion.personalidad_cambiada.connect(self.comandos.recargar)

        # Al apagar Windows: resumen del día.
        QApplication.instance().commitDataRequest.connect(self._al_apagar_windows)

        self._configurar_escucha()
        self._al_cambiar_estado_escucha("Micrófono apagado", False)
        if ajustes.obtener(Clave.ESCUCHA_ACTIVA):
            self.escucha.iniciar()

    # --- Racha ----------------------------------------------------------------

    def _celebrar(self, _tarea_id: int) -> None:
        """Primera tarea terminada del día con racha de 2 o más días: celebrarlo."""
        if not ajustes.obtener(Clave.CELEBRAR_RACHA):
            return
        resumen = servicio_pendientes.resumen_del_dia()
        if len(resumen.realizadas) == 1 and resumen.racha >= 2:
            texto = ajustes.frases_actuales().frase("racha", dias=dias_texto(resumen.racha))
            voz().hablar(texto)
            self.burbuja.ejecutar()

    # --- Comandos ------------------------------------------------------------

    def _comando_por_voz(self, comando_id: int) -> None:
        self.burbuja.ejecutar()
        self.ejecutar_comando(comando_id)

    def _cierre_por_voz(self, comando_id: int) -> None:
        self.burbuja.ejecutar()
        voz().hablar(self._cerrar_comando(comando_id))

    def ejecutar_comando(self, comando_id: int) -> None:
        comando = servicio_comandos.obtener(comando_id)
        if comando is None:
            return
        self.statusBar().showMessage(f"Ejecutando «{comando.frase}»…", 8000)
        servicio_comandos.ejecutar(comando_id, ajustes.frases_actuales())

    def _cerrar_comando(self, comando_id: int) -> str:
        return servicio_comandos.cerrar(comando_id, ajustes.frases_actuales())

    # --- Rutinas -------------------------------------------------------------

    def ejecutar_rutina(self, rutina_id: int) -> None:
        rutina = servicio_rutinas.obtener(rutina_id)
        if rutina is None:
            return
        match AccionRutina(rutina.accion):
            case AccionRutina.EJECUTAR_COMANDO:
                if rutina.comando_id is not None:
                    self.ejecutar_comando(rutina.comando_id)
            case AccionRutina.LEER_PENDIENTES:
                self.leer_pendientes()
            case AccionRutina.RESUMEN_DIA:
                self.decir_resumen_dia()

    # --- Modo enfoque ----------------------------------------------------------

    def _pedir_enfoque(self, tarea_id: int) -> None:
        minutos, ok = QInputDialog.getInt(
            self, "Modo enfoque", "¿Cuántos minutos quieres concentrarte?", 25, 1, 240
        )
        if ok:
            self.enfoque.iniciar(minutos, tarea_id)
            tarea = servicio_pendientes.obtener(tarea_id)
            en = f" en «{tarea.titulo}»" if tarea else ""
            voz().hablar(ajustes.frases_actuales().frase("enfoque_inicio", minutos=minutos, en=en))
            self.pendientes.recargar()

    def _al_cambiar_enfoque(self, texto: str) -> None:
        self.indicador_enfoque.setText(f"{texto}  ✕" if texto else "")
        self.indicador_enfoque.setVisible(bool(texto))
        self.bandeja.setToolTip(f"{APP_NAME} — {texto}" if texto else APP_NAME)

    def _terminar_enfoque_manual(self) -> None:
        if self.enfoque.terminar():
            voz().hablar(ajustes.frases_actuales().frase("enfoque_cancelado"))
            self.recordatorios.revisar()

    def _al_terminar_enfoque(self, tarea_id: int | None) -> None:
        frases = ajustes.frases_actuales()
        tarea = servicio_pendientes.obtener(tarea_id) if tarea_id is not None else None
        fin = frases.frase("enfoque_fin", en=f" en «{tarea.titulo}»" if tarea else "")
        voz().hablar(fin)
        self.bandeja.avisar("Modo enfoque", fin)
        # Los recordatorios que esperaban, ahora sí.
        self.recordatorios.revisar()
        if tarea is None or tarea.estado == Estado.REALIZADO:
            return
        eleccion = QMessageBox.question(
            None, "Modo enfoque", f"{fin}\n\n¿Marcar «{tarea.titulo}» como realizada?"
        )
        if eleccion == QMessageBox.StandardButton.Yes:
            servicio_pendientes.cambiar_estado(tarea.id, Estado.REALIZADO)
            voz().hablar(frases.frase("tarea_terminada", titulo=tarea.titulo))
            self.pendientes.recargar()
            self._celebrar(tarea.id)

    # --- Aviso de ocio ---------------------------------------------------------

    def _avisar_ocio(self, titulo: str) -> None:
        texto = ajustes.frases_actuales().frase("aviso_ocio", titulo=titulo)
        voz().hablar(texto)
        self.bandeja.avisar(APP_NAME, texto)

    # --- Escucha ---------------------------------------------------------------

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
        if not self.enfoque.activo:
            self.bandeja.setToolTip(f"{APP_NAME} — {texto}")

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
        voz().hablar(ajustes.frases_actuales().adaptar(texto_saludo(ajustes.obtener(Clave.NOMBRE))))

    def decir_resumen_dia(self) -> None:
        voz().hablar(self._texto_resumen())

    @staticmethod
    def _texto_resumen() -> str:
        return ajustes.frases_actuales().adaptar(texto_resumen_dia())

    def _al_apagar_windows(self, _gestor) -> None:
        """Windows se está apagando: leer el resumen del día antes de cerrar.
        Se le avisa a Windows por qué se espera (el usuario puede apagar igual)."""
        if self._resumen_al_apagar_leido or not ajustes.obtener(Clave.RESUMEN_AL_APAGAR):
            return
        self._resumen_al_apagar_leido = True
        ventana = int(self.winId())
        usuario32 = ctypes.windll.user32
        usuario32.ShutdownBlockReasonCreate(ventana, "Notivoz está leyendo tu resumen del día")
        try:
            voz().hablar(self._texto_resumen())
            limite = time.monotonic() + _MAXIMO_RESUMEN_AL_APAGAR
            time.sleep(0.3)
            while voz().ocupada() and time.monotonic() < limite:
                QApplication.processEvents()
                time.sleep(0.05)
        finally:
            usuario32.ShutdownBlockReasonDestroy(ventana)

    def salir(self) -> None:
        self._saliendo = True
        self.configuracion.detener_prueba_microfono()
        self.escucha.detener()
        self.burbuja.ocultar()
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

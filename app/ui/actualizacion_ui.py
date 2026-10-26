"""Panel del menú lateral: versión, botón «Hay una nueva actualización» y una
barra de progreso animada (también para preparar la voz la primera vez)."""

import logging
import threading

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.config import APP_VERSION
from app.services import actualizacion, modelo_voz, transcripcion
from app.ui import theme

log = logging.getLogger(__name__)

_REVISAR_CADA_MS = 6 * 60 * 60 * 1000  # cada 6 horas
_PRIMERA_REVISION_MS = 8000  # al abrir, sin retrasar el arranque


class BarraAnimada(QWidget):
    """Barra de progreso con degradado morado y un brillo que la recorre."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._valor = 0.0  # 0 a 1 (lo que se muestra, suavizado)
        self._objetivo = 0.0
        self._brillo = -0.3
        self._reloj = QTimer(self, interval=16)
        self._reloj.timeout.connect(self._animar)

    def set_valor(self, valor: float) -> None:
        self._objetivo = max(0.0, min(1.0, valor))
        if not self._reloj.isActive():
            self._reloj.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._reloj.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._reloj.stop()

    def _animar(self) -> None:
        self._valor += (self._objetivo - self._valor) * 0.12
        self._brillo += 0.018
        if self._brillo > 1.3:
            self._brillo = -0.3
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radio = r.height() / 2
        fondo = QColor(theme.ACENTO)
        fondo.setAlpha(45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(r, radio, radio)

        ancho = max(r.height(), r.width() * self._valor)
        lleno = QRectF(r.left(), r.top(), ancho, r.height())
        recorte = QPainterPath()
        recorte.addRoundedRect(lleno, radio, radio)
        p.setClipPath(recorte)
        degradado = QLinearGradient(lleno.topLeft(), lleno.topRight())
        degradado.setColorAt(0.0, QColor("#5b3df5"))
        degradado.setColorAt(1.0, QColor("#a996ff"))
        p.fillRect(lleno, degradado)
        # Brillo que avanza: da sensación de movimiento aunque el % no cambie.
        x = r.left() + r.width() * self._brillo
        brillo = QLinearGradient(x - 40, 0, x + 40, 0)
        brillo.setColorAt(0.0, QColor(255, 255, 255, 0))
        brillo.setColorAt(0.5, QColor(255, 255, 255, 150))
        brillo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(lleno, brillo)
        p.end()


class PanelVersion(QWidget):
    """«Notivoz está en su última versión» o el botón para actualizar."""

    # Se emiten desde hilos: la interfaz los recibe en el suyo.
    _encontrada = Signal(object)  # actualizacion.Version | None
    _progreso = Signal(int, int)
    _descargada = Signal(object)  # Path del instalador
    _fallo = Signal(str)
    _modelos_avance = Signal(str, float)
    _modelos_listos = Signal(bool)
    # Para la ventana principal.
    salir_para_actualizar = Signal()
    modelos_preparados = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PanelVersion")
        self._version: actualizacion.Version | None = None
        self._ocupado = False

        self.estado = QLabel()
        self.estado.setObjectName("EstadoVersion")
        self.estado.setWordWrap(True)
        self.boton = QPushButton()
        self.boton.setObjectName("BotonActualizar")
        self.boton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton.clicked.connect(self.actualizar)
        self.boton.hide()
        self.barra = BarraAnimada()
        self.barra.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 0)
        layout.setSpacing(6)
        layout.addWidget(self.boton)
        layout.addWidget(self.estado)
        layout.addWidget(self.barra)

        self._encontrada.connect(self._al_encontrar)
        self._progreso.connect(self._al_progresar)
        self._descargada.connect(self._al_descargar)
        self._fallo.connect(self._al_fallar)
        self._modelos_avance.connect(self._al_avanzar_modelos)
        self._modelos_listos.connect(self._al_terminar_modelos)

        if actualizacion.es_ejecutable():
            self._mostrar_estado("✓  Notivoz está en su última versión")
            self._reloj = QTimer(self, interval=_REVISAR_CADA_MS)
            self._reloj.timeout.connect(self.revisar)
            self._reloj.start()
            QTimer.singleShot(_PRIMERA_REVISION_MS, self.revisar)
        else:
            self._mostrar_estado(f"v{APP_VERSION} · versión de desarrollo")

    # --- Revisar ---

    def revisar(self) -> None:
        if self._ocupado or self._version is not None:
            return
        threading.Thread(target=self._buscar, name="BuscarActualizacion", daemon=True).start()

    def _buscar(self) -> None:
        try:
            self._encontrada.emit(actualizacion.buscar())
        except Exception as error:
            # Sin internet o GitHub no responde: se reintenta en la próxima revisión.
            log.info("No se pudo revisar si hay actualizaciones: %s", error)

    def _al_encontrar(self, version) -> None:
        if version is None or self._ocupado:
            return
        self._version = version
        self.estado.hide()
        # En dos líneas: el menú lateral es angosto.
        self.boton.setText(f"⬆  Hay una nueva\n     actualización v{version.numero}")
        self.boton.show()

    # --- Actualizar ---

    def actualizar(self) -> None:
        if self._version is None or self._ocupado:
            return
        self._ocupado = True
        self.boton.hide()
        self._mostrar_estado(f"Descargando v{self._version.numero}…  0%")
        self.barra.set_valor(0)
        self.barra.show()
        version = self._version

        def trabajar() -> None:
            try:
                ruta = actualizacion.descargar(version, lambda l, t: self._progreso.emit(l, t))
                self._descargada.emit(ruta)
            except Exception as error:
                log.exception("Falló la actualización")
                self._fallo.emit(str(error) or "Error de conexión")

        threading.Thread(target=trabajar, name="Actualizacion", daemon=True).start()

    def _al_progresar(self, leidos: int, total: int) -> None:
        if total:
            self.barra.set_valor(leidos / total)
            self.estado.setText(f"Descargando v{self._version.numero}…  {leidos * 100 // total}%")

    def _al_descargar(self, ruta) -> None:
        self.barra.set_valor(1.0)
        self.estado.setText("Instalando… Notivoz se abrirá de nuevo en unos segundos")
        try:
            actualizacion.instalar(ruta)
        except OSError as error:
            self._al_fallar(str(error))
            return
        # Dar un instante para que se vea el mensaje antes de cerrar.
        QTimer.singleShot(1200, self.salir_para_actualizar.emit)

    def _al_fallar(self, mensaje: str) -> None:
        self._ocupado = False
        self.barra.hide()
        self._mostrar_estado(f"No se pudo actualizar: {mensaje}")
        if self._version is not None:
            self.boton.setText(f"⟳  Reintentar\n     actualización v{self._version.numero}")
            self.boton.show()

    # --- Preparar la voz la primera vez ---

    def preparar_modelos(self) -> None:
        """Descarga (verificando su huella) lo que falte para entender la voz:
        el modelo de comandos y Whisper. Así la app queda lista sola."""
        if modelo_voz.instalado() and transcripcion.instalado():
            return
        self._ocupado = True
        self.boton.hide()
        self._mostrar_estado("Preparando la voz de Notivoz…  0%")
        self.barra.set_valor(0)
        self.barra.show()
        threading.Thread(target=self._descargar_modelos, name="PrepararVoz", daemon=True).start()

    def _descargar_modelos(self) -> None:
        # Pesos aproximados para una sola barra: el de comandos es pequeño.
        partes = []
        if not modelo_voz.instalado():
            partes.append((modelo_voz.descargar, modelo_voz.TAMANO_APROX_MB))
        if not transcripcion.instalado():
            partes.append((transcripcion.descargar, transcripcion.TAMANO_APROX_MB))
        total = sum(peso for _, peso in partes)
        hecho = 0
        try:
            for descargar, peso in partes:
                base = hecho

                def avance(leidos: int, tamano: int, base=base, peso=peso) -> None:
                    fraccion = (base + peso * (leidos / tamano if tamano else 0)) / total
                    self._modelos_avance.emit("Preparando la voz de Notivoz…", fraccion)

                descargar(avance)
                hecho += peso
            self._modelos_listos.emit(True)
        except Exception:
            log.exception("No se pudo preparar la voz")
            self._modelos_listos.emit(False)

    def _al_avanzar_modelos(self, texto: str, fraccion: float) -> None:
        self.barra.set_valor(fraccion)
        self.estado.setText(f"{texto}  {int(fraccion * 100)}%")

    def _al_terminar_modelos(self, bien: bool) -> None:
        self._ocupado = False
        self.barra.hide()
        if bien:
            self._mostrar_estado("✓  Voz lista")
            self.modelos_preparados.emit()
            QTimer.singleShot(4000, self._restaurar_estado)
        else:
            self._mostrar_estado("No se pudo preparar la voz (revisa tu internet). Se reintentará al abrir.")

    def _restaurar_estado(self) -> None:
        if self._ocupado or self._version is not None:
            return
        if actualizacion.es_ejecutable():
            self._mostrar_estado("✓  Notivoz está en su última versión")
        else:
            self._mostrar_estado(f"v{APP_VERSION} · versión de desarrollo")

    def _mostrar_estado(self, texto: str) -> None:
        self.estado.setText(texto)
        self.estado.show()

"""Productividad en segundo plano: modo enfoque, rutinas por horario y el
aviso amable si abres apps de ocio en horario de trabajo."""

import logging
import time
from datetime import datetime, timedelta

from PySide6.QtCore import QObject, QTimer, Signal

from app.data.models import Estado
from app.services import ajustes, lanzador
from app.services import pendientes as servicio_pendientes
from app.services import rutinas as servicio_rutinas
from app.services.ajustes import Clave

log = logging.getLogger(__name__)


class ControladorEnfoque(QObject):
    """Un bloque de concentración con cuenta regresiva."""

    # Texto para mostrar («🎯 24:59 · Revisar servidor») o "" al terminar.
    cambiado = Signal(str)
    # Terminó el tiempo (id de la tarea o None). No se emite si se cancela.
    terminado = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fin = 0.0
        self._tarea_id: int | None = None
        self._titulo = ""
        self._reloj = QTimer(self, interval=1000)
        self._reloj.timeout.connect(self._avanzar)

    @property
    def activo(self) -> bool:
        return self._reloj.isActive()

    def iniciar(self, minutos: int, tarea_id: int | None = None) -> None:
        self._fin = time.monotonic() + minutos * 60
        self._tarea_id = tarea_id
        self._titulo = ""
        if tarea_id is not None and (tarea := servicio_pendientes.obtener(tarea_id)):
            self._titulo = tarea.titulo
            if tarea.estado == Estado.PENDIENTE:
                servicio_pendientes.cambiar_estado(tarea_id, Estado.EN_PROCESO)
        log.info("Modo enfoque: %d min (tarea %s)", minutos, tarea_id)
        self._reloj.start()
        self._avanzar()

    def terminar(self) -> bool:
        """Cancela el enfoque. Devuelve False si no había uno activo."""
        if not self.activo:
            return False
        self._reloj.stop()
        self.cambiado.emit("")
        return True

    def _avanzar(self) -> None:
        restante = int(self._fin - time.monotonic())
        if restante <= 0:
            self._reloj.stop()
            self.cambiado.emit("")
            self.terminado.emit(self._tarea_id)
            return
        minutos, segundos = divmod(restante, 60)
        texto = f"🎯 {minutos:02d}:{segundos:02d}"
        if self._titulo:
            texto += f" · {self._titulo}"
        self.cambiado.emit(texto)


class ProgramadorRutinas(QObject):
    """Cada medio minuto revisa si toca alguna rutina."""

    ejecutar = Signal(int)  # id de la rutina

    def __init__(self, parent=None, intervalo_ms: int = 30_000):
        super().__init__(parent)
        self._timer = QTimer(self, interval=intervalo_ms)
        self._timer.timeout.connect(self.revisar)
        self._timer.start()
        QTimer.singleShot(3000, self.revisar)  # al abrir la app

    def revisar(self) -> None:
        for rutina in servicio_rutinas.para_ejecutar():
            servicio_rutinas.marcar_ejecutada(rutina.id)
            log.info("Rutina «%s»", rutina.nombre)
            self.ejecutar.emit(rutina.id)


def en_horario_laboral(ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now()
    if ahora.weekday() not in ajustes.obtener(Clave.HORARIO_DIAS):
        return False
    inicio = ajustes.obtener(Clave.HORARIO_INICIO)
    fin = ajustes.obtener(Clave.HORARIO_FIN)
    return inicio <= ahora.strftime("%H:%M") < fin


class MonitorOcio(QObject):
    """Si en horario de trabajo pasas a una app de ocio y tienes tareas activas,
    avisa con la tarea más importante (como mucho una vez cada 30 minutos)."""

    aviso = Signal(str)  # título de la tarea a recordar

    ESPERA_ENTRE_AVISOS = timedelta(minutes=30)

    def __init__(self, parent=None, intervalo_ms: int = 5000):
        super().__init__(parent)
        self._anterior: str | None = None
        self._ultimo_aviso = datetime.min
        self._timer = QTimer(self, interval=intervalo_ms)
        self._timer.timeout.connect(self.revisar)
        self._timer.start()

    def revisar(self, ahora: datetime | None = None) -> None:
        if not ajustes.obtener(Clave.AVISO_OCIO):
            return
        ahora = ahora or datetime.now()
        actual = lanzador.proceso_en_primer_plano()
        acaba_de_abrir = actual != self._anterior
        self._anterior = actual
        if not acaba_de_abrir or actual not in {a.lower() for a in ajustes.obtener(Clave.APPS_OCIO)}:
            return
        if not en_horario_laboral(ahora) or ahora - self._ultimo_aviso < self.ESPERA_ENTRE_AVISOS:
            return
        # La primera tarea de la lista: en proceso o la más importante.
        activas = [p for p in servicio_pendientes.listar() if p.estado != Estado.REALIZADO]
        if activas:
            self._ultimo_aviso = ahora
            self.aviso.emit(activas[0].titulo)

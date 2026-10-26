"""Conecta la escucha con la IA: audio → Whisper → Claude → acciones y voz.

La transcripción y la IA corren en un hilo aparte (tardan unos segundos); los
resultados vuelven al hilo de la interfaz con señales.
"""

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal

from app.services import transcripcion
from app.services.asistente import Asistente, ErrorAsistente, Respuesta
from app.services.escucha import Escucha
from app.services.ia_herramientas import respuesta_confirmacion
from app.services.voz import voz
from app.ui.avisos import Tipo, avisar

log = logging.getLogger(__name__)


class ControladorIA(QObject):
    tareas_cambiaron = Signal()
    notas_cambiaron = Signal()
    activar_modo = Signal(int)
    # Para la burbuja: True mientras se piensa, False al terminar sin hablar.
    pensando = Signal(bool)
    _listo = Signal(object)  # Respuesta
    _fallo = Signal(str)

    def __init__(self, escucha: Escucha, parent=None):
        super().__init__(parent)
        self.asistente = Asistente()
        self._escucha = escucha
        self._ocupado = False
        escucha.dictado_listo.connect(self._al_dictar)
        self._listo.connect(self._al_responder)
        escucha.transcribir = self._transcribir
        self._fallo.connect(self._al_fallar)
        self.actualizar()

    def actualizar(self) -> None:
        """Lee los ajustes: si la IA quedó lista, la escucha manda los pedidos libres."""
        lista = self.asistente.disponible() and transcripcion.instalado()
        self._escucha.dictado_activo = lista
        if lista:
            # Cargar Whisper de antemano para que el primer pedido no tarde más.
            threading.Thread(target=self._precargar, name="Whisper", daemon=True).start()

    @staticmethod
    def _precargar() -> None:
        try:
            transcripcion.transcriptor().precargar()
        except Exception:
            log.exception("No se pudo cargar Whisper")

    # --- Flujo ---

    @staticmethod
    def _transcribir(audio: bytes) -> str:
        """Lo usa la escucha (en su hilo) al terminar cada pedido."""
        inicio = time.monotonic()
        try:
            texto = transcripcion.transcriptor().transcribir(audio)
        except Exception:
            log.exception("No se pudo transcribir")
            return ""
        log.info("Whisper: %.1f s", time.monotonic() - inicio)
        return texto

    def _al_dictar(self, _audio: bytes, texto: str) -> None:
        if self._ocupado:
            return
        self._ocupado = True
        self.pensando.emit(True)
        threading.Thread(target=self._procesar, args=(texto,), name="IA", daemon=True).start()

    def _procesar(self, texto: str) -> None:
        try:
            transcrito = time.monotonic()
            if not texto:
                self._listo.emit(Respuesta(""))
                return
            pendiente = self.asistente.herramientas.pendiente
            if pendiente is not None and pendiente.vigente:
                # Respuestas cortas («sí», «dale», «no») se resuelven al instante, sin IA.
                decision = respuesta_confirmacion(texto)
                if decision is not None:
                    self.asistente.herramientas.pendiente = None
                    self._listo.emit(self._resolver_confirmacion(pendiente, decision))
                    return
                if pendiente.es_eliminacion:
                    # Otra forma de responder: la IA la interpreta y, si es un sí,
                    # confirma (lo preparado sigue pendiente solo durante este turno).
                    self.asistente.registrar_evento(
                        f"preparaste eliminar «{pendiente.titulo}» y le preguntaste si está seguro"
                    )
                else:
                    self.asistente.herramientas.pendiente = None
            respuesta = self.asistente.responder(texto)
            # Solo tiempos (nunca lo que dijiste), para medir la fluidez.
            log.info("Pedido por voz: IA %.1f s", time.monotonic() - transcrito)
            self._listo.emit(respuesta)
        except ErrorAsistente as error:
            self._fallo.emit(str(error))
        except Exception:
            log.exception("Error al procesar un pedido por voz")
            self._fallo.emit("Algo falló al procesar tu pedido.")

    def _resolver_confirmacion(self, pendiente, confirma: bool) -> Respuesta:
        """Las acciones delicadas las confirma el usuario, comprobado aquí sin la IA."""
        respuesta = Respuesta("")
        if not pendiente.es_eliminacion:
            if confirma:
                pendiente.ejecutar()
                respuesta.texto = f"Listo, cerré {pendiente.titulo}."
                self.asistente.registrar_evento(f"el usuario confirmó y se forzó el cierre de {pendiente.titulo}")
            else:
                respuesta.texto = f"De acuerdo, dejo {pendiente.titulo} abierto."
                self.asistente.registrar_evento(f"el usuario no quiso forzar el cierre de {pendiente.titulo}")
            return respuesta
        if confirma:
            pendiente.ejecutar()
            unico = len(pendiente.ids) == 1
            respuesta.texto = f"Listo, eliminé «{pendiente.titulo}»." if unico else f"Listo, eliminé {pendiente.titulo}."
            respuesta.eliminado = pendiente.titulo
            if pendiente.tipo == "tarea":
                respuesta.efectos.tareas = True
            else:
                respuesta.efectos.notas = True
            self.asistente.registrar_evento(f"el usuario confirmó y se eliminó «{pendiente.titulo}»")
        else:
            respuesta.texto = "De acuerdo, no lo elimino."
            self.asistente.registrar_evento(f"el usuario canceló eliminar «{pendiente.titulo}»")
        return respuesta

    def _al_responder(self, respuesta: Respuesta) -> None:
        self._ocupado = False
        efectos = respuesta.efectos
        if efectos.tareas:
            self.tareas_cambiaron.emit()
        if efectos.notas:
            self.notas_cambiaron.emit()
        if respuesta.eliminado:
            avisar(f"Eliminado: «{respuesta.eliminado}»", Tipo.ELIMINADO)
        for comando_id in efectos.comandos_activados:
            self.activar_modo.emit(comando_id)
        if respuesta.texto:
            voz().hablar(respuesta.texto)
            self._escucha.permitir_contestar_encima()
        elif not efectos.comandos_activados:
            self.pensando.emit(False)
        # Conversación fluida: tras cualquier respuesta (o si no se entendió lo que
        # dijiste) puedes seguir hablando sin repetir «Notivoz».
        self._escucha.esperar_respuesta()

    def _al_fallar(self, mensaje: str) -> None:
        self._ocupado = False
        voz().hablar(mensaje)

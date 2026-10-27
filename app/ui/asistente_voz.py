"""Conecta la escucha con la IA: audio → Whisper → Claude → acciones y voz.

La transcripción y la IA corren en un hilo aparte (tardan unos segundos); los
resultados vuelven al hilo de la interfaz con señales.

Conversación:
- «Notivoz» hace aparecer la burbuja; al tocarla te escucha hasta que dejas de
  hablar, y luego procesa tu pedido.
- Si la tocas mientras procesa, lo nuevo que digas se suma a lo anterior: la
  respuesta anterior no se dice (sus acciones sí se hacen) y se responde todo junto.
- Un «gracias» u «ok» se responde con una sonrisa (sin hablar ni gastar IA).
"""

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal

from app.services import ajustes, transcripcion
from app.services.asistente import Asistente, ErrorAsistente, Respuesta
from app.services.escucha import Escucha
from app.services.ia_herramientas import deshacer_ultima_eliminacion, normalizar
from app.services.voz import voz
from app.ui.avisos import Tipo, avisar

log = logging.getLogger(__name__)

# «Gracias», «ok», «perfecto»…: se responde con un gesto, sin gastar IA.
_PALABRAS_DE_CIERRE = set("""
gracias muchas mil ok okey okay vale perfecto perfecta genial listo lista excelente
chevere bacan buenisimo buenisima buena bueno bien super increible joya dale
entendido de nada notivoz noti voz muy ya va esta todo
por la el lo eso te tu ayuda agradezco hoy siempre crack amigo
""".split())


def es_cierre(texto: str) -> bool:
    """¿Solo agradece o da por terminado («ok, gracias», «perfecto»)?"""
    palabras = normalizar(texto).replace(",", " ").replace(".", " ").replace("!", " ").split()
    return 0 < len(palabras) <= 8 and set(palabras) <= _PALABRAS_DE_CIERRE


class ControladorIA(QObject):
    tareas_cambiaron = Signal()
    notas_cambiaron = Signal()
    activar_modo = Signal(int)
    # "" = mostrar la ventana; si no, el nombre de la sección.
    mostrar_ventana = Signal(str)
    # Para la burbuja: True mientras se piensa, False al terminar sin hablar.
    pensando = Signal(bool)
    decir_en_nube = Signal(str)
    # Una carita en la burbuja: ya (le agradeciste) o al terminar de hablar (hizo algo).
    gesto = Signal()
    gesto_al_terminar = Signal()
    # Para la burbuja: te está escuchando / un aviso breve.
    escuchando = Signal()
    mensaje = Signal(str)
    _listo = Signal(object)  # Respuesta

    def __init__(self, escucha: Escucha, parent=None):
        super().__init__(parent)
        self.asistente = Asistente()
        self._escucha = escucha
        self._ocupado = False  # la IA está procesando un pedido
        self._esperando_pedido = False  # tocaste la burbuja y aún no hablas
        self._cola: list[str] = []  # lo que dijiste mientras procesaba
        self._retenida: Respuesta | None = None  # llegó mientras volvías a hablar
        escucha.dictado_listo.connect(self._al_dictar)
        escucha.sin_pedido.connect(self._sin_pedido)
        escucha.pedido_terminado.connect(lambda: self.pensando.emit(True))
        escucha.pedido_continua.connect(self.escuchando.emit)
        escucha.transcribir = self._transcribir
        self._listo.connect(self._al_responder)
        self.actualizar()

    def actualizar(self) -> None:
        """Lee los ajustes: si la IA quedó lista, la escucha manda los pedidos libres."""
        lista = self.asistente.disponible() and transcripcion.instalado()
        self._escucha.dictado_activo = lista
        if lista:
            # Cargar Whisper de antemano para que el primer pedido no tarde más.
            threading.Thread(target=self._precargar, name="Whisper", daemon=True).start()
            self.preparar_confirmaciones()

    @staticmethod
    def preparar_confirmaciones() -> None:
        """Grabar de antemano las confirmaciones («¡Listo! Tarea creada.») con la
        personalidad y la voz actuales: así suenan apenas termina el pedido."""
        voz().preparar(ajustes.frases_actuales().confirmaciones())

    @staticmethod
    def _precargar() -> None:
        try:
            transcripcion.transcriptor().precargar()
        except Exception:
            log.exception("No se pudo cargar Whisper")

    # --- Efectos (los usa también el chat) ---

    def aplicar_efectos(self, respuesta: Respuesta) -> None:
        """Refrescar vistas, avisos, abrir la ventana o un modo."""
        efectos = respuesta.efectos
        if efectos.tareas:
            self.tareas_cambiaron.emit()
        if efectos.notas:
            self.notas_cambiaron.emit()
        if efectos.eliminado:
            avisar(f"Eliminado: {efectos.eliminado}", Tipo.ELIMINADO, ("Deshacer", self.deshacer))
        if efectos.restaurado:
            avisar(f"Recuperado: {efectos.restaurado}")
        if efectos.abrir_ventana is not None:
            self.mostrar_ventana.emit(efectos.abrir_ventana)
        for comando_id in efectos.comandos_activados:
            self.activar_modo.emit(comando_id)

    def deshacer(self) -> None:
        restaurado = deshacer_ultima_eliminacion()
        if restaurado is None:
            avisar("Ya no se puede deshacer", Tipo.INFO)
            return
        self.tareas_cambiaron.emit()
        self.notas_cambiaron.emit()
        avisar(f"Recuperado: {restaurado[1]}")
        self.asistente.registrar_evento(f"el usuario recuperó lo eliminado ({restaurado[1]})")

    # --- Flujo por voz ---

    def al_oir_activacion(self) -> None:
        """Se oyó «Notivoz»: mientras decides si tocas la burbuja, dejar lista la
        conexión con la IA (así el pedido no espera a abrirla)."""
        if self._escucha.dictado_activo:
            threading.Thread(target=self.asistente.precalentar, name="Precalentar", daemon=True).start()

    def al_tocar(self) -> None:
        """Tocaste la burbuja: escuchar tu pedido."""
        if not self._escucha.dictado_activo:
            self.mensaje.emit("Activa el asistente en Configuración para hablar conmigo.")
            return
        if not self._escucha.activa:
            self.mensaje.emit("Enciende el micrófono para hablar conmigo.")
            return
        voz().detener()
        self._esperando_pedido = True
        self._escucha.escuchar_pedido()
        self.escuchando.emit()

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

    def _al_dictar(self, _audio: bytes, texto: str, _origen: str) -> None:
        self._esperando_pedido = False
        self._retenida = None  # lo nuevo reemplaza a la respuesta que esperaba
        self.pensando.emit(True)
        if self._ocupado:
            # Sigue procesando lo anterior: esto se suma y se responde todo junto.
            if texto:
                self._cola.append(texto)
            return
        self._empezar(texto)

    def _empezar(self, texto: str) -> None:
        self._ocupado = True
        threading.Thread(target=self._procesar, args=(texto,), name="IA", daemon=True).start()

    def _sin_pedido(self) -> None:
        """Tocaste la burbuja pero no dijiste nada."""
        self._esperando_pedido = False
        if self._retenida is not None:
            respuesta, self._retenida = self._retenida, None
            self._mostrar(respuesta)
        elif self._ocupado:
            self.pensando.emit(True)
        else:
            self.mensaje.emit("No te escuché. Presióname y vuelve a intentarlo.")

    def _procesar(self, texto: str) -> None:
        try:
            if not texto:
                self._listo.emit(Respuesta("", gesto="no_entendi"))
                return
            # ¿Forzar un cierre o apagar ya? «sí»/«no» se resuelven sin IA.
            confirmada = self.asistente.resolver_pendiente(texto)
            if confirmada is not None:
                self._listo.emit(confirmada)
                return
            if es_cierre(texto):
                # «Gracias», «ok»…: una sonrisa, sin hablar ni gastar IA.
                self._listo.emit(Respuesta("", gesto="gesto"))
                return
            inicio = time.monotonic()
            respuesta = self.asistente.responder(texto)
            # Solo tiempos (nunca lo que dijiste), para medir la fluidez.
            log.info("Pedido por voz: IA %.1f s", time.monotonic() - inicio)
            self._listo.emit(respuesta)
        except ErrorAsistente as error:
            self._listo.emit(Respuesta(str(error)))
        except Exception:
            log.exception("Error al procesar un pedido por voz")
            self._listo.emit(Respuesta("Algo falló al procesar tu pedido."))

    def _al_responder(self, respuesta: Respuesta) -> None:
        self._ocupado = False
        self.aplicar_efectos(respuesta)
        if self._cola:
            # Hablaste de nuevo mientras procesaba: responder todo junto (lo
            # anterior ya está en la conversación, solo falta lo nuevo).
            texto = "[Continúa mi pedido anterior] " + " ".join(self._cola)
            self._cola.clear()
            self._empezar(texto)
            return
        if self._esperando_pedido:
            # Volviste a tocar la burbuja: si no dices nada, se dice esta respuesta.
            self._retenida = respuesta
            return
        self._mostrar(respuesta)

    def _mostrar(self, respuesta: Respuesta) -> None:
        if respuesta.gesto == "gesto":
            self.gesto.emit()
        elif respuesta.gesto == "no_entendi":
            self.mensaje.emit("No te entendí. Presióname y repítelo, por favor.")
        elif respuesta.texto:
            voz().hablar(respuesta.texto)
            self.decir_en_nube.emit(respuesta.texto)
        elif not respuesta.efectos.comandos_activados:
            # (Un modo activado se anuncia solo.)
            self.pensando.emit(False)
        if respuesta.efectos.hizo_algo and respuesta.gesto != "gesto":
            # Hizo lo que pediste: si no le vuelves a hablar, se despide con una carita.
            self.gesto_al_terminar.emit()

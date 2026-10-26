"""Conecta la escucha con la IA: audio → Whisper → Claude → acciones y voz.

La transcripción y la IA corren en un hilo aparte (tardan unos segundos); los
resultados vuelven al hilo de la interfaz con señales.

Conversación:
- Si Notivoz te pregunta algo, lo puedes contestar sin decir «Notivoz».
- Si terminó lo que pediste, te escucha solo un par de segundos más: un
  «gracias» u «ok» se responde con una sonrisa (sin hablar); si lo que dices no
  es para ella, lo ignora. Después hay que volver a decir «Notivoz».
"""

import logging
import threading
import time

from PySide6.QtCore import QObject, Signal

from app.services import transcripcion
from app.services.asistente import Asistente, ErrorAsistente, Respuesta
from app.services.escucha import Escucha
from app.services.ia_herramientas import deshacer_ultima_eliminacion, normalizar, respuesta_confirmacion
from app.services.voz import voz
from app.ui.avisos import Tipo, avisar

log = logging.getLogger(__name__)

_SEGUNDOS_PARA_CONTESTAR = 8  # Notivoz te preguntó algo
_SEGUNDOS_TRAS_TERMINAR = 2.5  # terminó lo que pediste: por si agradeces o sigues

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
    gesto = Signal()
    _listo = Signal(object, str)  # Respuesta, origen
    _fallo = Signal(str)

    def __init__(self, escucha: Escucha, parent=None):
        super().__init__(parent)
        self.asistente = Asistente()
        self._escucha = escucha
        self._ocupado = False
        escucha.dictado_listo.connect(self._al_dictar)
        escucha.transcribir = self._transcribir
        self._listo.connect(self._al_responder)
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

    def _al_dictar(self, _audio: bytes, texto: str, origen: str) -> None:
        if self._ocupado:
            return
        self._ocupado = True
        if origen != "cierre":
            self.pensando.emit(True)
        threading.Thread(target=self._procesar, args=(texto, origen), name="IA", daemon=True).start()

    def _procesar(self, texto: str, origen: str) -> None:
        try:
            if not texto:
                self._listo.emit(Respuesta(""), origen)
                return
            pendiente = self.asistente.herramientas.pendiente
            if pendiente is not None and pendiente.vigente:
                # ¿Forzar el cierre de la app? «sí»/«no» se resuelven aquí, sin IA.
                decision = respuesta_confirmacion(texto)
                self.asistente.herramientas.pendiente = None
                if decision is not None:
                    if decision:
                        pendiente.ejecutar()
                    texto_final = (
                        f"Listo, cerré {pendiente.titulo}." if decision else f"De acuerdo, dejo {pendiente.titulo} abierto."
                    )
                    self.asistente.registrar_evento(texto_final)
                    self._listo.emit(Respuesta(texto_final), origen)
                    return
            if es_cierre(texto):
                # «Gracias», «ok»…: una sonrisa, sin hablar ni gastar IA.
                self._listo.emit(Respuesta("", gesto="gesto"), origen)
                return
            if origen == "cierre":
                # Hablaste justo después de que Notivoz terminó: puede no ser para ella.
                texto = f"[Después de terminar] {texto}"
            inicio = time.monotonic()
            respuesta = self.asistente.responder(texto)
            # Solo tiempos (nunca lo que dijiste), para medir la fluidez.
            log.info("Pedido por voz: IA %.1f s", time.monotonic() - inicio)
            self._listo.emit(respuesta, origen)
        except ErrorAsistente as error:
            self._fallo.emit(str(error))
        except Exception:
            log.exception("Error al procesar un pedido por voz")
            self._fallo.emit("Algo falló al procesar tu pedido.")

    def _al_responder(self, respuesta: Respuesta, origen: str) -> None:
        self._ocupado = False
        self.aplicar_efectos(respuesta)
        if respuesta.gesto == "gesto":
            self.gesto.emit()
            return
        if respuesta.gesto == "ignorar":
            self.pensando.emit(False)
            return
        if respuesta.texto:
            voz().hablar(respuesta.texto)
            self.decir_en_nube.emit(respuesta.texto)
            self._escucha.permitir_contestar_encima()
            if respuesta.espera_respuesta or respuesta.espera_confirmacion:
                self._escucha.esperar_respuesta(_SEGUNDOS_PARA_CONTESTAR)
            else:
                self._escucha.esperar_respuesta(_SEGUNDOS_TRAS_TERMINAR, cierre=True)
            return
        if not respuesta.efectos.comandos_activados:
            self.pensando.emit(False)
        if origen in ("activacion", "respuesta") and not respuesta.efectos.comandos_activados:
            # No se entendió lo que dijiste: te sigue escuchando un momento.
            self._escucha.esperar_respuesta(_SEGUNDOS_PARA_CONTESTAR)

    def _al_fallar(self, mensaje: str) -> None:
        self._ocupado = False
        voz().hablar(mensaje)
        self.decir_en_nube.emit(mensaje)

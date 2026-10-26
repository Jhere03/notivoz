"""Reconocimiento de voz offline (Vosk) para los comandos: «Notivoz, modo relax».

Escucha el micrófono en un hilo propio con una gramática cerrada: solo puede
"oír" la palabra de activación y las frases de los comandos (y su cierre), lo
que lo hace preciso y evita que cualquier conversación dispare algo. Mientras
Notivoz habla, solo escucha las palabras para interrumpirlo.

Con la IA activa, lo que se dice tras «Notivoz» y no es un comando exacto se
entrega como audio (dictado_listo) para transcribirlo con Whisper: ningún
pedido llega a la IA sin la palabra de activación o sin que Notivoz haya
hecho una pregunta justo antes.
"""

import collections
import json
import logging
import unicodedata
from collections.abc import Callable
import queue
import threading
import time
import winsound

import numpy as np
from PySide6.QtCore import QObject, Signal

from app.services import modelo_voz
from app.services.audio import CanceladorEco, indice_dispositivo, nombres_dispositivos, reproductor
from app.services.microfono import BLOQUE, FRECUENCIA, nivel_de
from app.services.voz import voz

log = logging.getLogger(__name__)

# «Notivoz» no es una palabra del español, pero «noti voz» suena igual y el
# modelo sí conoce esas dos palabras.
PALABRA_ACTIVACION = "noti voz"
NOMBRE_ACTIVACION = "Notivoz"

# Palabras comunes que se añaden a la gramática como "relleno": así una
# conversación normal se reconoce como estas palabras y no se fuerza a encajar
# en un comando («el modo de trabajo de mi jefe» ≠ «modo trabajo»).
_RELLENO = """
a al algo algunos ahora ahí allá aquí así ayer bien bueno cada casa como con cosa
creo cuando cuál de del desde después día dice digo donde dos e el ella ellos en
entonces era es esa ese eso esta este esto está están estoy fue gente gracias
haber hace hacer hay hasta hola hoy ir la las le les lo los luego mal mamá mañana
me mejor mi mis mucho muy más nada no noche nos nosotros o otra otro para pero
poco por porque puede pues que quiero qué se sea ser si sí siempre sin sobre solo
son su sus también tan tanto te tengo tiempo tiene todo todos tu tú un una uno
va vamos ver vez voy y ya yo amigo amigos trabajo comer comida jefe juego juegos
mira oye espera vale claro sea dame pon quita abre cierra música video casa
eh em mm digamos además
""".split()

_FRECUENCIA = FRECUENCIA
_CONFIANZA_MINIMA = 0.55
_SEGUNDOS_TRAS_ACTIVACION = 5  # tras decir solo «Notivoz», tiempo para decir el comando
_SEGUNDOS_PARA_RESPONDER = 8  # tras una pregunta de Notivoz, tiempo para contestar
# Pedidos libres (con la IA): termina tras esta pausa, y como mucho dura esto.
_PAUSA_FIN_DICTADO = 1.3
# Si la frase quedó colgando («…y», «…o sea», «…este»), estás pensando: esperar más.
_PAUSA_PENSANDO = 3.0
# Nivel (0 a 1) a partir del cual un bloque se considera voz: retomaste la frase.
_NIVEL_VOZ = 0.12
_MAXIMO_DICTADO = 45
_CONECTORES = set("""
y e o u que pero este esto eh em mm mmm entonces pues bueno como sea porque de del con para
por la el los las un una unos mi mis tu a al en si cuando donde también además osea digamos
""".split())
_MAXIMO_FRASE_BYTES = 15 * FRECUENCIA * 2  # audio de la frase en curso que se guarda como mucho
# Para callar a Notivoz mientras habla.
_PALABRAS_INTERRUPCION = ("noti voz", "espera", "silencio", "cállate")
_CONFIANZA_INTERRUPCION = 0.85
_NUMEROS = "uno dos tres cuatro cinco seis siete ocho nueve diez once doce media cuarto".split()
# Contestar encima (con cancelación de eco): voz que supere al eco residual.
_UMBRAL_VOZ = 600  # RMS mínimo (voz normal: 2000 a 4000)
_VECES_SOBRE_ECO = 3.0
_BLOQUES_CON_VOZ = 4  # 0,4 s seguidos
_BLOQUES_PRECARGA = 12  # 1,2 s de audio previo que se conserva para tu respuesta

_modelo = None
_candado_modelo = threading.Lock()


def obtener_modelo():
    """Carga el modelo una sola vez (tarda un par de segundos)."""
    global _modelo
    with _candado_modelo:
        if _modelo is None:
            import vosk

            vosk.SetLogLevel(-1)
            _modelo = vosk.Model(str(modelo_voz.carpeta_modelo()))
        return _modelo


def palabras_desconocidas(frase: str) -> list[str]:
    """Palabras de la frase que el modelo no conoce (no las podrá reconocer)."""
    if not modelo_voz.instalado():
        return []
    modelo = obtener_modelo()
    return [p for p in frase.split() if modelo.vosk_model_find_word(p) < 0]


def dispositivos_entrada() -> list[str]:
    """Nombres de los micrófonos disponibles (sin duplicados de otras APIs de audio)."""
    return nombres_dispositivos(entrada=True)


# Palabras con las que una frase queda colgando: quien habla sigue pensando.
_COLGANTES = set("""
y e o u que pero este eh em mm mmm entonces pues como porque de del con para por la el
los las un una mi mis a al en si cuando donde sea digamos osea también además
""".split())


def quedo_a_medias(texto: str) -> bool:
    """«…con un cliente y», «o sea…», «este,»: el pedido no terminó."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    palabras = sin_tildes.strip(" .,;:!?").split()
    return bool(palabras) and (palabras[-1] in _COLGANTES or texto.rstrip().endswith(("…", "...", ",")))


# «Notivoz, cierra modo relax»: palabras para cerrar lo que abrió un comando.
VERBOS_CIERRE = ("cierra", "termina", "apaga", "fin del")


class _Interruptor:
    """Decide si interrumpiste a Notivoz mientras hablaba.

    Analiza el audio ya sin eco, bloque a bloque:
    - «Notivoz», «espera», «silencio»… callan a Notivoz siempre.
    - Si además se permite contestar encima (respuestas de la IA), cualquier
      frase tuya lo calla y se toma como tu respuesta.

    Para no confundirse con el eco que queda o con ruido (música, una tos):
    exige voz claramente más fuerte que ese residuo, sostenida unos 0,4 s, y con
    palabras reconocibles. El reconocedor también conoce palabras comunes,
    así el ruido no se "fuerza" a parecer «espera».
    """

    def __init__(self, modelo, vosk) -> None:
        conocidas = lambda frase: all(modelo.vosk_model_find_word(p) >= 0 for p in frase.split())
        self._claves = [p for p in _PALABRAS_INTERRUPCION if conocidas(p)]
        relleno = [p for p in dict.fromkeys(_RELLENO + _NUMEROS) if conocidas(p) and p not in self._claves]
        gramatica = [*self._claves, *relleno, "[unk]"]
        self._reconocedor = vosk.KaldiRecognizer(modelo, _FRECUENCIA, json.dumps(gramatica, ensure_ascii=False))
        self._reconocedor.SetWords(True)
        self._niveles: collections.deque[float] = collections.deque(maxlen=30)
        self._reciente: collections.deque[bytes] = collections.deque(maxlen=_BLOQUES_PRECARGA)
        self._seguidos = 0
        self._fuerte_hace = 99  # bloques desde el último bloque con voz fuerte

    def reiniciar(self) -> None:
        self._reconocedor.Reset()
        self._niveles.clear()
        self._reciente.clear()
        self._seguidos = 0
        self._fuerte_hace = 99

    def audio_reciente(self) -> bytes:
        """Lo último que se oyó (para no perder el inicio de tu respuesta)."""
        return b"".join(self._reciente)

    def procesar(self, datos: bytes, contestar_encima: bool) -> str | None:
        """'clave' (dijiste «espera»…), 'voz' (le contestaste encima) o None."""
        self._reciente.append(datos)
        muestras = np.frombuffer(datos, dtype=np.int16).astype(np.float64)
        rms = float(np.sqrt(np.mean(muestras**2)))
        piso = float(np.percentile(self._niveles, 30)) if len(self._niveles) >= 5 else _UMBRAL_VOZ
        if rms > max(_UMBRAL_VOZ, _VECES_SOBRE_ECO * piso):
            self._seguidos += 1
            self._fuerte_hace = 0
        else:
            self._seguidos = 0
            self._fuerte_hace += 1
            self._niveles.append(rms)

        if self._reconocedor.AcceptWaveform(datos):
            resultado = json.loads(self._reconocedor.Result())
            palabras = [p for p in resultado.get("result", []) if p.get("word") != "[unk]"]
            dicho = " ".join(p["word"] for p in palabras)
            if self._fuerte_hace <= _BLOQUES_PRECARGA and self._es_clave(palabras, dicho):
                return "clave"
            return None
        if contestar_encima and self._seguidos >= _BLOQUES_CON_VOZ:
            parcial = json.loads(self._reconocedor.PartialResult()).get("partial", "")
            if any(p != "[unk]" for p in parcial.split()):
                return "voz"
        return None

    def _es_clave(self, palabras: list[dict], dicho: str) -> bool:
        propia = voz().texto_actual.lower().replace(" ", "")
        for clave in self._claves:
            if clave not in dicho or clave.replace(" ", "") in propia:
                continue
            confianzas = [p.get("conf", 0) for p in palabras if p["word"] in clave.split()]
            if confianzas and min(confianzas) >= _CONFIANZA_INTERRUPCION:
                return True
        return False


class Escucha(QObject):
    comando_detectado = Signal(int)
    cierre_detectado = Signal(int)  # «cierra modo relax»
    # Se oyó «Notivoz» (también a mitad de frase, para reaccionar enseguida).
    activacion_oida = Signal()
    estado_cambiado = Signal(str, bool)  # texto para mostrar, ¿escuchando?
    # Con la IA activa: un pedido libre (audio PCM de 16 bits a 16 kHz y su texto,
    # vacío si no hay transcriptor).
    dictado_listo = Signal(bytes, str)
    # El usuario interrumpió a Notivoz mientras hablaba («Notivoz», «espera»…).
    interrupcion = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dispositivo: str | None = None  # None = micrófono por defecto
        # Volumen actual de la voz (0 a 1), para animar la burbuja.
        self.nivel = 0.0
        # Con la IA activa, lo que no es un comando exacto se manda como dictado.
        self.dictado_activo = False
        self._frases: dict[str, int] = {}
        self._cambio_frases = threading.Event()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        # Segundos para contestar sin decir «Notivoz» cuando él termine de hablar.
        self._respuesta_esperada = 0.0
        # Mientras Notivoz pregunta, cualquier respuesta tuya lo interrumpe.
        self._interrupcion_libre = False
        # Voz a texto para los pedidos libres (Whisper); lo pone quien usa la IA.
        self.transcribir: Callable[[bytes], str] | None = None

    @property
    def activa(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def set_frases(self, frases: dict[str, int]) -> None:
        """frase normalizada → id del comando. Se aplica sin reiniciar la escucha."""
        self._frases = dict(frases)
        self._cambio_frases.set()

    def permitir_contestar_encima(self) -> None:
        """Mientras Notivoz dice la respuesta de la IA, hablarle encima lo calla
        y lo que digas se toma como tu respuesta o tu nuevo pedido."""
        self._interrupcion_libre = True

    def esperar_respuesta(self, segundos: float = _SEGUNDOS_PARA_RESPONDER) -> None:
        """Conversación en curso: cuando Notivoz termine de hablar (o ya, si no
        está hablando), se le puede contestar unos segundos sin decir «Notivoz»."""
        self._respuesta_esperada = segundos
        self._interrupcion_libre = True

    def iniciar(self) -> None:
        if self.activa:
            return
        if not modelo_voz.instalado():
            self.estado_cambiado.emit("Falta el modelo de voz", False)
            return
        self._parar.clear()
        self._hilo = threading.Thread(target=self._trabajar, name="Escucha", daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=3)
        self._hilo = None

    # --- Hilo de escucha -----------------------------------------------------

    def _gramatica(self, modelo) -> tuple[list[str], dict[str, int]]:
        validas = {
            frase: id_
            for frase, id_ in self._frases.items()
            if all(modelo.vosk_model_find_word(p) >= 0 for p in frase.split())
        }
        frases = [PALABRA_ACTIVACION]
        for frase in validas:
            frases += [frase, f"{PALABRA_ACTIVACION} {frase}"]
            frases += [f"{PALABRA_ACTIVACION} {verbo} {frase}" for verbo in VERBOS_CIERRE]
            frases += [f"{verbo} {frase}" for verbo in VERBOS_CIERRE]
        relleno = [p for p in dict.fromkeys(_RELLENO) if modelo.vosk_model_find_word(p) >= 0]
        return frases + relleno + ["[unk]"], validas

    def _trabajar(self) -> None:
        import sounddevice as sd
        import vosk

        self.estado_cambiado.emit("Cargando reconocimiento de voz…", False)
        try:
            modelo = obtener_modelo()
        except Exception:
            log.exception("No se pudo cargar el modelo de voz")
            self.estado_cambiado.emit("Error al cargar el modelo de voz", False)
            return

        audio: queue.Queue[tuple[bytes, bytes | None]] = queue.Queue()
        try:
            stream, duplex = self._abrir_audio(
                sd,
                indice_dispositivo(self.dispositivo, entrada=True),
                indice_dispositivo(reproductor().salida, entrada=False),
                audio,
            )
        except Exception:
            log.exception("No se pudo abrir el micrófono")
            self.estado_cambiado.emit("No se encontró el micrófono", False)
            return
        cancelador = CanceladorEco()
        precarga: bytearray | None = None  # audio tuyo al interrumpir a Notivoz

        # Mientras Notivoz habla solo se escucha para interrumpirlo.
        interruptor = _Interruptor(modelo, vosk)
        armado_hasta = 0.0
        activacion_avisada = False  # ya se avisó «Notivoz» en esta frase
        silenciado = False
        reconocedor = None
        validas: dict[str, int] = {}
        frase_audio = bytearray()  # audio de la frase en curso (para el dictado)
        dictado = bytearray()  # pedido libre acumulado
        dictado_fin = 0.0  # si no se vuelve a hablar antes de esto, el pedido terminó
        dictado_inicio = 0.0
        bloques_voz = 0
        dictado_extendido = False
        # Audio de un «Notivoz» suelto: Vosk a veces corta ahí el inicio del pedido
        # («Notivoz, recuér|dame…»), así que se antepone al dictado que siga.
        audio_activacion = b""
        self._cambio_frases.set()
        reproductor().set_conductor_externo(duplex)
        with stream:
            self.estado_cambiado.emit("Escuchando", True)
            log.info("Escucha de comandos iniciada")
            while not self._parar.is_set():
                if self._cambio_frases.is_set():
                    self._cambio_frases.clear()
                    gramatica, validas = self._gramatica(modelo)
                    reconocedor = vosk.KaldiRecognizer(
                        modelo, _FRECUENCIA, json.dumps(gramatica, ensure_ascii=False)
                    )
                    reconocedor.SetWords(True)
                try:
                    datos = audio.get(timeout=0.25)
                except queue.Empty:
                    datos = None
                ahora = time.monotonic()

                # Pedido libre en curso: termina tras una pausa, o al pasar el máximo.
                if dictado and (
                    (dictado_fin and ahora > dictado_fin) or ahora - dictado_inicio > _MAXIMO_DICTADO
                ):
                    cortado = not dictado_fin  # llegó al máximo a mitad de frase
                    if cortado:
                        dictado += frase_audio
                        frase_audio.clear()
                        reconocedor.Reset()
                    texto = self.transcribir(bytes(dictado)) if self.transcribir else ""
                    if not cortado and not dictado_extendido and quedo_a_medias(texto):
                        # «…con un cliente y»: estabas pensando. Esperar un poco más
                        # (el audio que llegue mientras tanto no se pierde).
                        dictado_extendido = True
                        dictado_fin = time.monotonic() + _PAUSA_PENSANDO
                        self.activacion_oida.emit()
                        continue
                    self.dictado_listo.emit(bytes(dictado), texto)
                    dictado.clear()
                    dictado_fin = 0.0
                    dictado_extendido = False
                    armado_hasta = 0.0
                if datos is None:
                    continue
                mic, referencia = datos
                if referencia is not None:
                    # Restar el eco de la voz de Notivoz de lo que capta el micrófono.
                    datos = cancelador.procesar(
                        np.frombuffer(mic, dtype=np.int16), np.frombuffer(referencia, dtype=np.int16)
                    ).tobytes()
                else:
                    datos = mic

                # Mientras Notivoz habla no se escuchan comandos (para no oírse a
                # sí mismo), salvo para interrumpirlo.
                if voz().ocupada():
                    if not silenciado:
                        silenciado = True
                        interruptor.reiniciar()
                    self.nivel = 0.0
                    if precarga is not None:
                        precarga += datos  # ya lo interrumpiste: seguir guardando lo que dices
                        continue
                    if not (self.dictado_activo and voz().hablando):
                        continue
                    # Contestar encima solo cuando el eco ya se cancela bien (o no hay eco,
                    # como con audífonos); si no, se confundiría con su propia voz.
                    contestar_encima = self._interrupcion_libre and cancelador.listo
                    tipo = interruptor.procesar(datos, contestar_encima)
                    if tipo == "clave":
                        log.info("Notivoz fue interrumpido por el usuario («espera»)")
                        voz().detener()
                        self._respuesta_esperada = 0.0
                        self._interrupcion_libre = False
                        armado_hasta = ahora + _SEGUNDOS_TRAS_ACTIVACION
                        winsound.Beep(988, 120)
                        self.interrupcion.emit()
                    elif tipo == "voz":
                        # Le hablaste encima: callarlo y tomar lo que dijiste como
                        # tu respuesta o tu nuevo pedido.
                        log.info("Notivoz fue interrumpido por una respuesta del usuario")
                        voz().detener()
                        precarga = bytearray(interruptor.audio_reciente())
                        self._interrupcion_libre = False
                        self.interrupcion.emit()
                    continue
                if silenciado:
                    silenciado = False
                    reconocedor.Reset()
                    frase_audio.clear()
                    if precarga is not None:
                        # Lo que dijiste mientras Notivoz hablaba es el inicio de tu respuesta.
                        reconocedor.AcceptWaveform(bytes(precarga))
                        frase_audio += precarga
                        precarga = None
                        armado_hasta = ahora + _SEGUNDOS_TRAS_ACTIVACION
                        self._respuesta_esperada = 0.0
                    self._interrupcion_libre = False
                # Seguir la conversación: tras la respuesta de Notivoz (o si no te
                # entendió), escucharte unos segundos sin exigir «Notivoz».
                if self._respuesta_esperada:
                    if self.dictado_activo:
                        armado_hasta = ahora + self._respuesta_esperada
                        self.activacion_oida.emit()
                    self._respuesta_esperada = 0.0
                self.nivel = nivel_de(datos)
                frase_audio += datos

                if not reconocedor.AcceptWaveform(datos):
                    parcial = json.loads(reconocedor.PartialResult()).get("partial", "")
                    # Bloques seguidos con voz (dos o más = retomaste la frase; uno
                    # suelto puede ser un ruido y no debe alargar la espera).
                    bloques_voz = bloques_voz + 1 if self.nivel > _NIVEL_VOZ else 0
                    if dictado and (parcial or bloques_voz >= 2):
                        dictado_fin = 0.0  # sigue hablando: esperar a que termine la frase
                    # Silencio largo sin frase: no acumular audio de más.
                    del frase_audio[: max(0, len(frase_audio) - _MAXIMO_FRASE_BYTES)]
                    # Si ya dijo «Notivoz», reaccionar sin esperar a que termine la frase.
                    if not activacion_avisada and parcial.startswith(PALABRA_ACTIVACION):
                        activacion_avisada = True
                        self.activacion_oida.emit()
                    continue
                activacion_avisada = False
                resultado = json.loads(reconocedor.Result())
                audio_frase = bytes(frase_audio)
                frase_audio.clear()
                hubo_voz = bool(resultado.get("result"))
                texto = self._texto_confiable(resultado)

                if dictado:
                    # Continuación de un pedido libre tras una pausa breve.
                    if hubo_voz:
                        dictado += audio_frase
                        dictado_fin = ahora + self._pausa_tras(resultado)
                        self.activacion_oida.emit()
                    continue

                # Todo comando empieza con «Notivoz»: o en la misma frase
                # («Notivoz, modo relax») o justo antes («Notivoz» … «modo relax»).
                if texto.startswith(PALABRA_ACTIVACION):
                    frase = texto[len(PALABRA_ACTIVACION):].strip()
                    if not frase and not self._sigue_hablando(resultado):
                        armado_hasta = ahora + _SEGUNDOS_TRAS_ACTIVACION
                        audio_activacion = audio_frase
                        winsound.Beep(988, 120)
                        self.activacion_oida.emit()
                        continue
                    if frase and self._emitir_comando(frase, validas):
                        armado_hasta = 0.0
                        continue
                    if self.dictado_activo:
                        # «Notivoz, abre Spotify»: el pedido viene en la misma frase.
                        dictado += audio_frase
                        dictado_inicio = ahora
                        dictado_fin = ahora + self._pausa_tras(resultado)
                        self.activacion_oida.emit()
                    continue
                if ahora >= armado_hasta:
                    continue
                if texto and self._emitir_comando(texto, validas):
                    armado_hasta = 0.0
                    audio_activacion = b""
                elif self.dictado_activo and hubo_voz:
                    dictado += audio_activacion + audio_frase
                    audio_activacion = b""
                    dictado_inicio = ahora
                    dictado_fin = ahora + self._pausa_tras(resultado)
                    self.activacion_oida.emit()
        reproductor().set_conductor_externo(False)
        self.nivel = 0.0
        log.info("Escucha de comandos detenida")
        self.estado_cambiado.emit("Micrófono apagado", False)

    @staticmethod
    def _abrir_audio(sd, dispositivo, salida, audio: queue.Queue):
        """Flujo dúplex (micrófono y parlantes sincronizados) para poder cancelar
        el eco; si el equipo no lo permite, solo micrófono."""

        def al_audio(entrada, salida, muestras, *_):
            referencia = reproductor().siguiente(muestras)
            salida[:, 0] = referencia
            audio.put((entrada[:, 0].tobytes(), referencia.tobytes()))

        try:
            stream = sd.Stream(
                samplerate=_FRECUENCIA,
                blocksize=BLOQUE,
                dtype="int16",
                channels=1,
                device=(dispositivo, salida),
                callback=al_audio,
            )
            return stream, True
        except Exception:
            log.warning("Sin flujo dúplex: no se podrá cancelar el eco.", exc_info=True)
        stream = sd.RawInputStream(
            samplerate=_FRECUENCIA,
            blocksize=BLOQUE,
            dtype="int16",
            channels=1,
            device=dispositivo,
            callback=lambda datos, *_: audio.put((bytes(datos), None)),
        )
        return stream, False

    @staticmethod
    def _pausa_tras(resultado: dict) -> float:
        """Cuánto silencio esperar antes de dar por terminado el pedido."""
        palabras = [p.get("word", "") for p in resultado.get("result", []) if p.get("word") != "[unk]"]
        if palabras and palabras[-1] in _CONECTORES:
            return _PAUSA_PENSANDO
        return _PAUSA_FIN_DICTADO

    @staticmethod
    def _sigue_hablando(resultado: dict) -> bool:
        """«Notivoz» seguido de palabras que el modelo no conoce («Notivoz, abre
        Spotify» → «noti voz [unk]»): hay un pedido en la misma frase."""
        palabras = [p.get("word") for p in resultado.get("result", [])]
        return len(palabras) > 2

    def _emitir_comando(self, frase: str, validas: dict[str, int]) -> bool:
        """Si la frase es un comando («modo relax») o su cierre («cierra modo
        relax»), lo avisa y devuelve True."""
        if frase in validas:
            log.info("Comando de voz reconocido: «%s»", frase)
            self.comando_detectado.emit(validas[frase])
            return True
        for verbo in VERBOS_CIERRE:
            if frase.startswith(f"{verbo} ") and frase[len(verbo) + 1:] in validas:
                log.info("Cierre de comando reconocido: «%s»", frase)
                self.cierre_detectado.emit(validas[frase[len(verbo) + 1:]])
                return True
        return False

    @staticmethod
    def _texto_confiable(resultado: dict) -> str:
        palabras = [p for p in resultado.get("result", []) if p.get("word") != "[unk]"]
        if not palabras:
            return ""
        confianza = sum(p.get("conf", 0) for p in palabras) / len(palabras)
        if confianza < _CONFIANZA_MINIMA:
            return ""
        return " ".join(p["word"] for p in palabras)

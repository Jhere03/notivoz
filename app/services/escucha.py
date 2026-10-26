"""Reconocimiento de voz offline (Vosk) para los comandos: «Notivoz, modo relax».

Escucha el micrófono en un hilo propio con una gramática cerrada: solo puede
"oír" la palabra de activación y las frases de los comandos (y su cierre), lo
que lo hace preciso y evita que cualquier conversación dispare algo. Mientras
Notivoz habla, no escucha (para no activarse con su propia voz).
"""

import json
import logging
import queue
import threading
import time
import winsound

from PySide6.QtCore import QObject, Signal

from app.services import modelo_voz
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
""".split()

_FRECUENCIA = FRECUENCIA
_CONFIANZA_MINIMA = 0.55
_SEGUNDOS_TRAS_ACTIVACION = 5  # tras decir solo «Notivoz», tiempo para decir el comando

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
    import sounddevice as sd

    try:
        api_por_defecto = sd.query_devices(kind="input")["hostapi"]
    except Exception:
        return []
    return [
        d["name"]
        for d in sd.query_devices()
        if d["max_input_channels"] > 0 and d["hostapi"] == api_por_defecto
    ]


# «Notivoz, cierra modo relax»: palabras para cerrar lo que abrió un comando.
VERBOS_CIERRE = ("cierra", "termina", "apaga", "fin del")


class Escucha(QObject):
    comando_detectado = Signal(int)
    cierre_detectado = Signal(int)  # «cierra modo relax»
    # Se oyó «Notivoz» (también a mitad de frase, para reaccionar enseguida).
    activacion_oida = Signal()
    estado_cambiado = Signal(str, bool)  # texto para mostrar, ¿escuchando?

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dispositivo: str | None = None  # None = micrófono por defecto
        # Volumen actual de la voz (0 a 1), para animar la burbuja.
        self.nivel = 0.0
        self._frases: dict[str, int] = {}
        self._cambio_frases = threading.Event()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None

    @property
    def activa(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def set_frases(self, frases: dict[str, int]) -> None:
        """frase normalizada → id del comando. Se aplica sin reiniciar la escucha."""
        self._frases = dict(frases)
        self._cambio_frases.set()

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

        audio: queue.Queue[bytes] = queue.Queue()
        try:
            dispositivo = self.dispositivo if self.dispositivo in dispositivos_entrada() else None
            stream = sd.RawInputStream(
                samplerate=_FRECUENCIA,
                blocksize=BLOQUE,
                dtype="int16",
                channels=1,
                device=dispositivo,
                callback=lambda datos, *_: audio.put(bytes(datos)),
            )
        except Exception:
            log.exception("No se pudo abrir el micrófono")
            self.estado_cambiado.emit("No se encontró el micrófono", False)
            return

        armado_hasta = 0.0
        activacion_avisada = False  # ya se avisó «Notivoz» en esta frase
        silenciado = False
        reconocedor = None
        validas: dict[str, int] = {}
        self._cambio_frases.set()
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
                    datos = audio.get(timeout=0.5)
                except queue.Empty:
                    continue

                # No escuchar mientras Notivoz habla (ni justo después: eco).
                if voz().ocupada():
                    silenciado = True
                    self.nivel = 0.0
                    continue
                if silenciado:
                    silenciado = False
                    reconocedor.Reset()
                self.nivel = nivel_de(datos)

                if not reconocedor.AcceptWaveform(datos):
                    # Resultado parcial: si ya dijo «Notivoz», reaccionar sin
                    # esperar a que termine la frase.
                    parcial = json.loads(reconocedor.PartialResult()).get("partial", "")
                    if not activacion_avisada and parcial.startswith(PALABRA_ACTIVACION):
                        activacion_avisada = True
                        self.activacion_oida.emit()
                    continue
                activacion_avisada = False
                texto = self._texto_confiable(json.loads(reconocedor.Result()))
                if not texto:
                    continue

                # Todo comando empieza con «Notivoz»: o en la misma frase
                # («Notivoz, modo relax») o justo antes («Notivoz» … «modo relax»).
                ahora = time.monotonic()
                if texto.startswith(PALABRA_ACTIVACION):
                    frase = texto[len(PALABRA_ACTIVACION):].strip()
                    if not frase:
                        armado_hasta = ahora + _SEGUNDOS_TRAS_ACTIVACION
                        winsound.Beep(988, 120)
                        self.activacion_oida.emit()
                        continue
                elif ahora < armado_hasta:
                    frase = texto
                else:
                    continue

                if self._emitir_comando(frase, validas):
                    armado_hasta = 0.0
        self.nivel = 0.0
        log.info("Escucha de comandos detenida")
        self.estado_cambiado.emit("Micrófono apagado", False)

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

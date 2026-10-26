"""Voz de la aplicación (texto a voz).

- Principal: voces neuronales de Microsoft (edge-tts), muy naturales. Necesitan
  internet: el texto se envía al servicio de voz de Microsoft Edge.
- Respaldo: voces SAPI de Windows, sin internet (más robóticas).

Los audios generados se guardan en caché, así las frases repetidas suenan al
instante y también sin conexión. Todo corre en un hilo propio para no congelar
la interfaz; los textos se encolan y se leen uno detrás de otro.
"""

import asyncio
import hashlib
import logging
import queue
import threading
import time
import warnings
import wave
from pathlib import Path

import numpy as np

from app.config import data_dir
from app.services import mp3
from app.services.audio import remuestrear, reproductor

log = logging.getLogger(__name__)

# Nombre interno → nombre para mostrar.
VOCES_NEURALES = {
    "es-PE-CamilaNeural": "Camila · Perú",
    "es-PE-AlexNeural": "Alex · Perú",
    "es-MX-DaliaNeural": "Dalia · México",
    "es-MX-JorgeNeural": "Jorge · México",
    "es-CO-SalomeNeural": "Salomé · Colombia",
    "es-CO-GonzaloNeural": "Gonzalo · Colombia",
    "es-AR-ElenaNeural": "Elena · Argentina",
    "es-AR-TomasNeural": "Tomás · Argentina",
    "es-ES-ElviraNeural": "Elvira · España",
    "es-ES-AlvaroNeural": "Álvaro · España",
    "es-US-PalomaNeural": "Paloma · EE. UU.",
    "es-US-AlonsoNeural": "Alonso · EE. UU.",
}
VOZ_POR_DEFECTO = "es-PE-CamilaNeural"
VOZ_WINDOWS = ""  # Solo la voz de Windows, sin internet.

_TIEMPO_MAXIMO_RED = 10  # segundos para generar un audio
_PAUSA_TRAS_FALLO = 60  # sin internet: no reintentar la voz neural durante este tiempo
_MAX_CACHE = 300  # audios guardados como máximo
_IDIOMA_ESPANOL = 0x0A  # LCID principal del español en Windows
_SAPI_16KHZ_16BIT_MONO = 18
_SAPI_CREAR_ARCHIVO = 3


class Voz:
    def __init__(self) -> None:
        # Se aplican antes de cada frase, así un cambio vale desde la siguiente.
        self.velocidad = 0  # -10 a 10
        self.volumen = 100  # 0 a 100
        self.voz_neural = VOZ_POR_DEFECTO  # VOZ_WINDOWS para no usar internet
        self._neural_pausada_hasta = 0.0
        self._hablando = False
        self._silencio_hasta = 0.0
        # Frase que suena ahora (para no confundir la propia voz con una interrupción).
        self.texto_actual = ""
        self._interrumpida = False
        self._sapi = None
        self._cola: queue.Queue[str | None] = queue.Queue()
        self._hilo = threading.Thread(target=self._trabajar, name="Voz", daemon=True)
        self._hilo.start()

    def hablar(self, texto: str) -> None:
        texto = " ".join(texto.split())
        if texto:
            self._cola.put(texto)

    def cerrar(self) -> None:
        self._cola.put(None)

    def detener(self) -> None:
        """Calla ya: descarta lo que estaba en cola y corta la frase en curso
        (la voz de Windows de respaldo termina la frase que estaba diciendo)."""
        while True:
            try:
                if self._cola.get_nowait() is None:
                    self._cola.put(None)  # respetar el cierre pedido
                    break
            except queue.Empty:
                break
        if self._hablando:
            self._interrumpida = True
            reproductor().detener()

    @property
    def hablando(self) -> bool:
        """True solo mientras suena una frase."""
        return self._hablando

    def ocupada(self) -> bool:
        """True mientras habla, tiene frases en cola o acaba de hablar (eco).
        La escucha de comandos lo usa para no oír a Notivoz."""
        return self._hablando or not self._cola.empty() or time.monotonic() < self._silencio_hasta

    # --- Hilo de voz ---------------------------------------------------------

    def _trabajar(self) -> None:
        with warnings.catch_warnings():
            # comtypes avisa que aún no está probado en Python 3.15; funciona igual.
            warnings.simplefilter("ignore", FutureWarning)
            import comtypes
            import comtypes.client
        comtypes.CoInitialize()
        try:
            while (texto := self._cola.get()) is not None:
                self._hablando = True
                self.texto_actual = texto
                try:
                    if not (self._usar_neural() and self._hablar_neural(texto)):
                        self._hablar_windows(texto)
                finally:
                    self._hablando = False
                    self.texto_actual = ""
                    # Tras cortarla porque le hablaste, escuchar ya (sin esperar el eco).
                    self._silencio_hasta = 0.0 if self._interrumpida else time.monotonic() + 0.7
                    self._interrumpida = False
        finally:
            comtypes.CoUninitialize()

    def _usar_neural(self) -> bool:
        return bool(self.voz_neural) and time.monotonic() >= self._neural_pausada_hasta

    def _hablar_neural(self, texto: str) -> bool:
        """Devuelve False si no se pudo (sin internet, etc.) para usar el respaldo."""
        voz = self.voz_neural
        velocidad = f"{int(self.velocidad) * 10:+d}%"
        volumen = f"{int(self.volumen) - 100:+d}%"
        archivo = _carpeta_cache() / (
            hashlib.sha1(f"{voz}|{velocidad}|{volumen}|{texto}".encode()).hexdigest() + ".mp3"
        )
        try:
            if not archivo.exists():
                _generar_audio(texto, voz, velocidad, volumen, archivo)
                _limpiar_cache()
            pcm, frecuencia, canales = mp3.decodificar(archivo.read_bytes())
            muestras = np.frombuffer(pcm, dtype=np.int16)
            if canales == 2:
                muestras = muestras.reshape(-1, 2).mean(axis=1).astype(np.int16)
            reproductor().reproducir(remuestrear(muestras, frecuencia))
            archivo.touch()  # para la limpieza: lo usado recientemente se conserva
            return True
        except Exception as error:
            log.warning("Voz neural no disponible (%s); se usa la voz de Windows.", error)
            self._neural_pausada_hasta = time.monotonic() + _PAUSA_TRAS_FALLO
            return False

    def _hablar_windows(self, texto: str) -> None:
        try:
            if self._sapi is None:
                import comtypes.client

                self._sapi = comtypes.client.CreateObject("SAPI.SpVoice")
                _elegir_voz_espanol(self._sapi)
            self._sapi.Rate = max(-10, min(10, int(self.velocidad)))
            self._sapi.Volume = max(0, min(100, int(self.volumen)))
            reproductor().reproducir(self._sapi_a_pcm(texto))
        except Exception:
            log.exception("Error al leer en voz alta: %r", texto)


    def _sapi_a_pcm(self, texto: str) -> np.ndarray:
        """La voz de Windows se graba a un WAV de 16 kHz y lo reproduce Notivoz
        (así también se puede interrumpir y cancelar su eco)."""
        import comtypes.client

        ruta = _carpeta_cache() / "sapi.wav"
        flujo = comtypes.client.CreateObject("SAPI.SpFileStream")
        formato = comtypes.client.CreateObject("SAPI.SpAudioFormat")
        formato.Type = _SAPI_16KHZ_16BIT_MONO
        flujo.Format = formato
        flujo.Open(str(ruta), _SAPI_CREAR_ARCHIVO)
        try:
            self._sapi.AudioOutputStream = flujo
            self._sapi.Speak(texto)
        finally:
            flujo.Close()
        with wave.open(str(ruta)) as archivo:
            return np.frombuffer(archivo.readframes(archivo.getnframes()), dtype=np.int16)


# --- Utilidades ---------------------------------------------------------------


def _carpeta_cache() -> Path:
    carpeta = data_dir() / "voz_cache"
    carpeta.mkdir(exist_ok=True)
    return carpeta


def _generar_audio(texto: str, voz: str, velocidad: str, volumen: str, destino: Path) -> None:
    import edge_tts

    temporal = destino.with_suffix(".tmp")

    async def generar() -> None:
        comunicacion = edge_tts.Communicate(texto, voz, rate=velocidad, volume=volumen)
        await asyncio.wait_for(comunicacion.save(str(temporal)), _TIEMPO_MAXIMO_RED)

    try:
        asyncio.run(generar())
        if not temporal.exists() or temporal.stat().st_size == 0:
            raise RuntimeError("el servicio de voz no devolvió audio")
        temporal.replace(destino)
    finally:
        temporal.unlink(missing_ok=True)


def _limpiar_cache() -> None:
    audios = sorted(_carpeta_cache().glob("*.mp3"), key=lambda a: a.stat().st_mtime)
    for audio in audios[:-_MAX_CACHE]:
        audio.unlink(missing_ok=True)


def _elegir_voz_espanol(sapi) -> None:
    voces = sapi.GetVoices()
    for i in range(voces.Count):
        token = voces.Item(i)
        idiomas = token.GetAttribute("Language") or ""
        for codigo in idiomas.split(";"):
            try:
                if int(codigo, 16) & 0x3FF == _IDIOMA_ESPANOL:
                    sapi.Voice = token
                    return
            except ValueError:
                continue
    log.warning("No hay una voz de Windows en español instalada; se usará la voz por defecto.")


_voz: Voz | None = None


def voz() -> Voz:
    """Instancia única de la voz para toda la app."""
    global _voz
    if _voz is None:
        _voz = Voz()
    return _voz

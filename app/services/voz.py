"""Voz de la aplicación (texto a voz).

- Principal: voces neuronales de Microsoft (edge-tts), muy naturales. Necesitan
  internet: el texto se envía al servicio de voz de Microsoft Edge.
- Respaldo: voces SAPI de Windows, sin internet (más robóticas).

Los audios generados se guardan en caché, así las frases repetidas suenan al
instante y también sin conexión. Todo corre en un hilo propio para no congelar
la interfaz; los textos se encolan y se leen uno detrás de otro.
"""

import asyncio
import ctypes
import hashlib
import logging
import queue
import threading
import time
import warnings
from pathlib import Path

from app.config import data_dir

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


class Voz:
    def __init__(self) -> None:
        # Se aplican antes de cada frase, así un cambio vale desde la siguiente.
        self.velocidad = 0  # -10 a 10
        self.volumen = 100  # 0 a 100
        self.voz_neural = VOZ_POR_DEFECTO  # VOZ_WINDOWS para no usar internet
        self._neural_pausada_hasta = 0.0
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
                if self._usar_neural() and self._hablar_neural(texto):
                    continue
                self._hablar_windows(texto)
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
            _reproducir(archivo)
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
            self._sapi.Speak(texto)
        except Exception:
            log.exception("Error al leer en voz alta: %r", texto)


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


def _reproducir(archivo: Path) -> None:
    """Reproduce un MP3 con el reproductor interno de Windows (MCI) y espera a que termine."""
    mci = ctypes.windll.winmm.mciSendStringW
    alias = "notivoz_voz"

    def enviar(comando: str) -> None:
        error = mci(comando, None, 0, 0)
        if error:
            raise OSError(f"MCI error {error} en «{comando.split()[0]}»")

    enviar(f'open "{archivo}" type mpegvideo alias {alias}')
    try:
        enviar(f"play {alias} wait")
    finally:
        mci(f"close {alias}", None, 0, 0)
    archivo.touch()  # para la limpieza: lo usado recientemente se conserva


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

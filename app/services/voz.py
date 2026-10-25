"""Voz de la aplicación (texto a voz) usando las voces SAPI de Windows.

Habla en un hilo propio para no congelar la interfaz. Los textos se encolan y se
leen uno detrás de otro.
"""

import logging
import queue
import threading
import warnings

log = logging.getLogger(__name__)

# Identificador de idioma (LCID) principal del español en Windows.
_IDIOMA_ESPANOL = 0x0A


class Voz:
    def __init__(self) -> None:
        self._cola: queue.Queue[str | None] = queue.Queue()
        self._hilo = threading.Thread(target=self._trabajar, name="Voz", daemon=True)
        self._hilo.start()

    def hablar(self, texto: str) -> None:
        texto = " ".join(texto.split())
        if texto:
            self._cola.put(texto)

    def cerrar(self) -> None:
        self._cola.put(None)

    def _trabajar(self) -> None:
        try:
            with warnings.catch_warnings():
                # comtypes avisa que aún no está probado en Python 3.15; funciona igual.
                warnings.simplefilter("ignore", FutureWarning)
                import comtypes
                import comtypes.client

            comtypes.CoInitialize()
            voz = comtypes.client.CreateObject("SAPI.SpVoice")
            _elegir_voz_espanol(voz)
        except Exception:
            log.exception("No se pudo iniciar la voz de Windows; la app seguirá sin voz.")
            return

        try:
            while (texto := self._cola.get()) is not None:
                try:
                    voz.Speak(texto)
                except Exception:
                    log.exception("Error al leer en voz alta: %r", texto)
        finally:
            comtypes.CoUninitialize()


def _elegir_voz_espanol(voz) -> None:
    voces = voz.GetVoices()
    for i in range(voces.Count):
        token = voces.Item(i)
        idiomas = token.GetAttribute("Language") or ""
        for codigo in idiomas.split(";"):
            try:
                if int(codigo, 16) & 0x3FF == _IDIOMA_ESPANOL:
                    voz.Voice = token
                    return
            except ValueError:
                continue
    log.warning("No hay una voz en español instalada; se usará la voz por defecto.")


_voz: Voz | None = None


def voz() -> Voz:
    """Instancia única de la voz para toda la app."""
    global _voz
    if _voz is None:
        _voz = Voz()
    return _voz

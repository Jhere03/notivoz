"""Utilidades de micrófono: nivel de voz y prueba con eco retrasado."""

import collections
import logging
import math
from array import array

log = logging.getLogger(__name__)

FRECUENCIA = 16000
BLOQUE = 1600  # 0,1 s de audio por bloque
_RMS_MAXIMO = 4000  # volumen de voz normal → nivel ~1


def nivel_de(datos: bytes) -> float:
    """Volumen de un bloque de audio PCM de 16 bits, entre 0 y 1."""
    muestras = array("h", datos)
    if not muestras:
        return 0.0
    rms = math.sqrt(sum(m * m for m in muestras) / len(muestras))
    return min(1.0, rms / _RMS_MAXIMO)


class PruebaMicrofono:
    """Repite por los parlantes lo que capta el micrófono, con un retraso
    para no oírse encima de uno mismo."""

    RETARDO_SEGUNDOS = 1.0

    def __init__(self) -> None:
        self.nivel = 0.0
        self._stream = None

    @property
    def activa(self) -> bool:
        return self._stream is not None

    def iniciar(self, dispositivo: str | None = None) -> None:
        """Lanza OSError/Exception si no se puede abrir el micrófono o los parlantes."""
        import sounddevice as sd

        if self.activa:
            return
        bloques_retraso = int(self.RETARDO_SEGUNDOS * FRECUENCIA / BLOQUE)
        retraso: collections.deque[bytes] = collections.deque()
        silencio = bytes(BLOQUE * 2)

        def procesar(entrada, salida, *_):
            datos = bytes(entrada)
            self.nivel = nivel_de(datos)
            retraso.append(datos)
            salida[:] = retraso.popleft() if len(retraso) > bloques_retraso else silencio

        self._stream = sd.RawStream(
            samplerate=FRECUENCIA,
            blocksize=BLOQUE,
            dtype="int16",
            channels=1,
            device=(dispositivo, None),
            callback=procesar,
        )
        self._stream.start()
        log.info("Prueba de micrófono iniciada")

    def detener(self) -> None:
        if self._stream is None:
            return
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self.nivel = 0.0
            log.info("Prueba de micrófono terminada")

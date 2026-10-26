"""Voz a texto con Whisper, en tu propio equipo (sin internet y sin enviar tu voz).

Usa el modelo «small» de Whisper convertido para CTranslate2. La descarga está
fijada a una versión exacta del repositorio y cada archivo se comprueba con su
huella SHA-256 antes de usarlo: si alguien alterara el archivo en el camino o
en el servidor, Notivoz lo rechaza.
"""

import hashlib
import logging
import os
import shutil
import threading
import urllib.request
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.services.modelo_voz import carpeta_modelos

log = logging.getLogger(__name__)

_REPOSITORIO = "Systran/faster-whisper-small"
_REVISION = "536b0662742c02347bc0e980a01041f333bce120"
# archivo → (tamaño en bytes, SHA-256)
_ARCHIVOS = {
    "config.json": (2370, "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828"),
    "tokenizer.json": (2203239, "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab"),
    "vocabulary.txt": (459861, "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913"),
    "model.bin": (483546902, "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"),
}
TAMANO_APROX_MB = 460

_FRECUENCIA = 16000
_N_FFT = 400
_SALTO = 160
_N_MEL = 80
_MUESTRAS_30S = 30 * _FRECUENCIA
# Whisper procesa ventanas de 30 s (3000 cuadros) aunque hables 3 s. Recortarla a
# la duración real lo hace ~3 veces más rápido; con menos de 10 s pierde
# precisión, así que la ventana nunca baja de 1000 cuadros.
_CUADROS_MINIMOS = 1000
_CUADROS_EXTRA = 150
# Palabras que ayudan a Whisper a escribir bien los nombres propios de la app.
_CONTEXTO = " Notivoz, tarea, nota, recordatorio, cliente, modo relax, Spotify, Steam."
# Frases que Whisper a veces "inventa" sobre silencio o ruido.
_ALUCINACIONES = ("subtítulos", "subtitulos", "gracias por ver", "suscríbete", "amara.org")


def carpeta_modelo() -> Path:
    return carpeta_modelos() / f"whisper-small-{_REVISION[:8]}"


def instalado() -> bool:
    carpeta = carpeta_modelo()
    return all(
        (carpeta / nombre).is_file() and (carpeta / nombre).stat().st_size == tamano
        for nombre, (tamano, _) in _ARCHIVOS.items()
    )


def descargar(progreso: Callable[[int, int], None] | None = None) -> None:
    """Descarga y verifica el modelo. `progreso(bytes_leidos, bytes_totales)`."""
    destino = carpeta_modelo()
    temporal = destino.with_name(destino.name + ".part")
    shutil.rmtree(temporal, ignore_errors=True)
    temporal.mkdir(parents=True)
    total = sum(t for t, _ in _ARCHIVOS.values())
    leidos = 0
    try:
        for nombre, (tamano, sha256) in _ARCHIVOS.items():
            url = f"https://huggingface.co/{_REPOSITORIO}/resolve/{_REVISION}/{nombre}"
            huella = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=30) as respuesta, open(temporal / nombre, "wb") as archivo:
                while bloque := respuesta.read(512 * 1024):
                    archivo.write(bloque)
                    huella.update(bloque)
                    leidos += len(bloque)
                    if progreso is not None:
                        progreso(leidos, total)
            if (temporal / nombre).stat().st_size != tamano or huella.hexdigest() != sha256:
                raise RuntimeError(f"El archivo {nombre} no coincide con el original; se descartó.")
        shutil.rmtree(destino, ignore_errors=True)
        temporal.rename(destino)
        log.info("Modelo Whisper instalado y verificado.")
    finally:
        shutil.rmtree(temporal, ignore_errors=True)


# --- Espectrograma (igual que el de Whisper) ------------------------------------------


def _filtros_mel() -> np.ndarray:
    """Banco de filtros mel de Slaney (el mismo que usa Whisper), 80 × 201."""

    def a_mel(hz):
        hz = np.asarray(hz, dtype=np.float64)
        mel = hz / (200.0 / 3)
        corte = 1000.0 / (200.0 / 3)
        paso = np.log(6.4) / 27.0
        return np.where(hz >= 1000.0, corte + np.log(np.maximum(hz, 1e-10) / 1000.0) / paso, mel)

    def a_hz(mel):
        mel = np.asarray(mel, dtype=np.float64)
        hz = mel * (200.0 / 3)
        corte = 1000.0 / (200.0 / 3)
        paso = np.log(6.4) / 27.0
        return np.where(mel >= corte, 1000.0 * np.exp(paso * (mel - corte)), hz)

    frecuencias = np.linspace(0, _FRECUENCIA / 2, 1 + _N_FFT // 2)
    puntos = a_hz(np.linspace(a_mel(0.0), a_mel(_FRECUENCIA / 2), _N_MEL + 2))
    pesos = np.zeros((_N_MEL, len(frecuencias)))
    for i in range(_N_MEL):
        subida = (frecuencias - puntos[i]) / (puntos[i + 1] - puntos[i])
        bajada = (puntos[i + 2] - frecuencias) / (puntos[i + 2] - puntos[i + 1])
        pesos[i] = np.maximum(0, np.minimum(subida, bajada)) * (2.0 / (puntos[i + 2] - puntos[i]))
    return pesos.astype(np.float32)


def espectrograma(audio: np.ndarray) -> np.ndarray:
    """Log-mel de 80 × 3000 a partir de audio float32 a 16 kHz (máx. 30 s)."""
    audio = audio[:_MUESTRAS_30S]
    audio = np.pad(audio, (0, _MUESTRAS_30S - len(audio)))
    relleno = np.pad(audio, (_N_FFT // 2, _N_FFT // 2), mode="reflect")
    ventana = np.hanning(_N_FFT + 1)[:-1].astype(np.float32)  # Hann periódica
    cuadros = np.lib.stride_tricks.sliding_window_view(relleno, _N_FFT)[::_SALTO]
    espectro = np.abs(np.fft.rfft(cuadros * ventana, axis=1)) ** 2
    espectro = espectro[:-1].T  # 201 × 3000
    mel = _filtros_mel() @ espectro
    log_mel = np.log10(np.maximum(mel, 1e-10))
    log_mel = np.maximum(log_mel, log_mel.max() - 8.0)
    return ((log_mel + 4.0) / 4.0).astype(np.float32)


# --- Transcripción --------------------------------------------------------------------


class Transcriptor:
    """Carga el modelo una vez (unos segundos) y transcribe audio PCM de 16 bits."""

    def __init__(self) -> None:
        self._modelo = None
        self._tokenizador = None
        self._candado = threading.Lock()

    def _cargar(self) -> None:
        import ctranslate2
        from tokenizers import Tokenizer

        if not instalado():
            raise RuntimeError("Falta descargar el modelo de Whisper.")
        carpeta = str(carpeta_modelo())
        self._modelo = ctranslate2.models.Whisper(
            carpeta, device="cpu", compute_type="int8", intra_threads=os.cpu_count() or 4
        )
        self._tokenizador = Tokenizer.from_file(str(carpeta_modelo() / "tokenizer.json"))
        log.info("Whisper cargado.")

    def precargar(self) -> None:
        with self._candado:
            if self._modelo is None:
                self._cargar()

    def transcribir(self, pcm16: bytes) -> str:
        import ctranslate2

        audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio) < _FRECUENCIA // 3:
            return ""
        with self._candado:
            if self._modelo is None:
                self._cargar()
            tok = self._tokenizador
            especiales = [
                tok.token_to_id(t)
                for t in ("<|startoftranscript|>", "<|es|>", "<|transcribe|>", "<|notimestamps|>")
            ]
            previo = [tok.token_to_id("<|startofprev|>")] + tok.encode(_CONTEXTO, add_special_tokens=False).ids
            cuadros = min(3000, max(_CUADROS_MINIMOS, len(audio) // _SALTO + _CUADROS_EXTRA))
            cuadros += cuadros % 2
            mel = np.ascontiguousarray(espectrograma(audio)[:, :cuadros])
            caracteristicas = ctranslate2.StorageView.from_array(mel[np.newaxis])
            resultado = self._modelo.generate(
                caracteristicas,
                [previo + especiales],
                beam_size=2,
                max_length=224,
                return_no_speech_prob=True,
                suppress_blank=True,
            )[0]
        if resultado.no_speech_prob > 0.6:
            return ""
        texto = tok.decode(resultado.sequences_ids[0], skip_special_tokens=True).strip()
        if any(a in texto.lower() for a in _ALUCINACIONES):
            return ""
        return texto


_transcriptor: Transcriptor | None = None


def transcriptor() -> Transcriptor:
    global _transcriptor
    if _transcriptor is None:
        _transcriptor = Transcriptor()
    return _transcriptor

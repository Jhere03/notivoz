"""Decodifica MP3 a PCM con el decodificador que trae Windows (ACM), sin
dependencias externas. Se usa para las voces neuronales (edge-tts entrega MP3)."""

import ctypes
from ctypes import wintypes

_WAVE_FORMAT_PCM = 1
_WAVE_FORMAT_MPEGLAYER3 = 0x55
_MPEGLAYER3_ID_MPEG = 1
_MPEGLAYER3_FLAG_PADDING_OFF = 2
_ACM_STREAMOPENF_NONREALTIME = 0x04
_ACM_STREAMSIZEF_SOURCE = 0x00
_ACM_STREAMCONVERTF_START = 0x10
_ACM_STREAMCONVERTF_END = 0x20
_RESERVADO = 15 if ctypes.sizeof(ctypes.c_void_p) == 8 else 10


class _WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wFormatTag", wintypes.WORD),
        ("nChannels", wintypes.WORD),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", wintypes.WORD),
        ("wBitsPerSample", wintypes.WORD),
        ("cbSize", wintypes.WORD),
    ]


class _MPEGLAYER3WAVEFORMAT(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("wfx", _WAVEFORMATEX),
        ("wID", wintypes.WORD),
        ("fdwFlags", wintypes.DWORD),
        ("nBlockSize", wintypes.WORD),
        ("nFramesPerBlock", wintypes.WORD),
        ("nCodecDelay", wintypes.WORD),
    ]


class _ACMSTREAMHEADER(ctypes.Structure):
    _fields_ = [
        ("cbStruct", wintypes.DWORD),
        ("fdwStatus", wintypes.DWORD),
        ("dwUser", ctypes.c_size_t),
        ("pbSrc", ctypes.c_void_p),
        ("cbSrcLength", wintypes.DWORD),
        ("cbSrcLengthUsed", wintypes.DWORD),
        ("dwSrcUser", ctypes.c_size_t),
        ("pbDst", ctypes.c_void_p),
        ("cbDstLength", wintypes.DWORD),
        ("cbDstLengthUsed", wintypes.DWORD),
        ("dwDstUser", ctypes.c_size_t),
        ("dwReservedDriver", wintypes.DWORD * _RESERVADO),
    ]


def _cabecera_mp3(datos: bytes) -> tuple[int, int, int]:
    """(frecuencia, kbps, canales) del primer cuadro MP3 del archivo."""
    tablas_kbps = {
        3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],  # MPEG-1
        2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],  # MPEG-2
    }
    frecuencias = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}
    inicio = 0
    if datos[:3] == b"ID3":  # saltar la etiqueta ID3v2
        tamano = (datos[6] << 21) | (datos[7] << 14) | (datos[8] << 7) | datos[9]
        inicio = 10 + tamano
    for i in range(inicio, len(datos) - 4):
        if datos[i] == 0xFF and datos[i + 1] & 0xE0 == 0xE0:
            version = (datos[i + 1] >> 3) & 0x3
            capa = (datos[i + 1] >> 1) & 0x3
            indice_kbps = datos[i + 2] >> 4
            indice_frec = (datos[i + 2] >> 2) & 0x3
            if capa != 1 or version == 1 or indice_kbps in (0, 15) or indice_frec == 3:
                continue
            kbps = tablas_kbps[3 if version == 3 else 2][indice_kbps]
            canales = 1 if (datos[i + 3] >> 6) == 3 else 2
            return frecuencias[version][indice_frec], kbps, canales
    raise ValueError("No es un MP3 válido.")


def decodificar(datos: bytes) -> tuple[bytes, int, int]:
    """MP3 → (PCM de 16 bits, frecuencia, canales)."""
    acm = ctypes.windll.msacm32
    frecuencia, kbps, canales = _cabecera_mp3(datos)
    origen = _MPEGLAYER3WAVEFORMAT()
    origen.wfx.wFormatTag = _WAVE_FORMAT_MPEGLAYER3
    origen.wfx.nChannels = canales
    origen.wfx.nSamplesPerSec = frecuencia
    origen.wfx.nAvgBytesPerSec = kbps * 1000 // 8
    origen.wfx.nBlockAlign = 1
    origen.wfx.cbSize = 12
    origen.wID = _MPEGLAYER3_ID_MPEG
    origen.fdwFlags = _MPEGLAYER3_FLAG_PADDING_OFF
    origen.nBlockSize = (144 if frecuencia >= 32000 else 72) * kbps * 1000 // frecuencia
    origen.nFramesPerBlock = 1
    origen.nCodecDelay = 1393

    destino = _WAVEFORMATEX()
    destino.wFormatTag = _WAVE_FORMAT_PCM
    destino.nChannels = canales
    destino.nSamplesPerSec = frecuencia
    destino.wBitsPerSample = 16
    destino.nBlockAlign = 2 * canales
    destino.nAvgBytesPerSec = frecuencia * destino.nBlockAlign

    flujo = ctypes.c_void_p()
    error = acm.acmStreamOpen(
        ctypes.byref(flujo), None, ctypes.byref(origen), ctypes.byref(destino), None, 0, 0,
        _ACM_STREAMOPENF_NONREALTIME,
    )  # fmt: skip
    if error:
        raise OSError(f"Windows no pudo abrir el decodificador MP3 (error {error}).")
    try:
        salida = wintypes.DWORD()
        acm.acmStreamSize(flujo, len(datos), ctypes.byref(salida), _ACM_STREAMSIZEF_SOURCE)
        origen_buf = ctypes.create_string_buffer(datos, len(datos))
        destino_buf = ctypes.create_string_buffer(max(salida.value, 1) + 65536)
        cabecera = _ACMSTREAMHEADER()
        cabecera.cbStruct = ctypes.sizeof(cabecera)
        cabecera.pbSrc = ctypes.cast(origen_buf, ctypes.c_void_p)
        cabecera.cbSrcLength = len(datos)
        cabecera.pbDst = ctypes.cast(destino_buf, ctypes.c_void_p)
        cabecera.cbDstLength = len(destino_buf)
        if acm.acmStreamPrepareHeader(flujo, ctypes.byref(cabecera), 0):
            raise OSError("No se pudo preparar la decodificación MP3.")
        try:
            if acm.acmStreamConvert(
                flujo, ctypes.byref(cabecera), _ACM_STREAMCONVERTF_START | _ACM_STREAMCONVERTF_END
            ):
                raise OSError("Falló la decodificación MP3.")
            pcm = destino_buf.raw[: cabecera.cbDstLengthUsed]
        finally:
            acm.acmStreamUnprepareHeader(flujo, ctypes.byref(cabecera), 0)
    finally:
        acm.acmStreamClose(flujo, 0)
    return pcm, frecuencia, canales

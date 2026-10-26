"""Reproducción de la voz de Notivoz y cancelación de eco.

Para poder interrumpir a Notivoz hablándole encima, hay que distinguir tu voz
de la suya, que el micrófono también capta por los parlantes. Por eso Notivoz
reproduce su voz él mismo: cuando la escucha está activa, el audio sale por el
mismo flujo dúplex con el que se lee el micrófono, así se sabe con exactitud
qué sonó y cuándo, y el cancelador de eco lo resta de lo que capta el micrófono.
"""

import threading

import numpy as np

FRECUENCIA = 16000


# --- Dispositivos -------------------------------------------------------------------
#
# Los nombres se buscan solo en la API de audio principal (MME): el mismo
# dispositivo aparece repetido en otras APIs y el nombre solo sería ambiguo.
# Sin elección, se usa el «Asignador de sonido Microsoft», que envía el audio a
# la salida (o toma la entrada) predeterminada de Windows, aunque se cambie con
# Notivoz abierto.


def _dispositivos_api(entrada: bool) -> list[tuple[int, str]]:
    """(índice, nombre) de la API principal; el primero es el asignador de Windows."""
    import sounddevice as sd

    try:
        api = sd.query_devices(kind="input" if entrada else "output")["hostapi"]
        indices = sd.query_hostapis(api)["devices"]
    except Exception:
        return []
    canales = "max_input_channels" if entrada else "max_output_channels"
    return [(i, sd.query_devices(i)["name"]) for i in indices if sd.query_devices(i)[canales] > 0]


def _es_asignador(nombre: str) -> bool:
    return "microsoft" in nombre.lower() and ("asignador" in nombre.lower() or "mapper" in nombre.lower())


def nombres_dispositivos(entrada: bool) -> list[str]:
    """Micrófonos o salidas para elegir (sin el asignador de Windows)."""
    return [n for _, n in _dispositivos_api(entrada) if not _es_asignador(n)]


def nombre_legible(nombre: str) -> str:
    """La API principal recorta los nombres a 31 letras («Realtek HD Audio 2nd
    output (Re»); otra API suele tener el nombre completo."""
    import sounddevice as sd

    try:
        completos = [d["name"] for d in sd.query_devices() if d["name"].startswith(nombre)]
    except Exception:
        return nombre
    return max(completos, key=len, default=nombre)


def indice_dispositivo(nombre: str | None, entrada: bool) -> int | None:
    """Índice para sounddevice: el elegido por nombre o, si no hay (o ya no
    está conectado), el predeterminado de Windows."""
    dispositivos = _dispositivos_api(entrada)
    for indice, actual in dispositivos:
        if nombre and actual == nombre:
            return indice
    for indice, actual in dispositivos:
        if _es_asignador(actual):
            return indice
    return None


def remuestrear(pcm: np.ndarray, desde: int, hasta: int = FRECUENCIA) -> np.ndarray:
    """Cambia la frecuencia de muestreo (por FFT, sin distorsionar)."""
    if desde == hasta or len(pcm) == 0:
        return pcm.astype(np.int16)
    largo = int(round(len(pcm) * hasta / desde))
    espectro = np.fft.rfft(pcm.astype(np.float64))
    salida = np.fft.irfft(espectro[: largo // 2 + 1], largo) * (largo / len(pcm))
    return np.clip(salida, -32768, 32767).astype(np.int16)


class Reproductor:
    """Reproduce PCM de 16 bits a 16 kHz, interrumpible.

    Si la escucha tiene abierto su flujo dúplex, ella "conduce" la reproducción
    (pide cada bloque con `siguiente`); si no, se abre un flujo de salida propio.
    """

    def __init__(self) -> None:
        self._candado = threading.Lock()
        self._pcm: np.ndarray | None = None
        self._posicion = 0
        self._terminado = threading.Event()
        self._terminado.set()
        self._conductor_externo = False
        # Nombre de la salida elegida en Configuración ("" = la de Windows).
        self.salida = ""

    @property
    def sonando(self) -> bool:
        return not self._terminado.is_set()

    def set_conductor_externo(self, activo: bool) -> None:
        self._conductor_externo = activo

    def siguiente(self, muestras: int) -> np.ndarray:
        """Próximo bloque a reproducir (silencio si no hay nada)."""
        bloque = np.zeros(muestras, dtype=np.int16)
        with self._candado:
            if self._pcm is None:
                return bloque
            trozo = self._pcm[self._posicion : self._posicion + muestras]
            bloque[: len(trozo)] = trozo
            self._posicion += muestras
            if self._posicion >= len(self._pcm):
                self._pcm = None
                self._terminado.set()
        return bloque

    def detener(self) -> None:
        with self._candado:
            self._pcm = None
            self._terminado.set()

    def reproducir(self, pcm: np.ndarray) -> None:
        """Reproduce y espera a que termine (o a que se llame a `detener`)."""
        import sounddevice as sd

        with self._candado:
            self._pcm = pcm.astype(np.int16)
            self._posicion = 0
            self._terminado.clear()
        flujo = None
        try:
            while not self._terminado.wait(0.05):
                if not self._conductor_externo and flujo is None:
                    flujo = sd.OutputStream(
                        samplerate=FRECUENCIA,
                        device=indice_dispositivo(self.salida, entrada=False),
                        channels=1,
                        dtype="int16",
                        blocksize=800,
                        callback=self._al_pedir_salida,
                    )
                    flujo.start()
            if flujo is not None:
                # Dejar que suene lo que ya estaba en el búfer del dispositivo.
                sd.sleep(int(flujo.latency * 1000) + 60)
        finally:
            if flujo is not None:
                flujo.close()

    def _al_pedir_salida(self, salida, muestras, *_):
        if self._conductor_externo:
            salida[:, 0] = 0
        else:
            salida[:, 0] = self.siguiente(muestras)


_reproductor: Reproductor | None = None


def reproductor() -> Reproductor:
    global _reproductor
    if _reproductor is None:
        _reproductor = Reproductor()
    return _reproductor


# Si el micrófono capta la voz de Notivoz 30 dB más baja (o menos), no hay eco.
_ECO_DESPRECIABLE = 0.03


class CanceladorEco:
    """Cancelador de eco adaptativo (NLMS por bloques en frecuencia, particionado).

    Recibe en paralelo lo que sonó (referencia) y lo que captó el micrófono, y
    devuelve el micrófono sin el eco de Notivoz. El retardo grueso entre ambos
    (latencias del dispositivo) se estima por correlación; el filtro cubre el
    resto (la sala) con 128 ms.
    """

    _P = 160  # muestras por bloque del filtro (el micrófono entrega bloques de 1600)
    _K = 13  # particiones → 2080 coeficientes (130 ms)
    _RETARDO_MAXIMO = 8000  # 0,5 s
    _PASO = 0.2
    _REGULARIZACION = 1e3

    def __init__(self) -> None:
        self.retardo: int | None = None
        # El micrófono casi no capta la voz de Notivoz (audífonos).
        self.sin_eco = False
        self._historial_ref = np.zeros(self._RETARDO_MAXIMO + 4 * FRECUENCIA, dtype=np.float32)
        self._muestras_ref = 0
        self._estimacion_mic: list[np.ndarray] = []
        self._estimacion_ref: list[np.ndarray] = []
        self._reiniciar_filtro()

    def _reiniciar_filtro(self) -> None:
        p, k = self._P, self._K
        self._W = np.zeros((k, p + 1), dtype=np.complex128)
        self._X = np.zeros((k, p + 1), dtype=np.complex128)
        self._potencia = np.full(p + 1, self._REGULARIZACION, dtype=np.float64)
        self._ref_anterior = np.zeros(p, dtype=np.float64)
        self._bloques_adaptados = 0

    @property
    def convergido(self) -> bool:
        """Tras ~2 s de voz de Notivoz el filtro ya cancela bien el eco."""
        return self._bloques_adaptados > 200

    @property
    def listo(self) -> bool:
        """Se puede distinguir tu voz de la de Notivoz: el eco ya se cancela, o
        no hay eco que cancelar (audífonos)."""
        return self.convergido or self.sin_eco

    def procesar(self, mic: np.ndarray, ref: np.ndarray) -> np.ndarray:
        """Bloques int16 de igual largo (múltiplo de 160). Devuelve int16 sin eco."""
        ref_f = ref.astype(np.float32)
        mic_f = mic.astype(np.float64)
        # Historial de la referencia para aplicar el retardo.
        n = len(ref_f)
        self._historial_ref = np.roll(self._historial_ref, -n)
        self._historial_ref[-n:] = ref_f
        self._muestras_ref += n

        if self.retardo is None:
            self._acumular_para_retardo(mic_f, ref_f)
            if self.retardo is None:
                return mic
        fin = len(self._historial_ref) - self.retardo
        ref_retrasada = self._historial_ref[fin - n : fin].astype(np.float64)
        salida = np.empty(n, dtype=np.float64)
        for i in range(0, n, self._P):
            salida[i : i + self._P] = self._bloque(mic_f[i : i + self._P], ref_retrasada[i : i + self._P])
        return np.clip(salida, -32768, 32767).astype(np.int16)

    def _bloque(self, d: np.ndarray, x: np.ndarray) -> np.ndarray:
        p = self._P
        self._X = np.roll(self._X, 1, axis=0)
        self._X[0] = np.fft.rfft(np.concatenate([self._ref_anterior, x]))
        self._ref_anterior = x
        y = np.fft.irfft((self._X * self._W).sum(axis=0))[p:]
        e = d - y
        # Doble habla: si queda mucho más que el eco estimado, es tu voz; no
        # aprender de ella (el filtro se desajustaría).
        doble_habla = self.convergido and np.mean(e**2) > 4 * np.mean(y**2) + 1e4
        if np.abs(x).max() > 1.0 and not doble_habla:  # adaptar solo con referencia
            E = np.fft.rfft(np.concatenate([np.zeros(p), e]))
            # Normalizar por la energía de todas las particiones: estable con filtros largos.
            self._potencia = 0.9 * self._potencia + 0.1 * (np.abs(self._X) ** 2).sum(axis=0)
            # Regularizar con la energía media: las frecuencias casi vacías no
            # deben producir pasos enormes (sería inestable).
            paso = self._PASO / (self._potencia + 0.1 * self._potencia.mean() + self._REGULARIZACION)
            gradiente = np.fft.irfft(np.conj(self._X) * (E * paso), axis=1)
            gradiente[:, p:] = 0  # restricción: filtro lineal, no circular
            self._W += np.fft.rfft(gradiente, axis=1)
            self._bloques_adaptados += 1
        return e

    def _acumular_para_retardo(self, mic: np.ndarray, ref: np.ndarray) -> None:
        """Con ~1,5 s de voz de Notivoz, estima el retardo micrófono-parlante."""
        if np.abs(ref).max() < 300 and not self._estimacion_ref:
            return
        self._estimacion_mic.append(mic)
        self._estimacion_ref.append(ref.astype(np.float64))
        acumulado = sum(len(b) for b in self._estimacion_mic)
        rms = lambda x: float(np.sqrt(np.mean(x**2)))
        if acumulado == FRECUENCIA:
            # Al segundo ya debería oírse el eco (el retardo máximo es 0,5 s). Si el
            # micrófono sigue casi en silencio, no hay eco (audífonos): no esperar
            # más, por si le hablas encima enseguida.
            ultimo = np.concatenate(self._estimacion_mic)[-FRECUENCIA // 2 :]
            if rms(ultimo) < _ECO_DESPRECIABLE * rms(np.concatenate(self._estimacion_ref)):
                self.sin_eco = True
        if acumulado < int(1.5 * FRECUENCIA):
            return
        m = np.concatenate(self._estimacion_mic)
        r = np.concatenate(self._estimacion_ref)
        self._estimacion_mic, self._estimacion_ref = [], []
        tamano = 1 << int(np.ceil(np.log2(len(m) + self._RETARDO_MAXIMO)))
        M, R = np.fft.rfft(m, tamano), np.fft.rfft(r, tamano)
        cruce = M * np.conj(R)
        correlacion = np.fft.irfft(cruce / (np.abs(cruce) + 1e-9), tamano)[: self._RETARDO_MAXIMO]
        pico = int(np.argmax(correlacion))
        if rms(m) < _ECO_DESPRECIABLE * rms(r):
            # Micrófono casi mudo mientras Notivoz habla: no hay eco (un "pico" aquí
            # sería casualidad del ruido).
            self.sin_eco = True
        elif correlacion[pico] > 8 * np.median(np.abs(correlacion)):
            # Hay eco. Un poco antes del pico: el filtro cubre también los primeros reflejos.
            self.retardo = max(0, pico - 64)
            self.sin_eco = False
            self._reiniciar_filtro()
        # Si no, el micrófono oyó algo que no es eco (tu voz, ruido): volver a medir.

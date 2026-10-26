"""Autoprueba del ejecutable: `Notivoz.exe --autoprueba` carga cada pieza nativa
(voz, micrófono, Whisper, credenciales, IA) y deja el resultado en
%APPDATA%\\Notivoz\\autoprueba.txt. Sirve para comprobar un empaquetado sin
abrir la interfaz."""

import importlib
import traceback

from app.config import APP_VERSION, data_dir


def _probar(nombre: str, funcion, resultados: list[str]) -> bool:
    try:
        detalle = funcion() or ""
        resultados.append(f"OK    {nombre} {detalle}")
        return True
    except Exception:
        resultados.append(f"FALLA {nombre}\n{traceback.format_exc()}")
        return False


def ejecutar() -> int:
    resultados = [f"Notivoz {APP_VERSION}"]

    def base_de_datos():
        from app.data.database import init_db

        init_db()

    def credenciales():
        import keyring

        return type(keyring.get_keyring()).__name__

    def microfono():
        import sounddevice as sd

        return f"{len(sd.query_devices())} dispositivos"

    def vosk():
        import vosk as v

        v.SetLogLevel(-1)
        return "importado"

    def whisper():
        import ctranslate2

        importlib.import_module("tokenizers")
        return f"ctranslate2 {ctranslate2.__version__}"

    def voz_windows():
        import comtypes.client

        comtypes.client.CreateObject("SAPI.SpVoice")

    def voz_neural():
        importlib.import_module("edge_tts")

    def mp3():
        from app.services import mp3 as m

        return "decodificador listo" if m else ""

    def ia():
        import anthropic

        return f"anthropic {anthropic.__version__}"

    pruebas = [
        ("base de datos", base_de_datos),
        ("credenciales", credenciales),
        ("micrófono", microfono),
        ("vosk", vosk),
        ("whisper", whisper),
        ("voz de Windows", voz_windows),
        ("voz neural", voz_neural),
        ("mp3", mp3),
        ("IA", ia),
    ]
    todo_bien = all([_probar(n, f, resultados) for n, f in pruebas])
    (data_dir() / "autoprueba.txt").write_text("\n".join(resultados), encoding="utf-8")
    return 0 if todo_bien else 1

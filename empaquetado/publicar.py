"""Publica una versión de Notivoz en GitHub (Releases): los Notivoz instalados
la detectan y muestran «Hay una nueva actualización».

Pasos para sacar una versión nueva:
  1. Sube la versión en app/config.py (APP_VERSION = "0.1.1") en tu rama, y
     haz el merge a master como siempre.
  2. En master, actualizado y sin cambios pendientes:
         .venv\\Scripts\\python empaquetado\\publicar.py "Qué cambió en esta versión"
     Construye el instalador y crea el Release v0.1.1 con el instalador y su huella.

Requisitos (una sola vez): Inno Setup 6 y GitHub CLI con tu sesión iniciada
(`gh auth login`).
"""

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import construir  # noqa: E402

RAIZ = construir.RAIZ
REPOSITORIO = "Jhere03/notivoz"
_GH = [shutil.which("gh"), r"C:\Program Files\GitHub CLI\gh.exe"]


def _salida(comando: list[str]) -> str:
    return subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def main() -> None:
    notas = " ".join(sys.argv[1:]).strip() or "Mejoras y correcciones."
    gh = next((g for g in _GH if g and Path(g).exists()), None)
    if gh is None:
        raise SystemExit("Falta GitHub CLI. Instálalo con: winget install GitHub.cli")
    if subprocess.run([gh, "auth", "status"], capture_output=True).returncode != 0:
        raise SystemExit("Inicia sesión en GitHub una vez con: gh auth login")

    rama = _salida(["git", "branch", "--show-current"])
    if rama != "master":
        raise SystemExit(f"Publica desde master (estás en «{rama}»).")
    if _salida(["git", "status", "--porcelain"]):
        raise SystemExit("Hay cambios sin commit: súbelos antes de publicar.")
    subprocess.run(["git", "fetch", "origin", "master"], cwd=RAIZ, check=True)
    if _salida(["git", "rev-parse", "HEAD"]) != _salida(["git", "rev-parse", "origin/master"]):
        raise SystemExit("Tu master no coincide con GitHub: haz git pull (o git push) primero.")

    version = construir.version()
    etiqueta = f"v{version}"
    if subprocess.run([gh, "release", "view", etiqueta, "-R", REPOSITORIO], capture_output=True).returncode == 0:
        raise SystemExit(f"Ya existe el Release {etiqueta}: sube APP_VERSION en app/config.py.")

    construir.main()
    instalador = construir.DIST / "instalador" / f"Notivoz-Setup-{version}.exe"
    huella = instalador.parent / f"{instalador.name}.sha256"
    subprocess.run(
        [gh, "release", "create", etiqueta, str(instalador), str(huella), "-R", REPOSITORIO,
         "--target", "master", "--title", f"Notivoz {version}", "--notes", notas],
        cwd=RAIZ,
        check=True,
    )
    print(f"\nPublicado Notivoz {version}. Los Notivoz instalados mostrarán la actualización en unas horas")
    print("(o al abrirlos). Instalador para compartir:", instalador)


if __name__ == "__main__":
    main()

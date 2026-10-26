"""Construye Notivoz.exe y el instalador.

Uso (desde la raíz del proyecto):
    .venv\\Scripts\\python empaquetado\\construir.py

Resultado:
    dist\\Notivoz\\Notivoz.exe                      la app empaquetada
    dist\\instalador\\Notivoz-Setup-X.Y.Z.exe        el instalador para compartir
    dist\\instalador\\Notivoz-Setup-X.Y.Z.exe.sha256 su huella (la usa la actualización)
"""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
EMPAQUETADO = RAIZ / "empaquetado"
DIST = RAIZ / "dist"
_ISCC = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
]


def version() -> str:
    texto = (RAIZ / "app" / "config.py").read_text(encoding="utf-8")
    return re.search(r'APP_VERSION = "([\d.]+)"', texto).group(1)


def escribir_info_de_version(v: str) -> None:
    """Datos que Windows muestra en Propiedades → Detalles del .exe."""
    numeros = (v.split(".") + ["0", "0", "0"])[:4]
    tupla = ", ".join(numeros)
    (EMPAQUETADO / "version_windows.txt").write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tupla}), prodvers=({tupla})),
  kids=[
    StringFileInfo([StringTable('040A04B0', [
      StringStruct('CompanyName', 'Notivoz'),
      StringStruct('FileDescription', 'Notivoz - tus pendientes, con voz'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('ProductName', 'Notivoz'),
      StringStruct('ProductVersion', '{v}'),
      StringStruct('OriginalFilename', 'Notivoz.exe')])]),
    VarFileInfo([VarStruct('Translation', [0x040A, 1200])])
  ]
)
""",
        encoding="utf-8",
    )


def ejecutar(comando: list[str]) -> None:
    print(">", " ".join(str(c) for c in comando), flush=True)
    subprocess.run(comando, check=True, cwd=RAIZ)


def main() -> None:
    v = version()
    print(f"Construyendo Notivoz {v}")
    escribir_info_de_version(v)
    ejecutar([sys.executable, str(EMPAQUETADO / "crear_icono.py")])
    ejecutar([sys.executable, "-m", "PyInstaller", str(EMPAQUETADO / "notivoz.spec"), "--noconfirm",
              "--distpath", str(DIST), "--workpath", str(RAIZ / "build")])
    iscc = next((p for p in _ISCC if p.exists()), None)
    if iscc is None:
        raise SystemExit("No se encontró Inno Setup 6 (ISCC.exe). Instálalo con: winget install JRSoftware.InnoSetup")
    ejecutar([str(iscc), f"/DVersion={v}", str(EMPAQUETADO / "notivoz.iss")])
    instalador = DIST / "instalador" / f"Notivoz-Setup-{v}.exe"
    huella = hashlib.sha256(instalador.read_bytes()).hexdigest()
    (instalador.parent / f"{instalador.name}.sha256").write_text(f"{huella}  {instalador.name}\n", encoding="utf-8")
    print(f"\nListo: {instalador} ({instalador.stat().st_size / 1e6:.0f} MB)\nSHA-256: {huella}")


if __name__ == "__main__":
    main()

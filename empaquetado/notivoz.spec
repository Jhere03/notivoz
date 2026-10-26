# Empaquetado de Notivoz con PyInstaller (carpeta con Notivoz.exe y sus archivos).
#
# Uso (desde la raíz del proyecto):
#   .venv\Scripts\python -m PyInstaller empaquetado\notivoz.spec --noconfirm
#
# Resultado: dist\Notivoz\Notivoz.exe (lo usa el instalador de Inno Setup).

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

RAIZ = Path(SPECPATH).parent

datos = [(str(RAIZ / "assets"), "assets")]
binarios = []
# Bibliotecas nativas y datos que PyInstaller no detecta solo.
for paquete in ("vosk", "ctranslate2", "tokenizers", "sounddevice"):
    binarios += collect_dynamic_libs(paquete)
datos += collect_data_files("_sounddevice_data")
# keyring encuentra el Administrador de credenciales de Windows por sus metadatos.
datos += copy_metadata("keyring")

a = Analysis(
    [str(RAIZ / "main.py")],
    pathex=[str(RAIZ)],
    binaries=binarios,
    datas=datos,
    hiddenimports=["keyring.backends.Windows", "comtypes.stream"],
    excludes=["tkinter", "pytest", "pyflakes", "PyInstaller"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Notivoz",
    icon=str(RAIZ / "assets" / "notivoz.ico"),
    console=False,  # sin ventana negra de consola
    version=str(RAIZ / "empaquetado" / "version_windows.txt"),
)
coleccion = COLLECT(exe, a.binaries, a.datas, name="Notivoz")

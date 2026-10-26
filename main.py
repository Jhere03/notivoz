"""Punto de entrada de Notivoz.

Uso:
    python main.py            abre la ventana
    python main.py --inicio   modo "arranque con Windows": según la configuración
                              arranca oculto en la bandeja y lee tus pendientes
"""

import ctypes
import getpass
import logging
import sys

from PySide6.QtCore import QLocale, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_VERSION, data_dir
from app.data.database import init_db
from app.services import ajustes, inicio_windows
from app.services.ajustes import Clave
from app.services.voz import voz
from app.ui import apariencia
from app.ui.icono import icono_app
from app.ui.main_window import MainWindow
from app.ui.widgets import SinRuedaAccidental

# Con un único servidor local por usuario se evita abrir Notivoz dos veces.
_NOMBRE_INSTANCIA = f"{APP_NAME}-{getpass.getuser()}"
_MENSAJE_MOSTRAR = b"mostrar"

log = logging.getLogger(APP_NAME)


def _configurar_logs() -> None:
    # Con pythonw.exe (arranque con Windows) no hay consola: todo va a un archivo.
    handlers: list[logging.Handler] = [
        logging.FileHandler(data_dir() / "notivoz.log", encoding="utf-8")
    ]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    logging.getLogger("comtypes").setLevel(logging.WARNING)
    sys.excepthook = lambda tipo, valor, tb: log.critical(
        "Error no controlado", exc_info=(tipo, valor, tb)
    )


def _avisar_instancia_abierta(mostrar: bool) -> bool:
    """Si Notivoz ya está abierto, le pide mostrarse y devuelve True."""
    socket = QLocalSocket()
    socket.connectToServer(_NOMBRE_INSTANCIA)
    if not socket.waitForConnected(300):
        return False
    if mostrar:
        socket.write(_MENSAJE_MOSTRAR)
        socket.flush()
        socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return True


def _escuchar_otras_instancias(ventana: MainWindow) -> QLocalServer:
    servidor = QLocalServer()
    QLocalServer.removeServer(_NOMBRE_INSTANCIA)
    servidor.listen(_NOMBRE_INSTANCIA)

    def al_conectar() -> None:
        conexion = servidor.nextPendingConnection()
        conexion.waitForReadyRead(300)
        if conexion.readAll().data() == _MENSAJE_MOSTRAR:
            ventana.mostrar()
        conexion.disconnectFromServer()

    servidor.newConnection.connect(al_conectar)
    return servidor


def main() -> int:
    desde_windows = inicio_windows.ARG_INICIO in sys.argv[1:]
    _configurar_logs()

    # Meses y días en español (calendario, fechas).
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Peru))
    # Para que la barra de tareas muestre el icono de Notivoz y no el de Python.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(icono_app())
    app.setStyle("Fusion")
    # La app sigue viva en la bandeja aunque no haya ventanas visibles.
    app.setQuitOnLastWindowClosed(False)
    # La rueda del mouse desplaza la página en vez de cambiar listas y deslizadores.
    filtro_rueda = SinRuedaAccidental(app)
    app.installEventFilter(filtro_rueda)

    if _avisar_instancia_abierta(mostrar=not desde_windows):
        log.info("Notivoz ya estaba abierto; se trae al frente esa ventana.")
        return 0

    init_db()
    apariencia.instalar(app, ajustes.obtener(Clave.TEMA))
    inicio_windows.actualizar_ruta()
    voz().velocidad = ajustes.obtener(Clave.VOZ_VELOCIDAD)
    voz().volumen = ajustes.obtener(Clave.VOZ_VOLUMEN)
    voz().voz_neural = ajustes.obtener(Clave.VOZ_NOMBRE)
    app.aboutToQuit.connect(voz().cerrar)

    ventana = MainWindow()
    servidor = _escuchar_otras_instancias(ventana)  # noqa: F841 (debe seguir vivo)

    if not (desde_windows and ajustes.obtener(Clave.INICIAR_EN_BANDEJA)):
        ventana.show()
    if desde_windows and ajustes.obtener(Clave.LEER_AL_INICIAR):
        # Unos segundos de margen para que Windows termine de cargar el audio.
        QTimer.singleShot(4000, ventana.leer_pendientes)

    log.info("Notivoz %s iniciado%s", APP_VERSION, " con Windows" if desde_windows else "")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

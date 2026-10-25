"""Icono de Notivoz en la bandeja del sistema (junto al reloj)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.config import APP_NAME
from app.ui.icono import icono_app


class Bandeja(QSystemTrayIcon):
    abrir = Signal()
    nueva_tarea = Signal()
    nueva_nota = Signal()
    leer_pendientes = Signal()
    salir = Signal()

    def __init__(self, parent=None):
        super().__init__(icono_app(), parent)
        self.setToolTip(APP_NAME)

        menu = QMenu()
        menu.addAction("Abrir Notivoz", self.abrir.emit)
        menu.addSeparator()
        menu.addAction("Nueva tarea", self.nueva_tarea.emit)
        menu.addAction("Nueva nota", self.nueva_nota.emit)
        menu.addSeparator()
        menu.addAction("leeme", self.leer_pendientes.emit)
        menu.addSeparator()
        menu.addAction("Salir de Notivoz", self.salir.emit)
        # Se guarda como atributo: sin referencia Python lo borraría.
        self._menu = menu
        self.setContextMenu(menu)

        self.activated.connect(self._al_activar)

    def _al_activar(self, razon: QSystemTrayIcon.ActivationReason) -> None:
        if razon in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.abrir.emit()

    def avisar(self, titulo: str, mensaje: str) -> None:
        self.showMessage(titulo, mensaje, icono_app(), 5000)

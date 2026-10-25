"""Punto de entrada de Notivoz."""

import sys

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from app.config import APP_NAME, APP_VERSION
from app.data.database import init_db
from app.ui.main_window import MainWindow
from app.ui.theme import QSS


def main() -> int:
    # Meses y días en español (calendario, fechas).
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Peru))
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    init_db()

    ventana = MainWindow()
    ventana.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

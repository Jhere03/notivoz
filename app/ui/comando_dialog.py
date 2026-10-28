"""Formulario de un comando de voz y selector de aplicaciones instaladas."""

import os

from PySide6.QtCore import QFileInfo, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.data.models import Comando
from app.services import lanzador
from app.services.comandos import DatosApp, DatosComando, normalizar_frase
from app.services.escucha import palabras_desconocidas
from app.ui.iconos_menu import poner_icono

_ROL_DESTINO = Qt.ItemDataRole.UserRole


# Carpetas conocidas de Windows que aparecen en los AppID del menú Inicio.
_CARPETAS_CONOCIDAS = {
    "{6D809377-6AF0-444B-8957-A3773F02200E}": os.environ.get("ProgramFiles", ""),
    "{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}": os.environ.get("ProgramFiles(x86)", ""),
    "{F38BF404-1D43-42F2-9305-67DE0B28FC23}": os.environ.get("SystemRoot", ""),
    "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}": os.path.join(os.environ.get("SystemRoot", ""), "System32"),
}


def _ruta_real(destino: str) -> str:
    """De 'shell:AppsFolder\\{GUID}\\App\\app.exe' saca la ruta del .exe, si la hay."""
    prefijo = "shell:AppsFolder\\"
    if not destino.startswith(prefijo):
        return destino
    ruta = destino[len(prefijo):]
    for guid, carpeta in _CARPETAS_CONOCIDAS.items():
        if ruta.upper().startswith(guid):
            ruta = carpeta + ruta[len(guid):]
    return ruta


def icono_de(destino: str) -> QIcon:
    proveedor = QFileIconProvider()
    ruta = _ruta_real(destino)
    if os.path.exists(ruta):
        return proveedor.icon(QFileInfo(ruta))
    if "://" in destino:
        return proveedor.icon(QFileIconProvider.IconType.Network)
    return proveedor.icon(QFileIconProvider.IconType.Desktop)


class SelectorAppsDialog(QDialog):
    """Lista buscable de las apps del menú Inicio (incluye las de la Tienda)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Elegir aplicaciones")
        self.resize(460, 540)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            apps = lanzador.apps_instaladas()
        finally:
            QApplication.restoreOverrideCursor()

        self.buscar = QLineEdit()
        self.buscar.setPlaceholderText("Buscar… (por ejemplo: spotify, steam, opera)")
        self.buscar.setClearButtonEnabled(True)
        self.buscar.textChanged.connect(self._filtrar)

        self.lista = QListWidget()
        self.lista.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.lista.doubleClicked.connect(self.accept)
        for nombre, destino in apps:
            item = QListWidgetItem(nombre)
            item.setData(_ROL_DESTINO, destino)
            self.lista.addItem(item)

        ayuda = QLabel("Puedes elegir varias con Ctrl + clic.")
        ayuda.setObjectName("Resumen")

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Agregar")
        botones.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(10)
        layout.addWidget(self.buscar)
        layout.addWidget(self.lista, stretch=1)
        layout.addWidget(ayuda)
        layout.addWidget(botones)
        self.buscar.setFocus()

    def _filtrar(self, texto: str) -> None:
        texto = texto.strip().lower()
        for i in range(self.lista.count()):
            item = self.lista.item(i)
            item.setHidden(bool(texto) and texto not in item.text().lower())

    def elegidas(self) -> list[DatosApp]:
        return [DatosApp(i.text(), i.data(_ROL_DESTINO)) for i in self.lista.selectedItems()]


class ComandoDialog(QDialog):
    def __init__(self, comando: Comando | None = None, parent=None):
        super().__init__(parent)
        self._id = comando.id if comando else None
        self.setWindowTitle("Editar comando" if comando else "Nuevo comando")
        self.setMinimumWidth(540)

        self.frase = QLineEdit()
        self.frase.setPlaceholderText("Por ejemplo: modo trabajo")
        self.frase.setMaxLength(120)
        self.frase.textChanged.connect(self._actualizar_ejemplo)

        self.ejemplo = QLabel()
        self.ejemplo.setObjectName("Ayuda")
        self.ejemplo.setWordWrap(True)

        self.respuesta = QLineEdit()
        self.respuesta.setMaxLength(200)

        self.activo = QCheckBox("Comando activo")
        self.activo.setChecked(True)

        self.apps = QListWidget()
        self.apps.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.apps.setMinimumHeight(170)
        self.apps.setToolTip("Arrastra para cambiar el orden en que se abren")

        botones_apps = QHBoxLayout()
        botones_apps.setSpacing(6)
        for texto, accion in (
            ("App instalada…", self._agregar_instalada),
            ("Programa .exe…", self._agregar_archivo),
            ("Archivo…", self._agregar_documento),
            ("Web o enlace…", self._agregar_enlace),
        ):
            boton = QPushButton(texto)
            poner_icono(boton, "mas")
            boton.setAutoDefault(False)
            boton.clicked.connect(accion)
            botones_apps.addWidget(boton)
        botones_apps.addStretch()
        quitar = QPushButton("Quitar")
        quitar.setAutoDefault(False)
        quitar.clicked.connect(self._quitar)
        botones_apps.addWidget(quitar)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Frase *", self.frase)
        form.addRow("", self.ejemplo)
        form.addRow("Respuesta", self.respuesta)
        form.addRow("", self.activo)

        etiqueta_apps = QLabel("Aplicaciones y archivos que abre *")
        etiqueta_apps.setObjectName("SeccionTitulo")

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        botones.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primario")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botones.accepted.connect(self._validar)
        botones.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        layout.addLayout(form)
        layout.addWidget(etiqueta_apps)
        layout.addWidget(self.apps, stretch=1)
        layout.addLayout(botones_apps)
        layout.addWidget(botones)

        if comando is not None:
            self.frase.setText(comando.frase)
            self.respuesta.setText(comando.respuesta)
            self.activo.setChecked(comando.activo)
            for app in comando.apps:
                self._anadir(DatosApp(app.nombre, app.destino))
        self._actualizar_ejemplo()
        self.frase.setFocus()

    def _actualizar_ejemplo(self) -> None:
        frase = normalizar_frase(self.frase.text()) or "modo trabajo"
        self.ejemplo.setText(f"Di: «Notivoz, {frase}»")
        self.respuesta.setPlaceholderText(f"{frase.capitalize()} activado")

    def _anadir(self, app: DatosApp) -> None:
        existentes = {self.apps.item(i).data(_ROL_DESTINO) for i in range(self.apps.count())}
        if app.destino in existentes:
            return
        item = QListWidgetItem(icono_de(app.destino), app.nombre)
        item.setData(_ROL_DESTINO, app.destino)
        item.setToolTip(app.destino)
        self.apps.addItem(item)

    def _agregar_instalada(self) -> None:
        selector = SelectorAppsDialog(self)
        if selector.exec():
            for app in selector.elegidas():
                self._anadir(app)

    def _agregar_archivo(self) -> None:
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Elegir programas", "C:\\", "Programas y accesos directos (*.exe *.lnk *.bat);;Todos (*.*)"
        )
        for ruta in rutas:
            ruta = os.path.normpath(ruta)
            self._anadir(DatosApp(os.path.splitext(os.path.basename(ruta))[0], ruta))

    def _agregar_documento(self) -> None:
        """Cualquier archivo (Excel, PDF, Word, imágenes…): se abre con su
        programa predeterminado, como al darle doble clic."""
        rutas, _ = QFileDialog.getOpenFileNames(
            self,
            "Elegir archivos",
            os.path.join(os.path.expanduser("~"), "Documents"),
            "Documentos e imágenes (*.pdf *.doc *.docx *.xls *.xlsx *.xlsm *.csv *.ppt *.pptx *.txt "
            "*.odt *.ods *.png *.jpg *.jpeg *.gif *.bmp *.webp *.mp3 *.mp4);;Todos los archivos (*.*)",
        )
        for ruta in rutas:
            ruta = os.path.normpath(ruta)
            self._anadir(DatosApp(os.path.basename(ruta), ruta))

    def _agregar_enlace(self) -> None:
        enlace, ok = QInputDialog.getText(
            self, "Web o enlace", "Dirección (por ejemplo https://youtube.com o steam://open/main):"
        )
        enlace = lanzador.normalizar_destino(enlace)
        if ok and enlace:
            nombre = enlace.split("://", 1)[-1].strip("/").split("/")[0] or enlace
            self._anadir(DatosApp(nombre, enlace))

    def _quitar(self) -> None:
        for item in self.apps.selectedItems():
            self.apps.takeItem(self.apps.row(item))

    def _validar(self) -> None:
        frase = normalizar_frase(self.frase.text())
        if not frase:
            QMessageBox.warning(self, "Falta la frase", "Escribe la frase que vas a decir.")
            self.frase.setFocus()
            return
        if self.apps.count() == 0:
            QMessageBox.warning(self, "Sin aplicaciones", "Agrega al menos una aplicación o archivo para abrir.")
            return
        desconocidas = palabras_desconocidas(frase)
        if desconocidas:
            lista = ", ".join(f"«{p}»" for p in desconocidas)
            respuesta = QMessageBox.question(
                self,
                "Palabras que no reconocerá",
                f"El reconocimiento de voz no conoce {lista}, así que no podrá oír esta frase.\n\n"
                "Prueba con otras palabras en español (por ejemplo «modo relax» o «modo juego»).\n\n"
                "¿Guardar de todos modos? (Podrás ejecutarlo con el botón ▶).",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                self.frase.setFocus()
                return
        self.accept()

    def datos(self) -> DatosComando:
        apps = [
            DatosApp(self.apps.item(i).text(), self.apps.item(i).data(_ROL_DESTINO))
            for i in range(self.apps.count())
        ]
        return DatosComando(
            id=self._id,
            frase=self.frase.text(),
            respuesta=self.respuesta.text(),
            activo=self.activo.isChecked(),
            apps=apps,
        )

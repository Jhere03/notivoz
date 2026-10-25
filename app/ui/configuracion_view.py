"""Vista de configuración: inicio con Windows, bandeja y voz."""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.config import data_dir
from app.services import ajustes, inicio_windows
from app.services.ajustes import Clave
from app.services.voz import VOCES_NEURALES, VOZ_WINDOWS, voz


def _seccion(titulo: str, descripcion: str = "") -> tuple[QFrame, QVBoxLayout]:
    marco = QFrame()
    marco.setObjectName("Seccion")
    # Altura fija a su tamaño natural: si no, el scroll aplasta los campos.
    marco.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(marco)
    layout.setContentsMargins(20, 16, 20, 18)
    layout.setSpacing(12)
    encabezado = QLabel(titulo)
    encabezado.setObjectName("SeccionTitulo")
    layout.addWidget(encabezado)
    if descripcion:
        texto = QLabel(descripcion)
        texto.setObjectName("Resumen")
        texto.setWordWrap(True)
        layout.addWidget(texto)
    return marco, layout


def _ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("Ayuda")
    etiqueta.setWordWrap(True)
    return etiqueta


class ConfiguracionView(QWidget):
    probar_saludo = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Configuración")
        titulo.setObjectName("TituloVista")

        # --- Inicio ----------------------------------------------------------
        inicio, l_inicio = _seccion("Inicio con Windows")
        self.con_windows = QCheckBox("Iniciar Notivoz al encender la PC")
        self.con_windows.setChecked(inicio_windows.esta_activo())
        self.con_windows.toggled.connect(self._cambiar_inicio_windows)
        self.en_bandeja = QCheckBox("Arrancar oculto en la bandeja (sin abrir la ventana)")
        self.en_bandeja.setChecked(ajustes.obtener(Clave.INICIAR_EN_BANDEJA))
        self.en_bandeja.toggled.connect(lambda v: ajustes.guardar(Clave.INICIAR_EN_BANDEJA, v))
        self.leer = QCheckBox("Leer en voz alta mis pendientes y los recordatorios de hoy")
        self.leer.setChecked(ajustes.obtener(Clave.LEER_AL_INICIAR))
        self.leer.toggled.connect(lambda v: ajustes.guardar(Clave.LEER_AL_INICIAR, v))
        l_inicio.addWidget(self.con_windows)
        l_inicio.addWidget(self.en_bandeja)
        l_inicio.addWidget(self.leer)
        l_inicio.addWidget(
            _ayuda("Las dos últimas opciones solo se aplican cuando Notivoz arranca junto con Windows.")
        )

        # --- Bandeja ---------------------------------------------------------
        bandeja, l_bandeja = _seccion("Bandeja del sistema")
        self.cerrar_a_bandeja = QCheckBox("Al cerrar la ventana, seguir funcionando en la bandeja")
        self.cerrar_a_bandeja.setChecked(ajustes.obtener(Clave.CERRAR_A_BANDEJA))
        self.cerrar_a_bandeja.toggled.connect(lambda v: ajustes.guardar(Clave.CERRAR_A_BANDEJA, v))
        l_bandeja.addWidget(self.cerrar_a_bandeja)
        l_bandeja.addWidget(
            _ayuda(
                "Recomendado: así los recordatorios siguen sonando aunque cierres la ventana. "
                "Para salir del todo usa clic derecho en el icono → «Salir de Notivoz»."
            )
        )

        # --- Voz -------------------------------------------------------------
        seccion_voz, l_voz = _seccion("Voz")
        self.voz = QComboBox()
        for nombre, etiqueta in VOCES_NEURALES.items():
            self.voz.addItem(etiqueta, nombre)
        self.voz.addItem("Voz de Windows (sin internet, más robótica)", VOZ_WINDOWS)
        self.voz.setCurrentIndex(max(self.voz.findData(ajustes.obtener(Clave.VOZ_NOMBRE)), 0))
        self.voz.currentIndexChanged.connect(self._cambiar_voz)

        self.nombre = QLineEdit(ajustes.obtener(Clave.NOMBRE))
        self.nombre.setPlaceholderText("Tu nombre, para el saludo (opcional)")
        self.nombre.setMaxLength(40)
        self.nombre.editingFinished.connect(
            lambda: ajustes.guardar(Clave.NOMBRE, self.nombre.text().strip())
        )

        self.velocidad = self._slider(-5, 5, ajustes.obtener(Clave.VOZ_VELOCIDAD))
        self.velocidad.valueChanged.connect(self._cambiar_velocidad)
        self.volumen = self._slider(10, 100, ajustes.obtener(Clave.VOZ_VOLUMEN))
        self.volumen.valueChanged.connect(self._cambiar_volumen)
        self.etq_velocidad = QLabel()
        self.etq_volumen = QLabel()
        for etiqueta in (self.etq_velocidad, self.etq_volumen):
            etiqueta.setObjectName("Resumen")
            etiqueta.setFixedWidth(70)
        self._actualizar_etiquetas()

        probar = QPushButton("▶  Probar: leeme")
        probar.setObjectName("Secundario")
        probar.setCursor(Qt.CursorShape.PointingHandCursor)
        probar.clicked.connect(self._probar)

        l_voz.addWidget(self._fila("Voz", self.voz))
        l_voz.addWidget(
            _ayuda(
                "Las voces naturales necesitan internet: el texto a leer se envía al servicio "
                "de voz de Microsoft. Sin conexión, Notivoz usa la voz de Windows. Las frases "
                "que ya dijo antes se guardan y suenan también sin internet."
            )
        )
        l_voz.addWidget(self._fila("Tu nombre", self.nombre))
        l_voz.addWidget(self._fila("Velocidad", self.velocidad, self.etq_velocidad))
        l_voz.addWidget(self._fila("Volumen", self.volumen, self.etq_volumen))
        fila_probar = QHBoxLayout()
        fila_probar.addWidget(probar)
        fila_probar.addStretch()
        l_voz.addLayout(fila_probar)

        # --- Datos -----------------------------------------------------------
        datos, l_datos = _seccion(
            "Datos", f"Tus tareas, clientes y notas se guardan en:\n{data_dir()}"
        )
        abrir = QPushButton("Abrir carpeta de datos")
        abrir.clicked.connect(lambda: os.startfile(data_dir()))
        fila_datos = QHBoxLayout()
        fila_datos.addWidget(abrir)
        fila_datos.addStretch()
        l_datos.addLayout(fila_datos)

        contenido = QWidget()
        contenido.setObjectName("ListaNotas")
        columna = QVBoxLayout(contenido)
        columna.setContentsMargins(0, 0, 6, 0)
        columna.setSpacing(14)
        for marco in (inicio, bandeja, seccion_voz, datos):
            marco.setMaximumWidth(760)
            columna.addWidget(marco)
        columna.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("ScrollNotas")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(contenido)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)
        layout.addWidget(titulo)
        layout.addWidget(scroll, stretch=1)

    @staticmethod
    def _slider(minimo: int, maximo: int, valor: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimo, maximo)
        slider.setValue(valor)
        slider.setCursor(Qt.CursorShape.PointingHandCursor)
        return slider

    @staticmethod
    def _fila(texto: str, *widgets: QWidget) -> QWidget:
        fila = QWidget()
        fila.setObjectName("Fila")
        layout = QHBoxLayout(fila)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        etiqueta = QLabel(texto)
        etiqueta.setFixedWidth(90)
        layout.addWidget(etiqueta)
        for i, widget in enumerate(widgets):
            layout.addWidget(widget, stretch=1 if i == 0 else 0)
        return fila

    def _actualizar_etiquetas(self) -> None:
        v = self.velocidad.value()
        self.etq_velocidad.setText("Normal" if v == 0 else f"{v:+d}")
        self.etq_volumen.setText(f"{self.volumen.value()} %")

    def _cambiar_velocidad(self, valor: int) -> None:
        voz().velocidad = valor
        ajustes.guardar(Clave.VOZ_VELOCIDAD, valor)
        self._actualizar_etiquetas()

    def _cambiar_volumen(self, valor: int) -> None:
        voz().volumen = valor
        ajustes.guardar(Clave.VOZ_VOLUMEN, valor)
        self._actualizar_etiquetas()

    def _cambiar_voz(self) -> None:
        nombre = self.voz.currentData()
        voz().voz_neural = nombre
        ajustes.guardar(Clave.VOZ_NOMBRE, nombre)
        # Una muestra corta para escuchar la voz elegida.
        if nombre:
            etiqueta = VOCES_NEURALES[nombre].split(" · ")[0]
            voz().hablar(f"Hola, soy {etiqueta}. Así sonaré en Notivoz.")
        else:
            voz().hablar("Hola. Esta es la voz de Windows.")

    def _cambiar_inicio_windows(self, activo: bool) -> None:
        try:
            inicio_windows.activar(activo)
        except OSError as error:
            QMessageBox.warning(self, "No se pudo cambiar", f"Windows no permitió el cambio:\n{error}")
            self.con_windows.blockSignals(True)
            self.con_windows.setChecked(inicio_windows.esta_activo())
            self.con_windows.blockSignals(False)

    def _probar(self) -> None:
        ajustes.guardar(Clave.NOMBRE, self.nombre.text().strip())
        self.probar_saludo.emit()

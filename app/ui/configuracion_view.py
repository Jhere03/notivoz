"""Vista de configuración: inicio con Windows, bandeja y voz."""

import threading

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services import ajustes, inicio_windows, lanzador, modelo_voz
from app.services.ajustes import Clave
from app.services.audio import nombre_legible, nombres_dispositivos, reproductor
from app.services.escucha import NOMBRE_ACTIVACION, dispositivos_entrada
from app.services.microfono import PruebaMicrofono
from app.services.personalidad import Personalidad
from app.services.rutinas import DIAS_CORTOS
from app.services.voz import VOCES_NEURALES, VOZ_WINDOWS, voz
from app.ui import theme
from app.ui.apariencia import acrilico_disponible, apariencia
from app.ui.ia_config import SeccionIA
from app.ui.widgets import HoraEdit


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


def _miniatura(nombre: str) -> QIcon:
    """Dibujo de una ventanita con los colores del tema."""
    c = theme.paleta(nombre)
    ancho, alto = 132, 82
    pixmap = QPixmap(ancho * 2, alto * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QColor(c["borde"]))
    marco = QRectF(0.5, 0.5, ancho - 1, alto - 1)
    if nombre == theme.TRANSLUCIDO:
        # Lo que hay "detrás" de la ventana, visto a través de ella.
        detras = QLinearGradient(0, 0, ancho, alto)
        detras.setColorAt(0, QColor("#3d8bfd"))
        detras.setColorAt(0.5, QColor("#7c5cff"))
        detras.setColorAt(1, QColor("#2dd4bf"))
        p.setBrush(detras)
        p.drawRoundedRect(marco, 8, 8)
        fondo, lateral = QColor(14, 16, 21, 150), QColor(28, 31, 39, 120)
    else:
        fondo, lateral = QColor(c["fondo"]), QColor(c["superficie"])
    p.setBrush(fondo)
    p.drawRoundedRect(marco, 8, 8)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(lateral)
    p.drawRoundedRect(QRectF(1, 1, 36, alto - 2), 7, 7)
    p.setBrush(QColor(c["acento"]))
    p.drawRoundedRect(QRectF(6, 14, 26, 7), 3, 3)
    p.setBrush(QColor(c["texto_suave"]))
    for y in (27, 37):
        p.drawRoundedRect(QRectF(6, y, 22, 5), 2, 2)
    p.setBrush(QColor(c["texto"]))
    p.drawRoundedRect(QRectF(46, 12, 46, 7), 3, 3)
    tarjeta = QColor(c["superficie"])
    if nombre == theme.TRANSLUCIDO:
        tarjeta = QColor(46, 50, 61, 150)
    p.setBrush(tarjeta)
    p.drawRoundedRect(QRectF(46, 28, ancho - 56, 42), 5, 5)
    p.setBrush(QColor(c["acento"]))
    p.drawRoundedRect(QRectF(ancho - 40, 58, 28, 8), 3, 3)
    p.end()
    return QIcon(pixmap)


def _ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("Ayuda")
    etiqueta.setWordWrap(True)
    return etiqueta


class ConfiguracionView(QWidget):
    probar_saludo = Signal()
    # Cambió el micrófono o la palabra de activación: la escucha debe reajustarse.
    escucha_config_cambiada = Signal()
    modelo_instalado = Signal()
    # True al empezar la prueba de micrófono (pausar la escucha), False al terminar.
    prueba_microfono_cambiada = Signal(bool)
    personalidad_cambiada = Signal()
    ia_cambiada = Signal()
    _descarga_progreso = Signal(int, int)
    _descarga_terminada = Signal(str)  # mensaje de error, o "" si fue bien

    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Configuración")
        titulo.setObjectName("TituloVista")

        # --- Apariencia ------------------------------------------------------
        seccion_tema, l_tema = _seccion("Apariencia")
        self.grupo_tema = QButtonGroup(self)
        fila_temas = QHBoxLayout()
        fila_temas.setSpacing(10)
        tema_guardado = ajustes.obtener(Clave.TEMA)
        for nombre, etiqueta in theme.TEMAS.items():
            opcion = QToolButton()
            opcion.setText(etiqueta)
            opcion.setObjectName("OpcionTema")
            opcion.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            opcion.setCheckable(True)
            opcion.setCursor(Qt.CursorShape.PointingHandCursor)
            opcion.setIcon(_miniatura(nombre))
            opcion.setIconSize(QSize(132, 82))
            opcion.setProperty("tema", nombre)
            if nombre == theme.TRANSLUCIDO and not acrilico_disponible():
                opcion.setEnabled(False)
                opcion.setToolTip("Necesita Windows 11")
            opcion.setChecked(nombre == tema_guardado)
            self.grupo_tema.addButton(opcion)
            fila_temas.addWidget(opcion)
        fila_temas.addStretch()
        self.grupo_tema.buttonClicked.connect(self._cambiar_tema)
        l_tema.addLayout(fila_temas)
        l_tema.addWidget(
            _ayuda(
                "Translúcido deja ver, desenfocado, lo que hay detrás de Notivoz "
                "(como el Explorador de Windows 11). Cuando la ventana no está activa, "
                "Windows la muestra opaca."
            )
        )

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

        self.personalidad = QComboBox()
        for personalidad in Personalidad:
            self.personalidad.addItem(personalidad.etiqueta, personalidad.value)
        self.personalidad.setCurrentIndex(
            max(self.personalidad.findData(ajustes.obtener(Clave.PERSONALIDAD)), 0)
        )
        self.ejemplo_personalidad = _ayuda("")
        self._mostrar_ejemplo_personalidad()
        self.personalidad.currentIndexChanged.connect(self._cambiar_personalidad)

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
        l_voz.addWidget(self._fila("Personalidad", self.personalidad))
        l_voz.addWidget(self.ejemplo_personalidad)
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
        self.salida = QComboBox()
        self.salida.addItem("Salida predeterminada de Windows", "")
        for nombre in nombres_dispositivos(entrada=False):
            self.salida.addItem(nombre_legible(nombre), nombre)
        self.salida.setCurrentIndex(max(self.salida.findData(ajustes.obtener(Clave.SALIDA_VOZ)), 0))
        self.salida.currentIndexChanged.connect(self._cambiar_salida)
        l_voz.addWidget(self._fila("Salida", self.salida))
        fila_probar = QHBoxLayout()
        fila_probar.addWidget(probar)
        fila_probar.addStretch()
        l_voz.addLayout(fila_probar)

        # --- Comandos de voz --------------------------------------------------
        seccion_escucha, l_escucha = _seccion("Comandos de voz")
        self.estado_modelo = QLabel()
        self.estado_modelo.setWordWrap(True)
        self.btn_descargar = QPushButton(
            f"Descargar modelo de voz en español (≈{modelo_voz.TAMANO_APROX_MB} MB)"
        )
        self.btn_descargar.setObjectName("Secundario")
        self.btn_descargar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_descargar.clicked.connect(self._descargar_modelo)
        self.progreso = QProgressBar()
        self.progreso.hide()
        fila_descarga = QHBoxLayout()
        fila_descarga.addWidget(self.btn_descargar)
        fila_descarga.addWidget(self.progreso, stretch=1)

        como_usar = QLabel(
            f"Cada comando empieza siempre con la palabra «{NOMBRE_ACTIVACION}». "
            f"Di, por ejemplo, «{NOMBRE_ACTIVACION}, y el comando configurado», o di solo «{NOMBRE_ACTIVACION}», "
            "espera el pitido y di el comando en los 5 segundos siguientes."
            f"Sin «{NOMBRE_ACTIVACION}» no se ejecuta nada, así una conversación normal nunca abre aplicaciones."
        )
        como_usar.setWordWrap(True)

        self.btn_probar_mic = QPushButton("🎙  Probar micrófono")
        self.btn_probar_mic.setObjectName("Secundario")
        self.btn_probar_mic.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_probar_mic.setCheckable(True)
        self.btn_probar_mic.toggled.connect(self._alternar_prueba_mic)
        self.nivel_mic = QProgressBar()
        self.nivel_mic.setRange(0, 100)
        self.nivel_mic.hide()
        self.ayuda_prueba = _ayuda(
            "Habla: oirás tu voz con 1 segundo de retraso. Usa audífonos para evitar eco."
        )
        self.ayuda_prueba.hide()
        fila_prueba = QHBoxLayout()
        fila_prueba.addWidget(self.btn_probar_mic)
        fila_prueba.addWidget(self.nivel_mic, stretch=1)
        self._prueba_mic = PruebaMicrofono()
        self._reloj_nivel = QTimer(self, interval=50)
        self._reloj_nivel.timeout.connect(
            lambda: self.nivel_mic.setValue(int(self._prueba_mic.nivel * 100))
        )

        self.microfono = QComboBox()
        self.microfono.addItem("Micrófono predeterminado de Windows", "")
        for nombre in dispositivos_entrada():
            self.microfono.addItem(nombre, nombre)
        self.microfono.setCurrentIndex(max(self.microfono.findData(ajustes.obtener(Clave.MICROFONO)), 0))
        self.microfono.currentIndexChanged.connect(self._cambiar_microfono)

        l_escucha.addWidget(self.estado_modelo)
        l_escucha.addLayout(fila_descarga)
        l_escucha.addWidget(como_usar)
        l_escucha.addWidget(self._fila("Micrófono", self.microfono))
        l_escucha.addLayout(fila_prueba)
        l_escucha.addWidget(self.ayuda_prueba)
        l_escucha.addWidget(
            _ayuda(
                "El reconocimiento de voz funciona sin internet: el audio del micrófono nunca sale "
                "de tu PC. El micrófono se enciende o apaga desde la sección «Comandos de voz»."
            )
        )
        self._descarga_progreso.connect(self._al_progresar_descarga)
        self._descarga_terminada.connect(self._al_terminar_descarga)
        self._actualizar_estado_modelo()

        # --- Productividad -----------------------------------------------------
        productividad, l_prod = _seccion("Productividad")
        self.celebrar = QCheckBox("Celebrar mi racha cuando termino la primera tarea del día")
        self.celebrar.setChecked(ajustes.obtener(Clave.CELEBRAR_RACHA))
        self.celebrar.toggled.connect(lambda v: ajustes.guardar(Clave.CELEBRAR_RACHA, v))
        self.resumen_apagar = QCheckBox("Leerme el resumen del día al apagar la PC")
        self.resumen_apagar.setChecked(ajustes.obtener(Clave.RESUMEN_AL_APAGAR))
        self.resumen_apagar.toggled.connect(lambda v: ajustes.guardar(Clave.RESUMEN_AL_APAGAR, v))
        self.aviso_ocio = QCheckBox("Recordarme mis tareas si abro apps de ocio en horario de trabajo")
        self.aviso_ocio.setChecked(ajustes.obtener(Clave.AVISO_OCIO))
        self.aviso_ocio.toggled.connect(self._cambiar_aviso_ocio)

        # Horario laboral
        self.dias_laborales: list[QPushButton] = []
        fila_dias = QHBoxLayout()
        fila_dias.setSpacing(4)
        dias_guardados = set(ajustes.obtener(Clave.HORARIO_DIAS))
        for i, dia in enumerate(DIAS_CORTOS):
            boton = QPushButton(dia)
            boton.setObjectName("Dia")
            boton.setCheckable(True)
            boton.setChecked(i in dias_guardados)
            boton.setFixedWidth(46)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.toggled.connect(self._guardar_horario)
            self.dias_laborales.append(boton)
            fila_dias.addWidget(boton)
        fila_dias.addStretch()
        self.hora_inicio = HoraEdit()
        self.hora_inicio.setText(ajustes.obtener(Clave.HORARIO_INICIO))
        self.hora_fin = HoraEdit()
        self.hora_fin.setText(ajustes.obtener(Clave.HORARIO_FIN))
        for campo in (self.hora_inicio, self.hora_fin):
            campo.editingFinished.connect(self._guardar_horario)
        fila_horas = QHBoxLayout()
        fila_horas.setSpacing(8)
        fila_horas.addWidget(QLabel("de"))
        fila_horas.addWidget(self.hora_inicio)
        fila_horas.addWidget(QLabel("a"))
        fila_horas.addWidget(self.hora_fin)
        fila_horas.addStretch()

        # Apps de ocio
        self.apps_ocio = QListWidget()
        self.apps_ocio.setFixedHeight(110)
        self.apps_ocio.addItems(ajustes.obtener(Clave.APPS_OCIO))
        agregar_app = QPushButton("+ Elegir de las apps abiertas")
        agregar_app.setAutoDefault(False)
        agregar_app.clicked.connect(self._agregar_app_ocio)
        quitar_app = QPushButton("Quitar")
        quitar_app.setAutoDefault(False)
        quitar_app.clicked.connect(self._quitar_app_ocio)
        fila_apps = QHBoxLayout()
        fila_apps.addWidget(agregar_app)
        fila_apps.addWidget(quitar_app)
        fila_apps.addStretch()

        self._bloque_ocio = QWidget()
        self._bloque_ocio.setObjectName("Fila")
        bloque = QVBoxLayout(self._bloque_ocio)
        bloque.setContentsMargins(26, 0, 0, 0)
        bloque.setSpacing(8)
        bloque.addWidget(QLabel("Horario de trabajo"))
        bloque.addLayout(fila_dias)
        bloque.addLayout(fila_horas)
        bloque.addWidget(QLabel("Apps de ocio"))
        bloque.addWidget(self.apps_ocio)
        bloque.addLayout(fila_apps)
        self._bloque_ocio.setEnabled(self.aviso_ocio.isChecked())

        l_prod.addWidget(self.celebrar)
        l_prod.addWidget(self.resumen_apagar)
        l_prod.addWidget(
            _ayuda("Al apagar, Windows mostrará «Notivoz está leyendo tu resumen» unos segundos; puedes apagar igual.")
        )
        l_prod.addWidget(self.aviso_ocio)
        l_prod.addWidget(
            _ayuda("Como mucho una vez cada 30 minutos, Notivoz te recuerda tu tarea más importante.")
        )
        l_prod.addWidget(self._bloque_ocio)

        contenido = QWidget()
        contenido.setObjectName("ListaNotas")
        columna = QVBoxLayout(contenido)
        columna.setContentsMargins(0, 0, 6, 0)
        columna.setSpacing(14)
        self.seccion_ia = SeccionIA()
        self.seccion_ia.cambiada.connect(self.ia_cambiada)
        for marco in (seccion_tema, inicio, bandeja, seccion_voz, seccion_escucha, self.seccion_ia, productividad):
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

    def _cambiar_tema(self, boton: QToolButton) -> None:
        nombre = boton.property("tema")
        ajustes.guardar(Clave.TEMA, nombre)
        apariencia().aplicar(nombre)

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

    def _mostrar_ejemplo_personalidad(self) -> None:
        personalidad = Personalidad(self.personalidad.currentData())
        self.ejemplo_personalidad.setText(f"Por ejemplo: {personalidad.ejemplo}")

    def _cambiar_personalidad(self) -> None:
        ajustes.guardar(Clave.PERSONALIDAD, self.personalidad.currentData())
        # Solo se muestra el ejemplo escrito: cambiar de personalidad no habla.
        self._mostrar_ejemplo_personalidad()
        self.personalidad_cambiada.emit()

    def _cambiar_aviso_ocio(self, activo: bool) -> None:
        ajustes.guardar(Clave.AVISO_OCIO, activo)
        self._bloque_ocio.setEnabled(activo)

    def _guardar_horario(self) -> None:
        dias = [i for i, boton in enumerate(self.dias_laborales) if boton.isChecked()]
        ajustes.guardar(Clave.HORARIO_DIAS, dias)
        for campo, clave in ((self.hora_inicio, Clave.HORARIO_INICIO), (self.hora_fin, Clave.HORARIO_FIN)):
            if campo.hora() is not None:
                ajustes.guardar(clave, campo.text())

    def _guardar_apps_ocio(self) -> None:
        apps = [self.apps_ocio.item(i).text() for i in range(self.apps_ocio.count())]
        ajustes.guardar(Clave.APPS_OCIO, apps)

    def _agregar_app_ocio(self) -> None:
        actuales = {self.apps_ocio.item(i).text() for i in range(self.apps_ocio.count())}
        menu = QMenu(self)
        for nombre in lanzador.apps_con_ventana():
            if nombre not in actuales:
                menu.addAction(nombre, lambda n=nombre: (self.apps_ocio.addItem(n), self._guardar_apps_ocio()))
        if menu.isEmpty():
            menu.addAction("Abre primero la app (por ejemplo Steam) y vuelve a intentarlo").setEnabled(False)
        menu.exec(QCursor.pos())

    def _quitar_app_ocio(self) -> None:
        for item in self.apps_ocio.selectedItems():
            self.apps_ocio.takeItem(self.apps_ocio.row(item))
        self._guardar_apps_ocio()

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

    # --- Comandos de voz -------------------------------------------------------

    def refrescar_modelos(self) -> None:
        """Los modelos de voz se descargaron solos (primera vez)."""
        self._actualizar_estado_modelo()
        self.seccion_ia.actualizar()

    def _actualizar_estado_modelo(self) -> None:
        if modelo_voz.instalado():
            self.estado_modelo.setText("✓  Modelo de voz en español instalado.")
            self.btn_descargar.hide()
        else:
            self.estado_modelo.setText(
                "Para reconocer comandos de voz, Notivoz necesita descargar una sola vez "
                "el modelo de voz en español de Vosk."
            )
            self.btn_descargar.show()

    def _descargar_modelo(self) -> None:
        self.btn_descargar.setEnabled(False)
        self.btn_descargar.setText("Descargando…")
        self.progreso.setValue(0)
        self.progreso.show()

        def trabajar() -> None:
            try:
                modelo_voz.descargar(lambda leidos, total: self._descarga_progreso.emit(leidos, total))
                self._descarga_terminada.emit("")
            except Exception as error:
                self._descarga_terminada.emit(str(error) or error.__class__.__name__)

        threading.Thread(target=trabajar, name="DescargaModelo", daemon=True).start()

    def _al_progresar_descarga(self, leidos: int, total: int) -> None:
        if total:
            self.progreso.setValue(int(leidos * 100 / total))

    def _al_terminar_descarga(self, error: str) -> None:
        self.progreso.hide()
        self.btn_descargar.setEnabled(True)
        self.btn_descargar.setText(
            f"Descargar modelo de voz en español (≈{modelo_voz.TAMANO_APROX_MB} MB)"
        )
        if error:
            QMessageBox.warning(
                self, "No se pudo descargar", f"Revisa tu conexión a internet e inténtalo de nuevo.\n\n{error}"
            )
        else:
            self.modelo_instalado.emit()
        self._actualizar_estado_modelo()

    def _cambiar_salida(self) -> None:
        nombre = self.salida.currentData()
        ajustes.guardar(Clave.SALIDA_VOZ, nombre)
        reproductor().salida = nombre
        self.detener_prueba_microfono()
        # La escucha reproduce la voz por su flujo de audio: reabrirlo con la nueva salida.
        self.escucha_config_cambiada.emit()

    def _cambiar_microfono(self) -> None:
        self.detener_prueba_microfono()
        ajustes.guardar(Clave.MICROFONO, self.microfono.currentData())
        self.escucha_config_cambiada.emit()

    def _alternar_prueba_mic(self, probar: bool) -> None:
        if not probar:
            self.detener_prueba_microfono()
            return
        # La escucha de comandos se pausa para que el eco no dispare nada.
        self.prueba_microfono_cambiada.emit(True)
        try:
            self._prueba_mic.iniciar(self.microfono.currentData() or None, reproductor().salida or None)
        except Exception as error:
            self.prueba_microfono_cambiada.emit(False)
            self.btn_probar_mic.blockSignals(True)
            self.btn_probar_mic.setChecked(False)
            self.btn_probar_mic.blockSignals(False)
            QMessageBox.warning(
                self, "No se pudo probar", f"No se pudo usar el micrófono o los parlantes:\n{error}"
            )
            return
        self.btn_probar_mic.setText("■  Terminar prueba")
        self.btn_probar_mic.setObjectName("Primario")
        self._repolir(self.btn_probar_mic)
        self.nivel_mic.show()
        self.ayuda_prueba.show()
        self._reloj_nivel.start()

    def detener_prueba_microfono(self) -> None:
        """Termina la prueba (si está en curso). También se llama al cambiar
        de vista o cerrar la app."""
        if not self._prueba_mic.activa:
            return
        self._prueba_mic.detener()
        self._reloj_nivel.stop()
        self.nivel_mic.setValue(0)
        self.nivel_mic.hide()
        self.ayuda_prueba.hide()
        self.btn_probar_mic.blockSignals(True)
        self.btn_probar_mic.setChecked(False)
        self.btn_probar_mic.blockSignals(False)
        self.btn_probar_mic.setText("🎙  Probar micrófono")
        self.btn_probar_mic.setObjectName("Secundario")
        self._repolir(self.btn_probar_mic)
        self.prueba_microfono_cambiada.emit(False)

    @staticmethod
    def _repolir(widget: QWidget) -> None:
        """Reaplica la hoja de estilos tras cambiar el objectName."""
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _probar(self) -> None:
        ajustes.guardar(Clave.NOMBRE, self.nombre.text().strip())
        self.probar_saludo.emit()


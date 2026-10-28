"""Vista de rutinas automáticas y su formulario."""

from datetime import time

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.data.models import AccionRutina, Rutina
from app.services import comandos as servicio_comandos
from app.services import rutinas as servicio
from app.services.rutinas import DIAS_CORTOS, DatosRutina
from app.ui.animaciones import aparecer, desvanecer
from app.ui.avisos import Tipo, avisar
from app.ui.widgets import HoraEdit
from app.ui.iconos_menu import poner_icono
from app.ui.widgets import EstadoVacio


def describir_accion(rutina: Rutina) -> str:
    accion = AccionRutina(rutina.accion)
    if accion == AccionRutina.EJECUTAR_COMANDO:
        return f"Ejecutar «{rutina.comando.frase}»" if rutina.comando else "⚠ Su comando fue eliminado"
    return accion.etiqueta


class RutinaDialog(QDialog):
    def __init__(self, rutina: Rutina | None = None, parent=None):
        super().__init__(parent)
        self._id = rutina.id if rutina else None
        self.setWindowTitle("Editar rutina" if rutina else "Nueva rutina")
        self.setMinimumWidth(480)

        self.nombre = QLineEdit()
        self.nombre.setPlaceholderText("Por ejemplo: Inicio de jornada")
        self.nombre.setMaxLength(120)

        self.accion = QComboBox()
        for accion in AccionRutina:
            self.accion.addItem(accion.etiqueta, accion)
        self.accion.currentIndexChanged.connect(self._actualizar_comando)

        self.comando = QComboBox()
        for comando in servicio_comandos.listar():
            self.comando.addItem(comando.frase.capitalize(), comando.id)
        self.sin_comandos = QLabel("Primero crea un comando en «Comandos de voz».")
        self.sin_comandos.setObjectName("Ayuda")

        self.dias: list[QPushButton] = []
        fila_dias = QHBoxLayout()
        fila_dias.setSpacing(4)
        for i, dia in enumerate(DIAS_CORTOS):
            boton = QPushButton(dia)
            boton.setObjectName("Dia")
            boton.setCheckable(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setFixedWidth(46)
            self.dias.append(boton)
            fila_dias.addWidget(boton)
        fila_dias.addStretch()
        atajos = QHBoxLayout()
        atajos.setSpacing(6)
        for texto, dias in (("Lunes a viernes", range(5)), ("Todos los días", range(7)), ("Fines de semana", (5, 6))):
            boton = QPushButton(texto)
            boton.setObjectName("Rapido")
            boton.setAutoDefault(False)
            boton.clicked.connect(lambda _=False, d=tuple(dias): self._marcar_dias(d))
            atajos.addWidget(boton)
        atajos.addStretch()

        self.hora = HoraEdit()
        self.activo = QCheckBox("Rutina activa")
        self.activo.setChecked(True)

        bloque_dias = QVBoxLayout()
        bloque_dias.setSpacing(6)
        bloque_dias.addLayout(fila_dias)
        bloque_dias.addLayout(atajos)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Nombre *", self.nombre)
        form.addRow("Qué hacer", self.accion)
        form.addRow("Comando", self.comando)
        form.addRow("", self.sin_comandos)
        form.addRow("Días", bloque_dias)
        form.addRow("Hora", self.hora)
        form.addRow("", self.activo)
        self._form = form

        ayuda = QLabel(
            "Si la PC estaba apagada a esa hora, la rutina se hace al encenderla, "
            "siempre que no haya pasado más de una hora."
        )
        ayuda.setObjectName("Ayuda")
        ayuda.setWordWrap(True)

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
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(ayuda)
        layout.addWidget(botones)

        if rutina is None:
            self._marcar_dias(range(5))
            self.hora.setHora(QTime(9, 0))
        else:
            self.nombre.setText(rutina.nombre)
            self.accion.setCurrentIndex(self.accion.findData(AccionRutina(rutina.accion)))
            self.comando.setCurrentIndex(max(self.comando.findData(rutina.comando_id), 0))
            self._marcar_dias(servicio.dias_de(rutina))
            hora = servicio.hora_de(rutina)
            self.hora.setHora(QTime(hora.hour, hora.minute))
            self.activo.setChecked(rutina.activo)
        self._actualizar_comando()
        self.nombre.setFocus()

    def _marcar_dias(self, dias) -> None:
        dias = set(dias)
        for i, boton in enumerate(self.dias):
            boton.setChecked(i in dias)

    def _actualizar_comando(self) -> None:
        es_comando = self.accion.currentData() == AccionRutina.EJECUTAR_COMANDO
        hay_comandos = self.comando.count() > 0
        self._form.setRowVisible(self.comando, es_comando and hay_comandos)
        self._form.setRowVisible(self.sin_comandos, es_comando and not hay_comandos)

    def _validar(self) -> None:
        try:
            datos = self.datos()
        except ValueError as error:
            QMessageBox.warning(self, "Revisa la rutina", str(error))
            return
        if not datos.nombre.strip():
            QMessageBox.warning(self, "Falta el nombre", "Ponle un nombre a la rutina.")
            return
        if not datos.dias:
            QMessageBox.warning(self, "Faltan los días", "Elige al menos un día.")
            return
        if datos.accion == AccionRutina.EJECUTAR_COMANDO and datos.comando_id is None:
            QMessageBox.warning(self, "Falta el comando", "Primero crea un comando en «Comandos de voz».")
            return
        self.accept()

    def datos(self) -> DatosRutina:
        hora = self.hora.hora()
        if hora is None:
            raise ValueError("Escribe la hora en formato 24 h, por ejemplo 09:00.")
        return DatosRutina(
            id=self._id,
            nombre=self.nombre.text(),
            accion=self.accion.currentData(),
            dias=[i for i, boton in enumerate(self.dias) if boton.isChecked()],
            hora=time(hora.hour(), hora.minute()),
            comando_id=self.comando.currentData(),
            activo=self.activo.isChecked(),
        )


class RutinaCard(QFrame):
    probar = Signal(int)
    editar = Signal(int)
    eliminar = Signal(int)
    activo_cambiado = Signal(int, bool)

    def __init__(self, rutina: Rutina, parent=None):
        super().__init__(parent)
        self.rutina_id = rutina.id
        self.setObjectName("NotaCard")
        self.setToolTip("Doble clic para editar")

        titulo = QLabel(f"⏰  {rutina.nombre}")
        titulo.setObjectName("NotaTitulo")
        cuando = QLabel(f"{servicio.describir_dias(servicio.dias_de(rutina))} · {rutina.hora}  —  {describir_accion(rutina)}")
        cuando.setObjectName("NotaContenido")

        activo = QCheckBox("Activa")
        activo.setChecked(rutina.activo)
        activo.toggled.connect(lambda v: self.activo_cambiado.emit(self.rutina_id, v))
        probar = QPushButton("Probar")
        probar.setObjectName("Secundario")
        poner_icono(probar, "play", "secundario")
        probar.setCursor(Qt.CursorShape.PointingHandCursor)
        probar.setToolTip("Hacerla ahora, sin esperar la hora")
        probar.clicked.connect(lambda: self.probar.emit(self.rutina_id))

        arriba = QHBoxLayout()
        arriba.setSpacing(10)
        arriba.addWidget(titulo, stretch=1)
        arriba.addWidget(activo)
        arriba.addWidget(probar)
        for texto, senal in (("Editar", self.editar), ("Eliminar", self.eliminar)):
            boton = QPushButton(texto)
            boton.setObjectName("Enlace")
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(lambda _=False, s=senal: s.emit(self.rutina_id))
            arriba.addWidget(boton)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 14)
        layout.setSpacing(6)
        layout.addLayout(arriba)
        layout.addWidget(cuando)
        if not rutina.activo:
            titulo.setProperty("suave", True)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.editar.emit(self.rutina_id)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Probar ahora", lambda: self.probar.emit(self.rutina_id))
        menu.addAction("Editar…", lambda: self.editar.emit(self.rutina_id))
        menu.addSeparator()
        menu.addAction("Eliminar", lambda: self.eliminar.emit(self.rutina_id))
        menu.exec(event.globalPos())


class RutinasView(QWidget):
    probar = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Rutinas")
        titulo.setObjectName("TituloVista")
        subtitulo = QLabel(
            "Cosas que Notivoz hace solo, ciertos días a cierta hora. Por ejemplo: "
            "de lunes a viernes a las 9:00 abrir el modo trabajo, o cada día a las 18:00 leerte el resumen."
        )
        subtitulo.setObjectName("Resumen")
        subtitulo.setWordWrap(True)

        nueva = QPushButton("Nueva rutina")
        nueva.setObjectName("Primario")
        poner_icono(nueva, "mas", "primario")
        nueva.setCursor(Qt.CursorShape.PointingHandCursor)
        nueva.clicked.connect(self.nueva)

        encabezado = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(4)
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        encabezado.addLayout(textos, stretch=1)
        encabezado.addSpacing(16)
        encabezado.addWidget(nueva, alignment=Qt.AlignmentFlag.AlignBottom)

        self._lista = QWidget()
        self._lista.setObjectName("ListaNotas")
        self._layout_lista = QVBoxLayout(self._lista)
        self._layout_lista.setContentsMargins(0, 0, 6, 0)
        self._layout_lista.setSpacing(10)
        scroll = QScrollArea()
        scroll.setObjectName("ScrollNotas")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._lista)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)
        layout.addLayout(encabezado)
        layout.addWidget(scroll, stretch=1)

        self.recargar()

    def recargar(self) -> None:
        while self._layout_lista.count():
            item = self._layout_lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        rutinas = servicio.listar()
        for rutina in rutinas:
            card = RutinaCard(rutina)
            card.probar.connect(self.probar.emit)
            card.editar.connect(self.editar)
            card.eliminar.connect(self.eliminar)
            card.activo_cambiado.connect(self._cambiar_activo)
            self._layout_lista.addWidget(card)
        if not rutinas:
            vacio = EstadoVacio(
                "rutinas",
                "Aún no tienes rutinas\n"
                "Pulsa «Nueva rutina» para que Notivoz haga algo solo, ciertos días a cierta hora.",
            )
            vacio.setMinimumHeight(320)
            self._layout_lista.addWidget(vacio)
        self._layout_lista.addStretch()

    def _tarjeta(self, rutina_id: int) -> RutinaCard | None:
        for i in range(self._layout_lista.count()):
            widget = self._layout_lista.itemAt(i).widget()
            if isinstance(widget, RutinaCard) and widget.rutina_id == rutina_id:
                return widget
        return None

    def _resaltar(self, rutina_id: int) -> None:
        """La tarjeta recién guardada aparece con un fundido."""
        tarjeta = self._tarjeta(rutina_id)
        if tarjeta is not None:
            aparecer(tarjeta, 320)

    def nueva(self) -> None:
        self._abrir_formulario(None)

    def editar(self, rutina_id: int) -> None:
        self._abrir_formulario(rutina_id)

    def _abrir_formulario(self, rutina_id: int | None) -> None:
        rutina = servicio.obtener(rutina_id) if rutina_id is not None else None
        dialogo = RutinaDialog(rutina, self)
        if dialogo.exec():
            try:
                guardado_id = servicio.guardar(dialogo.datos())
            except ValueError as error:
                QMessageBox.warning(self, "No se pudo guardar", str(error))
                return
            self.recargar()
            self._resaltar(guardado_id)
            avisar(f"Rutina {'actualizada' if rutina_id is not None else 'creada'}")

    def _cambiar_activo(self, rutina_id: int, activo: bool) -> None:
        servicio.cambiar_activo(rutina_id, activo)
        self.recargar()

    def eliminar(self, rutina_id: int) -> None:
        rutina = servicio.obtener(rutina_id)
        if rutina is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Eliminar rutina",
            f"¿Eliminar la rutina «{rutina.nombre}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            def borrar() -> None:
                servicio.eliminar(rutina_id)
                self.recargar()
                avisar("Rutina eliminada", Tipo.ELIMINADO)

            tarjeta = self._tarjeta(rutina_id)
            if tarjeta is None:
                borrar()
            else:
                desvanecer(tarjeta, borrar)

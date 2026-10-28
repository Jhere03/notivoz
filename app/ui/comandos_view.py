"""Vista de comandos de voz: tarjetas con la frase y las apps que abre."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.data.models import Comando
from app.services import ajustes
from app.services import comandos as servicio
from app.services.escucha import NOMBRE_ACTIVACION
from app.ui.animaciones import aparecer, desvanecer
from app.ui.avisos import Tipo, avisar
from app.ui.comando_dialog import ComandoDialog, icono_de
from app.ui.iconos_menu import poner_icono
from app.ui.widgets import EstadoVacio

_MAX_CHIPS = 6


class ComandoCard(QFrame):
    ejecutar = Signal(int)
    cerrar = Signal(int)
    editar = Signal(int)
    eliminar = Signal(int)
    activo_cambiado = Signal(int, bool)

    def __init__(self, comando: Comando, parent=None):
        super().__init__(parent)
        self.comando_id = comando.id
        self.setObjectName("NotaCard")
        self.setToolTip("Doble clic para editar")

        frase = QLabel(f"«{NOMBRE_ACTIVACION}, {comando.frase}»")
        frase.setObjectName("NotaTitulo")

        activo = QCheckBox("Activo")
        activo.setChecked(comando.activo)
        activo.toggled.connect(lambda v: self.activo_cambiado.emit(self.comando_id, v))

        ejecutar = QPushButton("Ejecutar")
        ejecutar.setObjectName("Secundario")
        poner_icono(ejecutar, "play", "secundario")
        ejecutar.setCursor(Qt.CursorShape.PointingHandCursor)
        ejecutar.setToolTip("Abrir ahora todas sus aplicaciones")
        ejecutar.clicked.connect(lambda: self.ejecutar.emit(self.comando_id))
        cerrar = QPushButton("Cerrar")
        poner_icono(cerrar, "stop")
        cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        cerrar.setToolTip(
            "Cierra las aplicaciones que abrió este comando (como al pulsar la X). "
            f"También puedes decir «{NOMBRE_ACTIVACION}, cierra {comando.frase}»."
        )
        cerrar.clicked.connect(lambda: self.cerrar.emit(self.comando_id))

        arriba = QHBoxLayout()
        arriba.setSpacing(10)
        arriba.addWidget(frase, stretch=1)
        arriba.addWidget(activo)
        arriba.addWidget(ejecutar)
        arriba.addWidget(cerrar)
        for texto, senal in (("Editar", self.editar), ("Eliminar", self.eliminar)):
            boton = QPushButton(texto)
            boton.setObjectName("Enlace")
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.clicked.connect(lambda _=False, s=senal: s.emit(self.comando_id))
            arriba.addWidget(boton)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        for app in comando.apps[:_MAX_CHIPS]:
            chip = QLabel(app.nombre)
            chip.setObjectName("ChipApp")
            chip.setToolTip(app.destino)
            icono = QLabel()
            icono.setPixmap(icono_de(app.destino).pixmap(16, 16))
            icono.setObjectName("ChipIcono")
            chips.addWidget(icono)
            chips.addWidget(chip)
            chips.addSpacing(6)
        if len(comando.apps) > _MAX_CHIPS:
            mas = QLabel(f"+{len(comando.apps) - _MAX_CHIPS} más")
            mas.setObjectName("Ayuda")
            chips.addWidget(mas)
        chips.addStretch()

        if comando.respuesta.strip():
            texto_respuesta = f"Responde: «{comando.respuesta.strip()}»"
        else:
            ejemplo = servicio.respuesta_de(comando, ajustes.frases_actuales())
            texto_respuesta = f"Responde según tu personalidad, por ejemplo: «{ejemplo}»"
        respuesta = QLabel(texto_respuesta)
        respuesta.setObjectName("NotaContenido")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 14)
        layout.setSpacing(8)
        layout.addLayout(arriba)
        layout.addLayout(chips)
        layout.addWidget(respuesta)
        if not comando.activo:
            self.setProperty("inactivo", True)
            frase.setProperty("suave", True)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.editar.emit(self.comando_id)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        menu.addAction("Ejecutar ahora", lambda: self.ejecutar.emit(self.comando_id))
        menu.addAction("Editar…", lambda: self.editar.emit(self.comando_id))
        menu.addSeparator()
        menu.addAction("Eliminar", lambda: self.eliminar.emit(self.comando_id))
        menu.exec(event.globalPos())


class ComandosView(QWidget):
    # La ventana principal enciende o apaga el micrófono y recarga las frases.
    escucha_pedida = Signal(bool)
    comandos_cambiaron = Signal()
    ejecutar = Signal(int)
    cerrar = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        titulo = QLabel("Comandos de voz")
        titulo.setObjectName("TituloVista")
        self.estado = QLabel()
        self.estado.setObjectName("Resumen")

        self.btn_escucha = QPushButton()
        self.btn_escucha.setCheckable(True)
        self.btn_escucha.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_escucha.toggled.connect(self._al_cambiar_escucha)

        self.btn_nuevo = QPushButton("Nuevo comando")
        self.btn_nuevo.setObjectName("Primario")
        poner_icono(self.btn_nuevo, "mas", "primario")
        self.btn_nuevo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_nuevo.clicked.connect(self.nuevo)

        encabezado = QHBoxLayout()
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo)
        textos.addWidget(self.estado)
        encabezado.addLayout(textos)
        encabezado.addStretch()
        encabezado.addWidget(self.btn_escucha, alignment=Qt.AlignmentFlag.AlignBottom)
        encabezado.addSpacing(8)
        encabezado.addWidget(self.btn_nuevo, alignment=Qt.AlignmentFlag.AlignBottom)

        ayuda = QLabel(
            f"Di «{NOMBRE_ACTIVACION}» y luego la frase, por ejemplo «{NOMBRE_ACTIVACION}, modo trabajo». "
            f"También puedes decir solo «{NOMBRE_ACTIVACION}», esperar el pitido y decir la frase. "
            "Cuando todas las aplicaciones estén abiertas, Notivoz te lo dirá. "
            f"Para cerrarlas di «{NOMBRE_ACTIVACION}, cierra modo relax» o usa el botón «Cerrar»."
        )
        ayuda.setObjectName("Ayuda")
        ayuda.setWordWrap(True)

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
        layout.setSpacing(14)
        layout.addLayout(encabezado)
        layout.addWidget(ayuda)
        layout.addWidget(scroll, stretch=1)

        self.set_estado_escucha("Micrófono apagado", False)
        self.recargar()

    def set_estado_escucha(self, texto: str, escuchando: bool) -> None:
        self.estado.setText(texto)
        self.btn_escucha.blockSignals(True)
        self.btn_escucha.setChecked(escuchando)
        self.btn_escucha.blockSignals(False)
        self.btn_escucha.setText("Escuchando" if escuchando else "Activar micrófono")
        self.btn_escucha.setObjectName("Primario" if escuchando else "Secundario")
        poner_icono(self.btn_escucha, "microfono", "primario" if escuchando else "secundario")
        # Reaplicar el estilo tras cambiar el objectName.
        self.btn_escucha.style().unpolish(self.btn_escucha)
        self.btn_escucha.style().polish(self.btn_escucha)

    def _al_cambiar_escucha(self, activar: bool) -> None:
        self.set_estado_escucha("Iniciando…" if activar else "Micrófono apagado", False)
        self.escucha_pedida.emit(activar)

    def recargar(self) -> None:
        while self._layout_lista.count():
            item = self._layout_lista.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

        comandos = servicio.listar()
        for comando in comandos:
            card = ComandoCard(comando)
            card.ejecutar.connect(self.ejecutar.emit)
            card.cerrar.connect(self.cerrar.emit)
            card.editar.connect(self.editar)
            card.eliminar.connect(self.eliminar)
            card.activo_cambiado.connect(self._cambiar_activo)
            self._layout_lista.addWidget(card)

        if not comandos:
            vacio = EstadoVacio(
                "comandos",
                "Aún no tienes comandos\n"
                "Pulsa «Nuevo comando» y crea, por ejemplo, «modo trabajo» con Opera GX, Steam y Spotify.",
            )
            vacio.setMinimumHeight(320)
            self._layout_lista.addWidget(vacio)
        self._layout_lista.addStretch()

    def _avisar_cambio(self) -> None:
        self.recargar()
        self.comandos_cambiaron.emit()

    def _tarjeta(self, comando_id: int) -> ComandoCard | None:
        for i in range(self._layout_lista.count()):
            widget = self._layout_lista.itemAt(i).widget()
            if isinstance(widget, ComandoCard) and widget.comando_id == comando_id:
                return widget
        return None

    def _resaltar(self, comando_id: int) -> None:
        """La tarjeta recién guardada aparece con un fundido."""
        tarjeta = self._tarjeta(comando_id)
        if tarjeta is not None:
            aparecer(tarjeta, 320)

    def nuevo(self) -> None:
        self._abrir_formulario(None)

    def editar(self, comando_id: int) -> None:
        self._abrir_formulario(comando_id)

    def _abrir_formulario(self, comando_id: int | None) -> None:
        comando = servicio.obtener(comando_id) if comando_id is not None else None
        dialogo = ComandoDialog(comando, self)
        if dialogo.exec():
            try:
                guardado_id = servicio.guardar(dialogo.datos())
            except ValueError as error:
                QMessageBox.warning(self, "No se pudo guardar", str(error))
                return
            self._avisar_cambio()
            self._resaltar(guardado_id)
            avisar(f"Comando {'actualizado' if comando_id is not None else 'creado'}")

    def _cambiar_activo(self, comando_id: int, activo: bool) -> None:
        servicio.cambiar_activo(comando_id, activo)
        self._avisar_cambio()

    def eliminar(self, comando_id: int) -> None:
        comando = servicio.obtener(comando_id)
        if comando is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Eliminar comando",
            f"¿Eliminar el comando «{comando.frase}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            def borrar() -> None:
                servicio.eliminar(comando_id)
                self._avisar_cambio()
                avisar("Comando eliminado", Tipo.ELIMINADO)

            tarjeta = self._tarjeta(comando_id)
            if tarjeta is None:
                borrar()
            else:
                desvanecer(tarjeta, borrar)

"""Paletas de colores (oscuro, claro y translúcido) y hoja de estilos (QSS).

El tema activo se cambia con `aplicar(nombre)`. Las constantes de este módulo
(FONDO, TEXTO, ACENTO…) siempre reflejan el tema activo; quien pinte a mano
debe leerlas en el momento de pintar (`theme.TEXTO`), no copiarlas al importar.
"""

from types import SimpleNamespace

from app.data.models import Estado, Importancia

OSCURO = "oscuro"
CLARO = "claro"
TRANSLUCIDO = "translucido"
TEMAS = {OSCURO: "Oscuro", CLARO: "Claro", TRANSLUCIDO: "Translúcido"}

# Componentes RGB del acento, para los rgba() de insignias y resaltados.
_ACENTO_RGB = "124, 92, 255"

_OSCURO = {
    # Colores que también se usan al pintar a mano (siempre opacos).
    "fondo": "#14161b",
    "superficie": "#1c1f26",
    "superficie_alta": "#242832",
    "borde": "#2d323d",
    "texto": "#e6e8ec",
    "texto_suave": "#8b93a1",
    "acento": "#7c5cff",
    "acento_hover": "#8f74ff",
    # Solo para la hoja de estilos.
    "fondo_widget": "#14161b",  # fondo general de cualquier widget
    "lateral": "#1c1f26",  # menú de la izquierda
    "fondo_ventana": "",        # fondo de ventanas y diálogos (solo translúcido)
    "boton": "#242832",
    "acento_pulsado": "#6a4af0",
    "alterna": "#1f232b",
    "seleccion": "#2e2a4d",
    "fila_hover": f"rgba({_ACENTO_RGB}, 0.07)",
    "secundario": "white",
    "secundario_hover": "#ece7ff",
    "secundario_texto": "#7c5cff",
    "deshabilitado": "#4b5160",
    "dia_bloqueado": "#2b2840",
    "nota_hover": "#4a4470",
    "nota_contenido": "#b9bfca",
    "alerta_contenido": "#c4c9d3",
    "hover_sutil": "rgba(255, 255, 255, 0.08)",
    "racha_texto": "#fbbf24",
    "perilla": "white",
    "barra": "#2d323d",
    "aviso": "#242832",
    # Menús, listas desplegables, calendario y alertas: son ventanas aparte
    # sin efecto acrílico, así que siempre opacas.
    "emergente": "#242832",
    "emergente_base": "#1c1f26",
}

_CLARO = {
    "fondo": "#f3f4f7",
    "superficie": "#ffffff",
    "superficie_alta": "#eceef3",
    "borde": "#dcdfe6",
    "texto": "#1c1f26",
    "texto_suave": "#6b7280",
    "acento": "#7c5cff",
    "acento_hover": "#6b4cf0",
    "fondo_widget": "#f3f4f7",
    "lateral": "#ffffff",
    "fondo_ventana": "",
    "boton": "#ffffff",
    "acento_pulsado": "#5a3bdc",
    "alterna": "#f8f9fb",
    "seleccion": "#e8e2ff",
    "fila_hover": f"rgba({_ACENTO_RGB}, 0.06)",
    # Los botones blancos del tema oscuro pasan a ser negros.
    "secundario": "#1c1f26",
    "secundario_hover": "#343842",
    "secundario_texto": "white",
    "deshabilitado": "#b0b6c1",
    "dia_bloqueado": "#e6e0ff",
    "nota_hover": "#c4b5ff",
    "nota_contenido": "#4b5262",
    "alerta_contenido": "#3f4553",
    "hover_sutil": "rgba(0, 0, 0, 0.06)",
    "racha_texto": "#b45309",
    "perilla": "#7c5cff",
    "barra": "#c5cad3",
    "aviso": "#1c1f26",
    "emergente": "#ffffff",
    "emergente_base": "#ffffff",
}

# Igual que el oscuro, pero con fondos semitransparentes sobre el acrílico de Windows.
_TRANSLUCIDO = {
    **_OSCURO,
    "fondo_widget": "transparent",
    # El menú deja ver el acrílico, apenas aclarado para separarlo del contenido.
    "lateral": "rgba(255, 255, 255, 0.04)",
    "fondo_ventana": "rgba(14, 16, 21, 0.58)",
    "superficie_css": "rgba(28, 31, 39, 0.55)",
    "superficie_alta_css": "rgba(46, 50, 61, 0.70)",
    "borde_css": "rgba(255, 255, 255, 0.10)",
    "boton": "rgba(46, 50, 61, 0.70)",
    "alterna": "rgba(255, 255, 255, 0.025)",
    "seleccion": f"rgba({_ACENTO_RGB}, 0.30)",
    "barra": "rgba(255, 255, 255, 0.18)",
    "dia_bloqueado": f"rgba({_ACENTO_RGB}, 0.18)",
}

_PALETAS = {OSCURO: _OSCURO, CLARO: _CLARO, TRANSLUCIDO: _TRANSLUCIDO}

_COLORES_ESTADO = {
    OSCURO: {
        Estado.PENDIENTE: "#3d8bfd",   # azul
        Estado.EN_PROCESO: "#f59e0b",  # naranja
        Estado.REALIZADO: "#2dd4bf",   # celeste turquesa
    },
    # Más intensos para que se lean sobre blanco.
    CLARO: {
        Estado.PENDIENTE: "#2563eb",
        Estado.EN_PROCESO: "#d97706",
        Estado.REALIZADO: "#0d9488",
    },
}
_COLORES_IMPORTANCIA = {
    OSCURO: {
        Importancia.BAJA.etiqueta: "#4caf87",
        Importancia.MEDIA.etiqueta: "#3d8bfd",
        Importancia.ALTA.etiqueta: "#f0a43a",
        Importancia.CRITICA.etiqueta: "#ef5350",
    },
    CLARO: {
        Importancia.BAJA.etiqueta: "#15803d",
        Importancia.MEDIA.etiqueta: "#2563eb",
        Importancia.ALTA.etiqueta: "#d97706",
        Importancia.CRITICA.etiqueta: "#dc2626",
    },
}

# Se rellenan con el tema activo en `_activar`.
tema_actual = OSCURO
FONDO = SUPERFICIE = SUPERFICIE_ALTA = BORDE = ""
TEXTO = TEXTO_SUAVE = ACENTO = ACENTO_HOVER = ""
# Diccionarios que se actualizan en el sitio: las referencias guardadas siguen valiendo.
COLOR_ESTADO: dict = {}
COLOR_IMPORTANCIA: dict = {}
QSS = ""


def construir_qss(nombre: str) -> str:
    p = dict(_PALETAS[nombre])
    # Los tokens *_css permiten que el translúcido use rgba() en la hoja de
    # estilos mientras las constantes de Python siguen siendo colores opacos.
    for clave in ("superficie", "superficie_alta", "borde"):
        p[clave] = p.get(f"{clave}_css", p[clave])
    c = SimpleNamespace(**p)
    ventana = (
        f"""
QMainWindow {{
    background: {c.fondo_ventana};
}}
/* Los diálogos se crean antes de poder hacerlos transparentes: si se les pone
   un fondo semitransparente, al repintar quedan "fantasmas". Van sólidos. */
QDialog {{
    background: {c.fondo};
}}
QComboBoxPrivateContainer {{
    background: {c.emergente};
}}"""
        if c.fondo_ventana
        else ""
    )
    return f"""
QWidget {{
    background: {c.fondo_widget};
    color: {c.texto};
    font-family: "Segoe UI";
    font-size: 10pt;
}}{ventana}
QToolTip {{
    background: {c.emergente};
    color: {c.texto};
    border: 1px solid {c.borde};
    padding: 4px 6px;
}}

/* Barra lateral */
#Sidebar {{
    background: {c.lateral};
    border-right: 1px solid {c.borde};
}}
#Logo {{
    background: transparent;
    font-size: 17pt;
    font-weight: 700;
    color: {c.texto};
    padding: 18px 18px 2px 18px;
}}
#Lema {{
    background: transparent;
    color: {c.texto_suave};
    font-size: 9pt;
    padding: 0 18px 14px 18px;
}}
#Nav {{
    background: transparent;
    border: none;
    outline: none;
    font-weight: bold;
}}
#Nav::item {{
    padding: 10px 12px;
    margin: 2px 10px;
    border-radius: 8px;
    color: {c.texto_suave};
}}
#Nav::item:hover {{
    background: {c.superficie_alta};
    color: {c.texto};
    /* Igual que los botones: crece un poco al pasar el cursor. */
    margin: 0px 8px;
}}
#Nav::item:selected {{
    background: {c.acento};
    color: white;
}}
#Version {{
    background: transparent;
    color: {c.texto_suave};
    font-size: 8pt;
    padding: 12px 18px;
}}

/* Encabezados */
#TituloVista {{
    font-size: 18pt;
    font-weight: 600;
}}
#Resumen, #Vacio, #Proximamente, QLabel[suave="true"] {{
    color: {c.texto_suave};
}}
#Vacio, #Proximamente {{
    font-size: 11pt;
}}

/* Controles */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {c.superficie};
    border: 1px solid {c.borde};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {c.acento};
    selection-color: white;
}}
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover {{
    border-color: {c.texto_suave};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {c.acento};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {c.emergente};
    border: 1px solid {c.borde};
    selection-background-color: {c.acento};
    selection-color: white;
    outline: none;
}}
QPushButton {{
    background: {c.boton};
    border: 1px solid {c.borde};
    border-radius: 6px;
    padding: 7px 14px;
    /* Espacio reservado para "crecer" al pasar el cursor sin mover nada alrededor. */
    margin: 2px;
}}
QPushButton:hover {{
    border-color: {c.texto_suave};
}}
/* Todos los botones se agrandan al pasar el cursor: el fondo ocupa el margen reservado. */
QPushButton:hover:!disabled {{
    margin: 0px;
}}
/* …y se "hunden" al pulsarlos. */
QPushButton:pressed:!disabled {{
    margin: 3px;
    border-color: {c.acento};
}}
QPushButton:focus {{
    outline: none;
}}
QPushButton#Primario {{
    background: {c.acento};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#Primario:hover {{
    background: {c.acento_hover};
}}
QPushButton#Primario:pressed {{
    background: {c.acento_pulsado};
}}
QPushButton#Secundario {{
    background: {c.secundario};
    border: none;
    color: {c.secundario_texto};
    font-weight: 600;
}}
QPushButton#Secundario:hover {{
    background: {c.secundario_hover};
}}
QPushButton:disabled {{
    color: {c.texto_suave};
    background: {c.superficie};
}}

/* Tabla */
QTableView {{
    background: {c.superficie};
    alternate-background-color: {c.alterna};
    border: 1px solid {c.borde};
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: {c.seleccion};
    selection-color: {c.texto};
    outline: none;
}}
QTableView::item {{
    padding: 0 8px;
    border-bottom: 1px solid {c.borde};
}}
QTableView::item:hover {{
    background: {c.fila_hover};
}}
QTableView::item:selected {{
    background: {c.seleccion};
}}
QHeaderView {{
    background: transparent;
}}
QHeaderView::section {{
    background: {c.superficie};
    color: {c.texto_suave};
    border: none;
    border-bottom: 1px solid {c.borde};
    padding: 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {c.superficie};
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c.barra};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c.texto_suave};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}

QPushButton#Rapido {{
    background: transparent;
    border: 1px solid {c.borde};
    border-radius: 12px;
    padding: 3px 10px;
    color: {c.texto_suave};
    font-size: 9pt;
}}
QPushButton#Rapido:hover {{
    border-color: {c.acento};
    color: {c.texto};
}}
QPushButton#Dia {{
    background: {c.superficie};
    border: 1px solid {c.borde};
    border-radius: 6px;
    padding: 6px 0;
    color: {c.texto_suave};
}}
QPushButton#Dia:checked {{
    background: {c.acento};
    border-color: {c.acento};
    color: white;
    font-weight: 600;
}}
QPushButton#Dia:disabled, QPushButton#Dia:checked:disabled {{
    background: {c.superficie};
    border-color: {c.borde};
    color: {c.deshabilitado};
}}
QPushButton#Dia:checked:disabled {{
    background: {c.dia_bloqueado};
    color: {c.texto_suave};
}}
QListWidget:disabled, QLabel:disabled, QLineEdit:disabled {{
    color: {c.deshabilitado};
}}
QPushButton#Enlace {{
    background: transparent;
    border: none;
    padding: 2px 6px;
    color: {c.texto_suave};
    font-size: 9pt;
}}
QPushButton#Enlace:hover {{
    color: {c.acento_hover};
    background: rgba({_ACENTO_RGB}, 0.14);
    border-radius: 6px;
}}
QPushButton::menu-indicator {{
    image: none;
    width: 0;
}}

QCheckBox {{
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c.texto_suave};
    border-radius: 4px;
    background: {c.superficie};
}}
QCheckBox::indicator:hover {{
    border-color: {c.acento};
}}
QCheckBox::indicator:checked {{
    background: {c.acento};
    border-color: {c.acento};
}}
QLineEdit:disabled {{
    color: {c.texto_suave};
}}

/* Notas */
#ScrollNotas, #ListaNotas {{
    background: transparent;
}}
#NotaCard {{
    background: {c.superficie};
    border: 1px solid {c.borde};
    border-radius: 10px;
}}
#NotaCard:hover {{
    border-color: {c.nota_hover};
}}
#NotaCard QLabel {{
    background: transparent;
}}
#NotaTitulo {{
    font-size: 11pt;
    font-weight: 600;
}}
#NotaContenido {{
    color: {c.nota_contenido};
}}
#BadgeProximo, #BadgeAvisado, #BadgeCreada {{
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 9pt;
}}
#BadgeProximo {{
    background: rgba({_ACENTO_RGB}, 0.18);
    border: 1px solid rgba({_ACENTO_RGB}, 0.6);
    color: {c.acento_hover};
}}
#BadgeAvisado, #BadgeCreada {{
    background: transparent;
    border: 1px solid {c.borde};
    color: {c.texto_suave};
}}

/* Alerta de recordatorio */
#Alerta {{
    background: {c.emergente};
    border: 2px solid {c.acento};
    border-radius: 12px;
}}
#Alerta QLabel {{
    background: transparent;
}}
#AlertaEtiqueta {{
    color: {c.acento_hover};
    font-size: 8.5pt;
    font-weight: 700;
}}
#AlertaTitulo {{
    font-size: 14pt;
    font-weight: 600;
}}
#AlertaContenido {{
    color: {c.alerta_contenido};
}}
QPushButton#AlertaCerrar {{
    background: transparent;
    border: none;
    color: {c.texto_suave};
    padding: 0 4px;
}}
QPushButton#AlertaCerrar:hover {{
    color: {c.texto};
    background: {c.hover_sutil};
    border-radius: 6px;
}}

#Racha {{
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.45);
    border-radius: 8px;
    color: {c.racha_texto};
    padding: 6px 12px;
    font-weight: 600;
}}

/* Avisos flotantes ("Tarea guardada", "Nota eliminada"…) */
#Aviso {{
    background: {c.aviso};
    border: 1px solid rgba({_ACENTO_RGB}, 0.55);
    border-radius: 10px;
}}
#Aviso QLabel {{
    background: transparent;
    color: white;
}}
#MensajeUsuario {{
    background: {c.acento};
    color: white;
    border-radius: 12px;
    padding: 8px 12px;
}}
#MensajeNotivoz {{
    background: {c.superficie_alta};
    border: 1px solid {c.borde};
    border-radius: 12px;
    padding: 8px 12px;
}}
#MensajeError {{
    background: rgba(239, 83, 80, 0.12);
    border: 1px solid rgba(239, 83, 80, 0.5);
    border-radius: 12px;
    padding: 8px 12px;
}}
#Escribiendo {{
    color: {c.texto_suave};
    font-style: italic;
}}
QPushButton#AvisoAccion {{
    background: transparent;
    border: none;
    color: {c.acento_hover};
    font-weight: 700;
    padding: 2px 6px;
    margin: 0;
}}
QPushButton#AvisoAccion:hover {{
    color: white;
}}
#AvisoIcono {{
    font-size: 11pt;
    font-weight: 700;
}}

/* Comandos */
#ChipApp {{
    background: {c.superficie_alta};
    border: 1px solid {c.borde};
    border-radius: 10px;
    padding: 2px 9px;
    font-size: 9pt;
}}
#ChipIcono {{
    background: transparent;
}}
QPushButton#IndicadorEnfoque {{
    background: rgba({_ACENTO_RGB}, 0.16);
    border: 1px solid rgba({_ACENTO_RGB}, 0.55);
    border-radius: 8px;
    color: {c.acento_hover};
    font-weight: 600;
    text-align: left;
    padding: 7px 10px;
    margin: 8px 12px 2px 12px;
}}
QPushButton#IndicadorEnfoque:hover {{
    background: rgba({_ACENTO_RGB}, 0.28);
    margin: 6px 10px 0 10px;
}}
#EstadoEscucha {{
    background: transparent;
    color: {c.texto_suave};
    font-size: 9pt;
    padding: 8px 18px 0 18px;
}}
QProgressBar {{
    background: {c.superficie_alta};
    border: 1px solid {c.borde};
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {c.acento};
    border-radius: 4px;
}}
QListWidget {{
    background: {c.superficie};
    border: 1px solid {c.borde};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px;
}}
QListWidget::item:selected {{
    background: {c.seleccion};
    color: {c.texto};
}}

/* Configuración */
#Seccion {{
    background: {c.superficie};
    border: 1px solid {c.borde};
    border-radius: 10px;
}}
#Seccion QLabel, #Seccion QCheckBox, #Fila {{
    background: transparent;
}}
#SeccionTitulo {{
    font-size: 12pt;
    font-weight: 600;
}}
#Ayuda {{
    color: {c.texto_suave};
    font-size: 9pt;
}}
QToolButton#OpcionTema {{
    background: {c.superficie};
    border: 2px solid {c.borde};
    border-radius: 10px;
    padding: 10px 10px 8px 10px;
    font-weight: 600;
}}
QToolButton#OpcionTema:hover {{
    border-color: {c.texto_suave};
}}
QToolButton#OpcionTema:disabled {{
    color: {c.deshabilitado};
}}
QToolButton#OpcionTema:checked {{
    border-color: {c.acento};
    background: rgba({_ACENTO_RGB}, 0.12);
}}
QSlider {{
    background: transparent;
    min-height: 22px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {c.barra};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {c.acento};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {c.perilla};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

/* Calendario */
#CalendarioPopup {{
    background: {c.emergente};
    border: 1px solid {c.borde};
    border-radius: 8px;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {c.emergente};
    padding: 4px;
}}
QCalendarWidget QToolButton {{
    background: transparent;
    color: {c.texto};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background: {c.hover_sutil};
}}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {{
    font-size: 15pt;
    padding: 0 10px;
}}
QCalendarWidget QToolButton::menu-indicator {{
    image: none;
}}
QCalendarWidget QSpinBox {{
    background: {c.emergente_base};
    border: 1px solid {c.borde};
    border-radius: 4px;
    padding: 2px 4px;
}}
QCalendarWidget QAbstractItemView {{
    background: {c.emergente_base};
    color: {c.texto};
    selection-background-color: {c.acento};
    selection-color: white;
    outline: none;
    border: none;
}}
QCalendarWidget QTableView::item {{
    padding: 0;
    border: none;
}}
QCalendarWidget QTableView::item:hover {{
    background: rgba({_ACENTO_RGB}, 0.18);
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: {c.deshabilitado};
}}

QMenu {{
    background: {c.emergente};
    border: 1px solid {c.borde};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {c.acento};
    color: white;
}}
QMenu::separator {{
    height: 1px;
    background: {c.borde};
    margin: 4px 6px;
}}

QStatusBar {{
    background: {c.superficie};
    color: {c.texto_suave};
    border-top: 1px solid {c.borde};
}}
"""


def _activar(nombre: str) -> None:
    """Pone las constantes del módulo con los valores del tema `nombre`."""
    global tema_actual, FONDO, SUPERFICIE, SUPERFICIE_ALTA, BORDE
    global TEXTO, TEXTO_SUAVE, ACENTO, ACENTO_HOVER, QSS
    if nombre not in _PALETAS:
        nombre = OSCURO
    p = _PALETAS[nombre]
    tema_actual = nombre
    FONDO, SUPERFICIE, SUPERFICIE_ALTA, BORDE = (
        p["fondo"], p["superficie"], p["superficie_alta"], p["borde"]
    )
    TEXTO, TEXTO_SUAVE, ACENTO, ACENTO_HOVER = (
        p["texto"], p["texto_suave"], p["acento"], p["acento_hover"]
    )
    variante = CLARO if nombre == CLARO else OSCURO
    COLOR_ESTADO.clear()
    COLOR_ESTADO.update(_COLORES_ESTADO[variante])
    COLOR_IMPORTANCIA.clear()
    COLOR_IMPORTANCIA.update(_COLORES_IMPORTANCIA[variante])
    QSS = construir_qss(nombre)


def paleta(nombre: str) -> dict[str, str]:
    """Colores de un tema (para dibujar, por ejemplo, su miniatura)."""
    return dict(_PALETAS.get(nombre, _OSCURO))


def es_oscuro() -> bool:
    return tema_actual != CLARO


_activar(OSCURO)

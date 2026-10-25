"""Paleta de colores y hoja de estilos (QSS) de la aplicación."""

from app.data.models import Estado, Importancia

FONDO = "#14161b"
SUPERFICIE = "#1c1f26"
SUPERFICIE_ALTA = "#242832"
BORDE = "#2d323d"
TEXTO = "#e6e8ec"
TEXTO_SUAVE = "#8b93a1"
ACENTO = "#7c5cff"
ACENTO_HOVER = "#8f74ff"

COLOR_IMPORTANCIA = {
    Importancia.BAJA.etiqueta: "#4caf87",
    Importancia.MEDIA.etiqueta: "#3d8bfd",
    Importancia.ALTA.etiqueta: "#f0a43a",
    Importancia.CRITICA.etiqueta: "#ef5350",
}

COLOR_ESTADO = {
    Estado.PENDIENTE: "#3d8bfd",   # azul
    Estado.EN_PROCESO: "#f59e0b",  # naranja
    Estado.REALIZADO: "#2dd4bf",   # celeste turquesa
}

QSS = f"""
QWidget {{
    background: {FONDO};
    color: {TEXTO};
    font-family: "Segoe UI";
    font-size: 10pt;
}}
QToolTip {{
    background: {SUPERFICIE_ALTA};
    color: {TEXTO};
    border: 1px solid {BORDE};
    padding: 4px 6px;
}}

/* Barra lateral */
#Sidebar {{
    background: {SUPERFICIE};
    border-right: 1px solid {BORDE};
}}
#Logo {{
    background: transparent;
    font-size: 17pt;
    font-weight: 700;
    color: {TEXTO};
    padding: 18px 18px 2px 18px;
}}
#Lema {{
    background: transparent;
    color: {TEXTO_SUAVE};
    font-size: 9pt;
    padding: 0 18px 14px 18px;
}}
#Nav {{
    background: transparent;
    border: none;
    outline: none;
}}
#Nav::item {{
    padding: 10px 14px;
    margin: 2px 10px;
    border-radius: 8px;
    color: {TEXTO_SUAVE};
}}
#Nav::item:hover {{
    background: {SUPERFICIE_ALTA};
    color: {TEXTO};
}}
#Nav::item:selected {{
    background: {ACENTO};
    color: white;
}}
#Version {{
    background: transparent;
    color: {TEXTO_SUAVE};
    font-size: 8pt;
    padding: 12px 18px;
}}

/* Encabezados */
#TituloVista {{
    font-size: 18pt;
    font-weight: 600;
}}
#Resumen, #Vacio, #Proximamente {{
    color: {TEXTO_SUAVE};
}}
#Vacio, #Proximamente {{
    font-size: 11pt;
}}

/* Controles */
QLineEdit, QPlainTextEdit, QComboBox {{
    background: {SUPERFICIE};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {ACENTO};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border-color: {ACENTO};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    selection-background-color: {ACENTO};
    outline: none;
}}
QPushButton {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    border-radius: 6px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    border-color: {TEXTO_SUAVE};
}}
QPushButton#Primario {{
    background: {ACENTO};
    border: none;
    color: white;
    font-weight: 600;
}}
QPushButton#Primario:hover {{
    background: {ACENTO_HOVER};
}}
QPushButton#Secundario {{
    background: white;
    border: none;
    color: {ACENTO};
    font-weight: 600;
}}
QPushButton#Secundario:hover {{
    background: #ece7ff;
}}
QPushButton:disabled {{
    color: {TEXTO_SUAVE};
    background: {SUPERFICIE};
}}

/* Tabla */
QTableView {{
    background: {SUPERFICIE};
    alternate-background-color: #1f232b;
    border: 1px solid {BORDE};
    border-radius: 8px;
    gridline-color: transparent;
    selection-background-color: #2e2a4d;
    selection-color: {TEXTO};
    outline: none;
}}
QTableView::item {{
    padding: 0 8px;
    border-bottom: 1px solid {BORDE};
}}
QHeaderView::section {{
    background: {SUPERFICIE};
    color: {TEXTO_SUAVE};
    border: none;
    border-bottom: 1px solid {BORDE};
    padding: 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {SUPERFICIE};
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {BORDE};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
}}

QPushButton#Rapido {{
    background: transparent;
    border: 1px solid {BORDE};
    border-radius: 12px;
    padding: 3px 10px;
    color: {TEXTO_SUAVE};
    font-size: 9pt;
}}
QPushButton#Rapido:hover {{
    border-color: {ACENTO};
    color: {TEXTO};
}}
QPushButton#Enlace {{
    background: transparent;
    border: none;
    padding: 2px 6px;
    color: {TEXTO_SUAVE};
    font-size: 9pt;
}}
QPushButton#Enlace:hover {{
    color: {ACENTO_HOVER};
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
    border: 1px solid {TEXTO_SUAVE};
    border-radius: 4px;
    background: {SUPERFICIE};
}}
QCheckBox::indicator:checked {{
    background: {ACENTO};
    border-color: {ACENTO};
}}
QLineEdit:disabled {{
    color: {TEXTO_SUAVE};
}}

/* Notas */
#ScrollNotas, #ListaNotas {{
    background: transparent;
}}
#NotaCard {{
    background: {SUPERFICIE};
    border: 1px solid {BORDE};
    border-radius: 10px;
}}
#NotaCard:hover {{
    border-color: #4a4470;
}}
#NotaCard QLabel {{
    background: transparent;
}}
#NotaTitulo {{
    font-size: 11pt;
    font-weight: 600;
}}
#NotaContenido {{
    color: #b9bfca;
}}
#BadgeProximo, #BadgeAvisado, #BadgeCreada {{
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 9pt;
}}
#BadgeProximo {{
    background: rgba(124, 92, 255, 0.18);
    border: 1px solid rgba(124, 92, 255, 0.6);
    color: {ACENTO_HOVER};
}}
#BadgeAvisado, #BadgeCreada {{
    background: transparent;
    border: 1px solid {BORDE};
    color: {TEXTO_SUAVE};
}}

/* Alerta de recordatorio */
#Alerta {{
    background: {SUPERFICIE_ALTA};
    border: 2px solid {ACENTO};
    border-radius: 12px;
}}
#Alerta QLabel {{
    background: transparent;
}}
#AlertaEtiqueta {{
    color: {ACENTO_HOVER};
    font-size: 8.5pt;
    font-weight: 700;
}}
#AlertaTitulo {{
    font-size: 14pt;
    font-weight: 600;
}}
#AlertaContenido {{
    color: #c4c9d3;
}}
QPushButton#AlertaCerrar {{
    background: transparent;
    border: none;
    color: {TEXTO_SUAVE};
    padding: 0 4px;
}}
QPushButton#AlertaCerrar:hover {{
    color: {TEXTO};
}}

/* Comandos */
#ChipApp {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    border-radius: 10px;
    padding: 2px 9px;
    font-size: 9pt;
}}
#ChipIcono {{
    background: transparent;
}}
#EstadoEscucha {{
    background: transparent;
    color: {TEXTO_SUAVE};
    font-size: 9pt;
    padding: 8px 18px 0 18px;
}}
QProgressBar {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACENTO};
    border-radius: 4px;
}}
QListWidget {{
    background: {SUPERFICIE};
    border: 1px solid {BORDE};
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 6px;
}}
QListWidget::item:selected {{
    background: #2e2a4d;
    color: {TEXTO};
}}

/* Configuración */
#Seccion {{
    background: {SUPERFICIE};
    border: 1px solid {BORDE};
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
    color: {TEXTO_SUAVE};
    font-size: 9pt;
}}
QSlider {{
    background: transparent;
    min-height: 22px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {BORDE};
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACENTO};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: white;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

/* Calendario */
#CalendarioPopup {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    border-radius: 8px;
}}
QCalendarWidget QWidget#qt_calendar_navigationbar {{
    background: {SUPERFICIE_ALTA};
    padding: 4px;
}}
QCalendarWidget QToolButton {{
    background: transparent;
    color: {TEXTO};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}}
QCalendarWidget QToolButton:hover {{
    background: {BORDE};
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
    background: {SUPERFICIE};
    border: 1px solid {BORDE};
    border-radius: 4px;
    padding: 2px 4px;
}}
QCalendarWidget QAbstractItemView {{
    background: {SUPERFICIE};
    color: {TEXTO};
    selection-background-color: {ACENTO};
    selection-color: white;
    outline: none;
    border: none;
}}
QCalendarWidget QTableView::item {{
    padding: 0;
    border: none;
}}
QCalendarWidget QAbstractItemView:disabled {{
    color: #4b5160;
}}

QMenu {{
    background: {SUPERFICIE_ALTA};
    border: 1px solid {BORDE};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACENTO};
}}
QMenu::separator {{
    height: 1px;
    background: {BORDE};
    margin: 4px 6px;
}}

QStatusBar {{
    background: {SUPERFICIE};
    color: {TEXTO_SUAVE};
    border-top: 1px solid {BORDE};
}}
"""

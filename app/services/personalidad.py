"""Personalidad de Notivoz: sus frases en tres estilos y con variaciones.

Las frases habladas de la app (comandos, racha, modo enfoque, aviso de ocio…) se
piden aquí con una clave y se arman con los datos del momento.
"""

import random
import re
import unicodedata
from enum import StrEnum


class Personalidad(StrEnum):
    FORMAL = "formal"
    AMIGABLE = "amigable"
    DIVERTIDO = "divertido"

    @property
    def etiqueta(self) -> str:
        return {"formal": "Formal", "amigable": "Amigable", "divertido": "Divertido"}[self]

    @property
    def ejemplo(self) -> str:
        return {
            "formal": "«Modo relax activado. Que disfrute su tiempo libre.»",
            "amigable": "«¡A relajarse, Erick! Modo relax activado.»",
            "divertido": "«¡Modo fiesta! Modo relax listo, a disfrutar, Erick.»",
        }[self]


F, A, D = Personalidad.FORMAL, Personalidad.AMIGABLE, Personalidad.DIVERTIDO

# {n} = «, Nombre» (o vacío si no hay nombre). El resto de campos los da quien pide la frase.
_FRASES: dict[str, dict[Personalidad, list[str]]] = {
    "tarea_terminada": {
        F: ["Bien hecho. «{titulo}» quedó realizada."],
        A: ["¡Bien hecho{n}! «{titulo}» quedó realizada.", "¡Genial! Una menos: «{titulo}»."],
        D: ["¡Boom! «{titulo}» tachada de la lista.", "¡Eso{n}! «{titulo}», terminada."],
    },
    # {dias} llega como «1 día» o «5 días».
    "racha": {
        F: ["Su racha es de {dias} terminando tareas."],
        A: ["¡Racha de {dias}{n}! Sigue así."],
        D: ["¡Llevas {dias} en racha! Imparable."],
    },
    # --- Enfoque ---
    "enfoque_inicio": {
        F: ["Modo enfoque de {minutos} minutos{en}. Silencié los recordatorios hasta que termine."],
        A: ["Modo enfoque de {minutos} minutos{en}. Te aviso al terminar."],
        D: ["¡A concentrarse! {minutos} minutos{en}. Yo cuido que nadie te moleste."],
    },
    "enfoque_fin": {
        F: ["Terminó su bloque de enfoque{en}."],
        A: ["¡Tiempo{n}! Terminaste tu bloque de enfoque{en}."],
        D: ["¡Tiempo! Bloque de enfoque superado{en}. Te ganaste un descanso."],
    },
    "enfoque_cancelado": {F: ["Modo enfoque finalizado."], A: ["Listo, salimos del modo enfoque."], D: ["Fin del modo monje."]},
    # --- Aviso de ocio en horario de trabajo ---
    "aviso_ocio": {
        F: ["Le recuerdo que tiene pendiente «{titulo}»."],
        A: ["Oye{n}, ¿ya terminaste «{titulo}»?", "Un recordatorio amable: «{titulo}» sigue pendiente."],
        D: ["¡Te vi{n}! ¿Y «{titulo}» para cuándo?", "Mmm… ¿«{titulo}» ya está lista o seguimos jugando?"],
    },
    # --- Comandos ---
    "comando_cerrado": {
        F: ["{modo} finalizado. Cerré sus aplicaciones."],
        A: ["Listo{n}, cerré {modo}."],
        D: ["{modo} apagado. ¡Hasta la próxima!"],
    },
    "comando_nada_que_cerrar": {
        F: ["No encontré aplicaciones abiertas de {modo}."],
        A: ["No hay nada abierto de {modo}."],
        D: ["{modo} ya estaba apagado."],
    },
}

_COMANDO_POR_CATEGORIA: dict[str, dict[Personalidad, list[str]]] = {
    "trabajo": {
        F: ["{modo} activado. Sus herramientas de trabajo están listas."],
        A: ["¡Listo{n}! {modo} activado, todo preparado para avanzar.", "¡A trabajar{n}! {modo} activado."],
        D: ["¡A chambear{n}! {modo} en marcha.", "¡Manos a la obra{n}! {modo} listo para romperla."],
    },
    "ocio": {
        F: ["{modo} activado. Que disfrute su tiempo libre."],
        A: ["¡A relajarse{n}! {modo} activado.", "¡Listo{n}! {modo} activado, a disfrutar."],
        D: ["¡Modo fiesta! {modo} listo, a disfrutar{n}.", "¡Que empiece la diversión{n}! {modo} activado."],
    },
    "estudio": {
        F: ["{modo} activado. Todo listo para estudiar."],
        A: ["¡A estudiar{n}! {modo} activado.", "{modo} activado. ¡Mucho éxito estudiando{n}!"],
        D: ["¡Cerebro en modo turbo{n}! {modo} activado."],
    },
    "general": {
        F: ["{modo} activado."],
        A: ["¡Listo{n}! {modo} activado.", "{modo} activado{n}."],
        D: ["¡{modo} activado{n}! Todo listo.", "¡Hecho! {modo} en marcha."],
    },
}

_PALABRAS_CATEGORIA = {
    "trabajo": (
        "chamba", "chambear", "trabajo", "trabajar", "oficina", "laburo", "codigo", "programar",
        "reunion", "negocio", "productivo", "proyecto",
    ),
    "ocio": (
        "chill", "relajo", "relax", "relajar", "juego", "jugar", "gamer", "gaming", "diversion",
        "fiesta", "musica", "pelicula", "peliculas", "serie", "series", "ocio", "vacilon", "joda",
    ),
    "estudio": ("estudio", "estudiar", "clase", "clases", "universidad", "curso", "aprender", "examen"),
}  # fmt: skip
_APPS_CATEGORIA = {
    "trabajo": (
        "visual studio", "code", "excel", "word", "outlook", "teams", "slack", "notion", "figma",
        "postman", "pycharm", "intellij", "sql", "powerpoint", "trello", "jira", "git",
    ),
    "ocio": (
        "steam", "epic", "spotify", "netflix", "discord", "twitch", "youtube", "battle net",
        "riot", "xbox", "prime video", "disney", "opera gx", "playstation", "crunchyroll",
    ),
    "estudio": ("classroom", "moodle", "zoom", "anki", "duolingo", "canvas"),
}  # fmt: skip

# Los textos informativos (saludo, resumen del día) se redactan tuteando; con la
# personalidad formal se pasan a «usted».
_A_USTED = [
    ("No tienes", "No tiene"), ("Hoy tienes", "Hoy tiene"), ("Tienes", "Tiene"),
    ("Te quedan", "Le quedan"), ("Te queda", "Le queda"), ("No te quedan", "No le quedan"),
    ("Hoy no cerraste", "Hoy no cerró"), ("Hoy cerraste", "Hoy cerró"), ("Llevas", "Lleva"),
]  # fmt: skip


def _normalizar(texto: str) -> str:
    """'Modo CHAMBA' → 'modo chamba' (minúsculas, sin tildes ni signos)."""
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w\s]", " ", texto).split())


def _contiene(texto: str, *frases: str) -> bool:
    return any(re.search(rf"\b{re.escape(f)}\b", texto) for f in frases)


def categoria_de_modo(frase: str, nombres_apps: list[str]) -> str:
    """Adivina si un modo es de trabajo, ocio o estudio: primero por sus
    palabras («chamba», «relajo»…) y si no, por las apps que abre."""
    texto = _normalizar(frase)
    for categoria, palabras in _PALABRAS_CATEGORIA.items():
        if _contiene(texto, *palabras):
            return categoria
    votos = {categoria: 0 for categoria in _APPS_CATEGORIA}
    for nombre in nombres_apps:
        nombre = _normalizar(nombre)
        for categoria, apps in _APPS_CATEGORIA.items():
            if _contiene(nombre, *apps):
                votos[categoria] += 1
    mejor = max(votos, key=votos.get)
    return mejor if votos[mejor] > 0 else "general"


class Frases:
    """Arma las frases de Notivoz según la personalidad y el nombre del usuario."""

    def __init__(self, personalidad: Personalidad = Personalidad.AMIGABLE, nombre: str = ""):
        self.personalidad = Personalidad(personalidad)
        self.nombre = nombre.strip()
        self._azar = random.Random()

    def _elegir(self, opciones: dict[Personalidad, list[str]], /, **datos) -> str:
        plantilla = self._azar.choice(opciones[self.personalidad])
        # El formal no tutea ni usa el nombre de pila.
        datos.setdefault("n", f", {self.nombre}" if self.nombre and self.personalidad != F else "")
        texto = plantilla.format(**datos)
        return texto[:1].upper() + texto[1:]

    def frase(self, clave: str, **datos) -> str:
        return self._elegir(_FRASES[clave], **datos)

    def comando_activado(self, frase: str, nombres_apps: list[str]) -> str:
        categoria = categoria_de_modo(frase, nombres_apps)
        return self._elegir(_COMANDO_POR_CATEGORIA[categoria], modo=frase.capitalize())

    def adaptar(self, texto: str) -> str:
        """Pasa a «usted» un texto escrito tuteando, si la personalidad es formal."""
        if self.personalidad == F:
            for tu, usted in _A_USTED:
                texto = texto.replace(tu, usted)
        return texto

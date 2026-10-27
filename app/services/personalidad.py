"""Personalidad de Notivoz: sus frases en cuatro estilos y con variaciones.

Las frases habladas de la app (comandos, racha, modo enfoque, aviso de ocio…) se
piden aquí con una clave y se arman con los datos del momento.
"""

import random
from collections import deque
import re
import unicodedata
from enum import StrEnum


class Personalidad(StrEnum):
    FORMAL = "formal"
    AMIGABLE = "amigable"
    DIVERTIDO = "divertido"
    PERUANAZO = "peruanazo"

    @property
    def etiqueta(self) -> str:
        return {"formal": "Formal", "amigable": "Amigable", "divertido": "Divertido", "peruanazo": "Peruanazo"}[self]

    @property
    def ejemplo(self) -> str:
        return {
            "formal": "«Tarea registrada correctamente.» Serio y de usted.",
            "amigable": "«¡Listo, Erick! Tu tarea ya está creada.» Cálido y con energía.",
            "divertido": "«¡Pum! Tarea creada. Una más para la colección.» Alegre y bromista.",
            "peruanazo": "«¡Ya está, batería! Tarea anotada al toque.» Con jerga peruana.",
        }[self]


F, A, D, P = Personalidad.FORMAL, Personalidad.AMIGABLE, Personalidad.DIVERTIDO, Personalidad.PERUANAZO

# {n} = «, Nombre» (o vacío si no hay nombre). El resto de campos los da quien pide la frase.
# Varias variantes por frase: nunca se repite la misma dos veces seguidas.
_FRASES: dict[str, dict[Personalidad, list[str]]] = {
    "tarea_terminada": {
        F: ["Bien hecho. «{titulo}» quedó realizada."],
        A: ["¡Bien hecho{n}! «{titulo}» quedó realizada.", "¡Genial! Una menos: «{titulo}»."],
        D: ["¡Boom! «{titulo}» tachada de la lista.", "¡Eso{n}! «{titulo}», terminada.", "¡Chau, «{titulo}»! No te extrañaremos."],
        P: [
            "¡Bacán, causa! «{titulo}» ya fue.", "¡Eso, batería! «{titulo}» terminada al toque.",
            "¡Paja, bro! «{titulo}» lista.", "¡Asu, cholo, la rompiste! «{titulo}» ya está.",
            "¡Mostro, pata! «{titulo}» chancada.",
        ],
    },
    # {dias} llega como «1 día» o «5 días».
    "racha": {
        F: ["Su racha es de {dias} terminando tareas."],
        A: ["¡Racha de {dias}{n}! Sigue así."],
        D: ["¡Llevas {dias} en racha! Imparable.", "¡{dias} seguidos! Ni el café es tan constante."],
        P: [
            "¡{dias} en racha, causa! Estás que la rompes.", "¡Asu, {dias} seguidos, batería! Imparable.",
            "¡{dias} de racha, bro! Estás on fire.", "¡{dias} en racha, cholo! A la firme, eres un crack.",
        ],
    },
    # --- Enfoque ---
    "enfoque_inicio": {
        F: ["Modo enfoque de {minutos} minutos{en}. Silencié los recordatorios hasta que termine."],
        A: ["Modo enfoque de {minutos} minutos{en}. Te aviso al terminar."],
        D: ["¡A concentrarse! {minutos} minutos{en}. Yo cuido que nadie te moleste.", "Modo monje: {minutos} minutos{en}. Shhh."],
        P: [
            "¡A chambear en serio, pata! {minutos} minutos{en}. Yo te cuido la puerta.",
            "¡Habla, batería! {minutos} minutos{en} a full. Nadie te molesta, palabra.",
            "¡De una, bro! {minutos} minutos{en}. Yo vigilo.",
        ],
    },
    "enfoque_fin": {
        F: ["Terminó su bloque de enfoque{en}."],
        A: ["¡Tiempo{n}! Terminaste tu bloque de enfoque{en}."],
        D: ["¡Tiempo! Bloque de enfoque superado{en}. Te ganaste un descanso.", "¡Ding ding! Ronda ganada{en}."],
        P: [
            "¡Ya fue, causa! Bloque de enfoque superado{en}. Te ganaste tu break.",
            "¡Bacán, cholo! Terminaste tu bloque{en}. Anda tómate un cafecito.",
            "¡Joya, bro! Enfoque cumplido{en}.",
        ],
    },
    "enfoque_cancelado": {
        F: ["Modo enfoque finalizado."],
        A: ["¡Listo, salimos del modo enfoque!"],
        D: ["Fin del modo monje.", "El monje colgó los hábitos."],
        P: ["Ya fue el modo monje, causa.", "Listo, bro, se acabó el enfoque.", "Chévere, batería, salimos del enfoque."],
    },
    # --- Aviso de ocio en horario de trabajo ---
    "aviso_ocio": {
        F: ["Le recuerdo que tiene pendiente «{titulo}»."],
        A: ["Oye{n}, ¿ya terminaste «{titulo}»?", "Un recordatorio amable: «{titulo}» sigue pendiente."],
        D: ["¡Te vi{n}! ¿Y «{titulo}» para cuándo?", "Mmm… ¿«{titulo}» ya está lista o seguimos jugando?"],
        P: [
            "¡Te vi, causa! ¿Y «{titulo}» para cuándo?", "Oe, ¿«{titulo}» ya está o seguimos vacilando?",
            "Ya pues, batería, ¿y «{titulo}»?", "Bro, «{titulo}» te está esperando, no te hagas.",
            "Cholo, ¿«{titulo}» cuándo? No me hagas roche.",
        ],
    },
    # --- Lo que hizo el asistente (confirmaciones cortas, siempre las mismas para
    # que su voz ya esté lista y suene al instante) ---
    "hecho_tarea": {
        F: ["Tarea registrada correctamente.", "Listo, la tarea quedó registrada.", "Hecho. Tarea creada.", "Su tarea ya está registrada."],
        A: ["¡Listo! Tarea creada.", "¡Hecho! Tu tarea ya está anotada.", "¡Ya está! Tarea guardada.", "¡Perfecto! Tarea lista."],
        D: ["¡Pum! Tarea creada.", "¡Anotada! Una más para la colección.", "¡Tarea creada! Ya no se me escapa.", "¡Tadá! Tarea lista."],
        P: [
            "¡Ya está, causa! Tarea anotada al toque.", "¡Bacán, batería! Tarea creada.",
            "¡De una, bro! Ya la anoté.", "¡Chévere, cholo! Tarea lista.", "¡Paja, pata! Tarea creada al toque.",
        ],
    },
    "hecho_tarea_editada": {
        F: ["Tarea actualizada correctamente.", "Listo, la tarea quedó actualizada.", "Hecho. Cambio registrado."],
        A: ["¡Listo! Tarea actualizada.", "¡Hecho! Ya cambié tu tarea.", "¡Ya está! Cambio guardado."],
        D: ["¡Listo! Tarea con cambio de look.", "¡Hecho! Tarea renovadita.", "¡Zas! Cambio hecho."],
        P: [
            "¡Ya fue, causa! Tarea cambiada.", "¡Chévere, bro! Tarea actualizada al toque.",
            "¡Listo, batería! Ya la cambié.", "¡Joya, cholo! Tarea actualizada.",
        ],
    },
    "hecho_nota": {
        F: ["Nota guardada correctamente.", "Listo, la nota quedó guardada.", "Hecho. Nota registrada."],
        A: ["¡Listo! Nota guardada.", "¡Hecho! Tu nota ya está guardada.", "¡Ya está! Nota anotada."],
        D: ["¡Nota guardada! Mejor que un post-it.", "¡Anotado! Mi memoria es de elefante.", "¡Pum! Nota guardada."],
        P: [
            "¡Ya está, causa! Nota guardada.", "¡Bacán, bro! Nota anotada al toque.",
            "¡De una, batería! Ya la guardé.", "¡Paja, cholo! Nota guardada.",
        ],
    },
    "hecho_recordatorio": {
        F: ["Recordatorio programado correctamente.", "Listo, se lo recordaré a la hora indicada.", "Hecho. Recordatorio registrado."],
        A: ["¡Listo! Te lo recordaré.", "¡Hecho! Recordatorio programado.", "¡Ya está! Yo te aviso."],
        D: ["¡Listo! Te lo recuerdo, aunque te escondas.", "¡Programado! Seré tu alarma con estilo.", "¡Hecho! Mi reloj ya está avisado."],
        P: [
            "¡Ya está, causa! Yo te aviso.", "¡Al toque, bro! Recordatorio listo.",
            "¡Chévere, batería! Yo te pego el grito.", "¡Joya, cholo! Te aviso a la hora.",
        ],
    },
    "hecho_eliminado": {
        F: ["Eliminado correctamente.", "Listo, quedó eliminado.", "Hecho. Eliminado."],
        A: ["¡Listo! Eliminado.", "¡Hecho! Ya lo eliminé.", "¡Ya está! Fuera de la lista."],
        D: ["¡Puf! Desapareció.", "¡Eliminado! Como si nunca hubiera existido.", "¡Zas! A la papelera."],
        P: [
            "¡Chau chau! Eliminado, causa.", "¡Ya fue, bro! Borrado al toque.",
            "¡Listo, batería! Lo volé.", "¡Fuera, cholo! Eliminado.",
        ],
    },
    "hecho_recuperado": {
        F: ["Recuperado correctamente."],
        A: ["¡Listo! Lo recuperé.", "¡Uf, a tiempo! Ya está de vuelta."],
        D: ["¡Resucitado! Ya está de vuelta.", "¡Uf, de las justas! Recuperado."],
        P: [
            "¡Salvado, causa! Ya está de vuelta.", "¡Asu, de las justas, bro! Recuperado.",
            "¡Bacán, batería! Ya regresó.",
        ],
    },
    "hecho_cliente": {
        F: ["Cliente registrado correctamente.", "Listo, cliente agregado."],
        A: ["¡Listo! Cliente agregado.", "¡Hecho! Cliente nuevo en la lista."],
        D: ["¡Cliente nuevo! La familia crece.", "¡Bienvenido a bordo, cliente nuevo!"],
        P: ["¡Bacán! Cliente nuevo en la lista, causa.", "¡Paja, bro! Cliente agregado.", "¡De una, batería! Cliente registrado."],
    },
    "hecho_app": {
        F: ["Aplicación abierta."],
        A: ["¡Listo! Ya está abierta."],
        D: ["¡Tadá! Ya está abierta."],
        P: ["¡Al toque, causa! Ya está abierta.", "¡Listo, bro! Ahí la tienes.", "¡De una, batería! Abierta."],
    },
    "hecho_ventana": {
        F: ["Aquí la tiene."],
        A: ["¡Aquí la tienes!"],
        D: ["¡Tadá! Aquí la tienes."],
        P: ["¡Ahí está, causa!", "¡Ahí la tienes, bro!", "¡Toma, batería!"],
    },
    "hecho_correccion": {
        F: ["Entendido, lo tendré en cuenta."],
        A: ["¡Anotado! La próxima te entiendo a la primera."],
        D: ["¡Anotado! Mis oídos aprendieron algo nuevo."],
        P: ["¡Ya manyé, causa! A la próxima no fallo.", "¡Chévere, bro! Ya lo aprendí.", "¡Ya caché, batería! No vuelve a pasar."],
    },
    "hecho_varios": {
        F: ["Listo, todo quedó registrado.", "Hecho. Todo está en orden."],
        A: ["¡Listo! Ya hice todo.", "¡Hecho! Todo listo."],
        D: ["¡Combo completo! Todo listo.", "¡Todo hecho! Ni pestañeé."],
        P: ["¡Ya fue, causa! Todo listo al toque.", "¡Paja, bro! Ya hice todo.", "¡Mostro, batería! Todo listo."],
    },
    # --- Apagado programado de la PC ---
    "apagado_aviso": {
        F: ["Su PC se apagará en un minuto. Puede cancelarlo en el aviso."],
        A: ["Tu PC se apagará en un minuto. Si quieres, cancélalo en el aviso."],
        D: ["¡Cuenta regresiva! Tu PC se apaga en un minuto. Aún puedes cancelarlo."],
        P: ["Oe causa, tu PC se apaga en un minuto. Si no, cancélalo en el aviso.", "Bro, en un minuto se apaga tu PC. Guarda todo, ah."],
    },
    "reinicio_aviso": {
        F: ["Su PC se reiniciará en un minuto. Puede cancelarlo en el aviso."],
        A: ["Tu PC se reiniciará en un minuto. Si quieres, cancélalo en el aviso."],
        D: ["¡Cuenta regresiva! Tu PC se reinicia en un minuto. Aún puedes cancelarlo."],
        P: ["Oe causa, tu PC se reinicia en un minuto. Si no, cancélalo en el aviso."],
    },
    "apagado_despedida": {
        F: ["Hasta luego. Apagando su PC.", "Que descanse. Apagando su PC."],
        A: ["¡Hasta pronto! Apagando tu PC.", "¡Nos vemos! Apagando tu PC."],
        D: ["¡Me voy a dormir! Nos vemos.", "¡Apagando motores! Hasta la próxima."],
        P: ["¡Chau, causa! Nos vemos al toque.", "¡Ya fue, bro! Me voy a jatear.", "¡Nos vidrios, batería!"],
    },
    "reinicio_despedida": {
        F: ["Reiniciando su PC. Vuelvo enseguida."],
        A: ["¡Ya vuelvo! Reiniciando tu PC."],
        D: ["¡Me doy una siestita y vuelvo!"],
        P: ["¡Ya regreso, bro! Reiniciando al toque.", "¡Toy de vuelta en nada, causa!"],
    },
    # (Sirve para apagar y para reiniciar.)
    "apagado_no": {
        F: ["De acuerdo, la dejo encendida."],
        A: ["Tranquilo, la dejo encendida."],
        D: ["¡Falsa alarma! Sigo despierta."],
        P: ["Ya, causa, la dejo prendida.", "Tranqui, bro, sigo prendida."],
    },
    "apagado_cancelado": {
        F: ["Apagado cancelado."],
        A: ["¡Listo! Cancelé el apagado."],
        D: ["¡Abortar misión! Apagado cancelado."],
        P: ["¡Ya fue, causa! Apagado cancelado.", "Tranqui, bro, ya no se apaga."],
    },
    # --- Comandos ---
    "comando_cerrado": {
        F: ["{modo} finalizado. Cerré sus aplicaciones."],
        A: ["Listo{n}, cerré {modo}."],
        D: ["{modo} apagado. ¡Hasta la próxima!", "{modo} se fue a dormir."],
        P: ["{modo} apagado, causa. ¡Nos vemos!", "Listo, bro, {modo} cerrado.", "Ya fue {modo}, batería."],
    },
    "comando_nada_que_cerrar": {
        F: ["No encontré aplicaciones abiertas de {modo}."],
        A: ["No hay nada abierto de {modo}."],
        D: ["{modo} ya estaba apagado."],
        P: ["{modo} ya estaba apagado, causa.", "Nada abierto de {modo}, bro."],
    },
}

_COMANDO_POR_CATEGORIA: dict[str, dict[Personalidad, list[str]]] = {
    "trabajo": {
        F: ["{modo} activado. Sus herramientas de trabajo están listas."],
        A: ["¡Listo{n}! {modo} activado, todo preparado para avanzar.", "¡A trabajar{n}! {modo} activado."],
        D: ["¡A trabajar{n}! {modo} en marcha.", "¡Manos a la obra{n}! {modo} listo para romperla."],
        P: [
            "¡A chambear, causa! {modo} en marcha.", "¡Manos a la obra, pata! {modo} listo para romperla.",
            "¡Habla, batería! {modo} activado, a sacar la chamba.", "¡De una, bro! {modo} listo.",
        ],
    },
    "ocio": {
        F: ["{modo} activado. Que disfrute su tiempo libre."],
        A: ["¡A relajarse{n}! {modo} activado.", "¡Listo{n}! {modo} activado, a disfrutar."],
        D: ["¡Modo fiesta! {modo} listo, a disfrutar{n}.", "¡Que empiece la diversión{n}! {modo} activado."],
        P: [
            "¡Modo vacilón, causa! {modo} listo.", "¡Que empiece el tono, bro! {modo} activado.",
            "¡A relajarse, batería! {modo} bacán.", "¡Chévere, cholo! {modo} activado, a disfrutar.",
        ],
    },
    "estudio": {
        F: ["{modo} activado. Todo listo para estudiar."],
        A: ["¡A estudiar{n}! {modo} activado.", "{modo} activado. ¡Mucho éxito estudiando{n}!"],
        D: ["¡Cerebro en modo turbo{n}! {modo} activado."],
        P: ["¡A chancar, causa! {modo} activado.", "¡Cerebro en modo turbo, bro! {modo} listo.", "¡A meterle, batería! {modo} activado."],
    },
    "general": {
        F: ["{modo} activado."],
        A: ["¡Listo{n}! {modo} activado.", "{modo} activado{n}."],
        D: ["¡{modo} activado{n}! Todo listo.", "¡Hecho! {modo} en marcha."],
        P: ["¡{modo} activado al toque, causa!", "¡Chévere, bro! {modo} en marcha.", "¡Joya, batería! {modo} listo."],
    },
}

# Lo que dice la nube mientras te escucha y mientras procesa.
_ESTADOS: dict[str, dict[Personalidad, str]] = {
    "escuchando": {F: "Escuchándote", A: "Escuchándote", D: "Escuchándote", P: "Ladra"},
    "procesando": {F: "Procesando", A: "Procesando", D: "Procesando", P: "Chambeando"},
}

# Gestos para un «gracias» (sin hablar), según la personalidad.
_GESTOS: dict[Personalidad, list[str]] = {
    F: ["🙂", "👍", "🤝", "✅", "👌", "🙏"],
    A: ["😊", "👍", "🙌", "💜", "🤗", "😄", "✨", "🥰", "👏", "🌟"],
    D: ["😄", "🙌", "🎉", "😎", "🥳", "🤩", "✨", "😜", "🕺", "🤘", "🦾", "🎊"],
    P: ["🇵🇪", "🤙", "😎", "🙌", "💪", "🔥", "🤜🤛", "🥳", "😄", "👊", "🫡", "✨"],
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


# Lo último que se dijo de cada lista, para no repetirlo enseguida (las frases se
# piden con objetos Frases nuevos cada vez, por eso vive aquí).
_RECIENTES: dict[int, deque[str]] = {}


def _variar(opciones: list[str], azar: random.Random) -> str:
    """Elige al azar sin repetir lo último que se dijo de esta lista (con muchas
    opciones, evita hasta las tres anteriores)."""
    recientes = _RECIENTES.setdefault(id(opciones), deque(maxlen=max(1, min(3, len(opciones) // 2))))
    libres = [o for o in opciones if o not in recientes] or list(opciones)
    elegida = azar.choice(libres)
    if len(opciones) > 1:
        recientes.append(elegida)
    return elegida


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
        return self._armar(_variar(opciones[self.personalidad], self._azar), **datos)

    def _armar(self, plantilla: str, /, **datos) -> str:
        # El formal no tutea ni usa el nombre de pila.
        datos.setdefault("n", f", {self.nombre}" if self.nombre and self.personalidad != F else "")
        texto = plantilla.format(**datos)
        return texto[:1].upper() + texto[1:]

    def frase(self, clave: str, **datos) -> str:
        return self._elegir(_FRASES[clave], **datos)

    def comando_activado(self, frase: str, nombres_apps: list[str]) -> str:
        categoria = categoria_de_modo(frase, nombres_apps)
        return self._elegir(_COMANDO_POR_CATEGORIA[categoria], modo=frase.capitalize())

    def confirmaciones(self) -> list[str]:
        """Todas las confirmaciones cortas del asistente («¡Listo! Tarea creada.»)."""
        return [t for clave in _FRASES if clave.startswith("hecho_") for t in self.todas(clave)]

    def todas(self, clave: str) -> list[str]:
        """Todas las variantes de una frase sin campos (para preparar su voz)."""
        return [self._armar(p) for p in _FRASES[clave][self.personalidad]]

    def estado(self, clave: str) -> str:
        """«Escuchándote» / «Procesando» (o como lo diga esta personalidad)."""
        return _ESTADOS[clave][self.personalidad]

    def gesto(self) -> str:
        """Un emoji para responder a un «gracias», distinto de los últimos."""
        return _variar(_GESTOS[self.personalidad], self._azar)

    def adaptar(self, texto: str) -> str:
        """Pasa a «usted» un texto escrito tuteando, si la personalidad es formal."""
        if self.personalidad == F:
            for tu, usted in _A_USTED:
                texto = texto.replace(tu, usted)
        return texto

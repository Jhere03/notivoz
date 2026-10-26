"""Herramientas que la IA puede pedir a Notivoz, y su validación.

La IA no ejecuta nada por sí misma: solo pide una de estas herramientas con
unos datos, y este módulo decide si se hace. Reglas de seguridad:

- Lista cerrada de herramientas: nada de comandos, rutas, archivos ni web.
- Todo dato que llega de la IA se vuelve a validar aquí (tipos, largos,
  fechas, ids): nunca se confía en que respete el esquema.
- Eliminar es inmediato (sin preguntas), pero solo si el usuario lo pidió con
  sus palabras en ese mismo pedido («elimina», «borra», «quita»…): un texto
  malicioso guardado en una nota no puede ordenar borrar nada. Además, lo
  eliminado se puede recuperar unos minutos («deshaz eso» o el botón Deshacer).
- Hay un máximo de cambios por pedido (si un texto malicioso intentara
  manipular a la IA, el daño posible queda acotado).
- Abrir apps: solo las instaladas que aparecen en el menú Inicio, sin
  argumentos (abrir una consola no ejecuta nada en ella), y nunca
  desinstaladores, el editor del registro u otras herramientas de
  administración del sistema.
- Forzar el cierre de una app (puede perder cambios sin guardar) también lo
  confirma el usuario, no la IA.
- Las respuestas llevan lo mínimo necesario y con límite de elementos.
"""

import json
import logging
import os
import sys
import threading
import time
import unicodedata
from collections.abc import Callable
from difflib import SequenceMatcher
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from app.data.models import Estado, Importancia
from app.services import ajustes
from app.services import clientes as servicio_clientes
from app.services import comandos as servicio_comandos
from app.services import lanzador
from app.services import notas as servicio_notas
from app.services import pendientes as servicio_pendientes
from app.services import rutinas as servicio_rutinas
from app.services.ajustes import Clave
from app.services.notas import DatosNota
from app.services.pendientes import DatosPendiente, FiltroPendientes
from app.services.personalidad import Frases
from app.services.redaccion import RedactorCorreo

log = logging.getLogger(__name__)

MAX_RESULTADOS = 25
MAX_CAMBIOS_POR_TURNO = 5
_MAX_A_ELIMINAR = 100  # elementos en una sola eliminación («elimina todas mis tareas»)
SEGUNDOS_PARA_CONFIRMAR = 90
_FORMATO_FECHA_HORA = "%Y-%m-%d %H:%M"

_LARGO_TITULO = 200
_LARGO_DESCRIPCION = 2000
_LARGO_CONTENIDO = 4000
_LARGO_NOMBRE = 120
_LARGO_BUSQUEDA = 100

_IMPORTANCIAS = {i.etiqueta: i for i in Importancia}
# Secciones de la ventana que la IA puede abrir.
SECCIONES = ("Mis tareas", "Notas", "Comandos de voz", "Rutinas", "Chateemos", "Configuración")
_ESTADOS = {e.value: e for e in Estado}

# Apps que nunca se abren por voz: consolas, scripts y herramientas del sistema.
# Desinstaladores y herramientas de administración del sistema: nunca por voz.
_APPS_BLOQUEADAS = (
    "registro", "registry", "regedit", "uninstall", "desinstalar",
    "servicios", "services", "msconfig", "configuracion del sistema",
    "system configuration", "programador de tareas", "task scheduler", "directiva", "policy",
    "administracion de equipos", "computer management", "administrador de discos",
    "disk management", "visor de eventos", "event viewer", "recovery", "recuperacion",
    "herramientas de windows", "windows tools", "administrative", "administrativas",
)


# Notivoz nunca se cierra a sí mismo por voz.
_PROPIO = os.path.basename(sys.executable).lower()


class ErrorHerramienta(Exception):
    """Dato inválido o acción no permitida: se le devuelve a la IA como error."""


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni espacios de más: para comparar nombres y títulos."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


# --- Nombres que suenan parecido -----------------------------------------------------
#
# Whisper puede escribir «Bento» cuando dijiste «Dento», o «F» cuando dijiste
# «EFE». Se compara cómo suenan, también deletreando siglas (EFE = «efe»).

_LETRAS = {
    "a": "a", "b": "be", "c": "ce", "d": "de", "e": "e", "f": "efe", "g": "ge", "h": "hache",
    "i": "i", "j": "jota", "k": "ka", "l": "ele", "m": "eme", "n": "ene", "o": "o", "p": "pe",
    "q": "cu", "r": "erre", "s": "ese", "t": "te", "u": "u", "v": "uve", "w": "doble uve",
    "x": "equis", "y": "ye", "z": "zeta",
}
_PARECIDO_MINIMO = 0.75


def _formas(texto: str) -> set[str]:
    """Cómo puede sonar un nombre: tal cual y, si es corto, deletreado."""
    normal = normalizar(texto)
    formas = {normal.replace(" ", "")}
    if 0 < len(normal.replace(" ", "")) <= 4 and normal.replace(" ", "").isalpha():
        formas.add("".join(_LETRAS.get(c, c) for c in normal.replace(" ", "")).replace(" ", ""))
    return formas


def _parecido(dicho: str, nombre: str) -> float:
    puntaje = max(SequenceMatcher(None, x, y).ratio() for x in _formas(dicho) for y in _formas(nombre))
    # «Beta» para «Beta SAC»: dijo una palabra completa del nombre.
    palabras = normalizar(nombre).split()
    if len(normalizar(dicho)) >= 3 and normalizar(dicho) in palabras:
        puntaje = max(puntaje, 0.9)
    return puntaje


def cliente_parecido(nombre: str, clientes: list):
    """El cliente que coincide o suena casi igual; None si no hay uno claro."""
    puntajes = sorted(((_parecido(nombre, c.nombre), c) for c in clientes), key=lambda p: -p[0])
    if not puntajes or puntajes[0][0] < _PARECIDO_MINIMO:
        return None
    if len(puntajes) > 1 and puntajes[1][0] >= puntajes[0][0] - 0.05 and puntajes[0][0] < 1.0:
        nombres = ", ".join(c.nombre for _, c in puntajes[:3])
        raise ErrorHerramienta(f"«{nombre}» se parece a varios clientes ({nombres}). Pregunta cuál.")
    return puntajes[0][1]


def _corto(texto: str, largo: int = 80) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def resumen_de_datos() -> str:
    """Lo esencial de la app en cada pedido, para que la IA actúe sin buscar
    primero (una llamada menos). Va en el mensaje, no en las instrucciones fijas."""
    lineas = []
    clientes = servicio_clientes.listar()
    lineas.append("Clientes: " + (", ".join(c.nombre for c in clientes[:60]) or "ninguno"))
    tareas = servicio_pendientes.listar()
    activas = [p for p in tareas if p.estado != Estado.REALIZADO]
    hechas = sorted(
        (p for p in tareas if p.estado == Estado.REALIZADO and p.fecha_realizado),
        key=lambda p: p.fecha_realizado,
        reverse=True,
    )
    lineas.append(f"Tareas sin terminar ({len(activas)}):")
    for p in activas[:40]:
        cliente = p.cliente.nombre if p.cliente else "sin cliente"
        lineas.append(
            f"- [id {p.id}] {_corto(p.titulo)} · {cliente} · {Importancia(p.importancia).etiqueta} · {p.estado}"
            f" · ingreso {p.fecha_ingreso:%Y-%m-%d}"
        )
    if hechas:
        lineas.append("Terminadas recientemente:")
        for p in hechas[:5]:
            cliente = p.cliente.nombre if p.cliente else "sin cliente"
            lineas.append(f"- [id {p.id}] {_corto(p.titulo)} · {cliente} · terminada {p.fecha_realizado:%d/%m %H:%M}")
    notas = servicio_notas.listar()
    proximos = [n for n in notas if servicio_notas.es_proxima(n)]
    if proximos:
        lineas.append("Recordatorios próximos:")
        for n in proximos[:15]:
            lineas.append(f"- [id {n.id}] {_corto(n.titulo)} · {n.recordatorio:{_FORMATO_FECHA_HORA}}")
    otras = [n for n in notas if not servicio_notas.es_proxima(n)]
    if otras:
        lineas.append(f"Otras notas ({len(otras)}): " + "; ".join(f"[id {n.id}] {_corto(n.titulo, 50)}" for n in otras[:8]))
    modos = servicio_comandos.listar()
    if modos:
        lineas.append("Modos: " + "; ".join(f"[id {c.id}] {c.frase}" for c in modos[:20]))
    return "\n".join(lineas)


# --- Validación de lo que manda la IA --------------------------------------------


def _texto(entrada: dict, clave: str, largo: int, obligatorio: bool = False) -> str | None:
    valor = entrada.get(clave)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obligatorio:
            raise ErrorHerramienta(f"Falta «{clave}».")
        return None
    if not isinstance(valor, str):
        raise ErrorHerramienta(f"«{clave}» debe ser texto.")
    valor = valor.strip()
    if len(valor) > largo:
        raise ErrorHerramienta(f"«{clave}» es demasiado largo (máximo {largo} caracteres).")
    return valor


def _id(entrada: dict, clave: str = "id") -> int:
    valor = entrada.get(clave)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 < valor < 10**9:
        raise ErrorHerramienta(f"«{clave}» debe ser un número de id válido.")
    return valor


def _opcion(entrada: dict, clave: str, opciones: dict) -> Any:
    valor = entrada.get(clave)
    if valor is None:
        return None
    if valor not in opciones:
        raise ErrorHerramienta(f"«{clave}» debe ser uno de: {', '.join(opciones)}.")
    return opciones[valor]


def _fecha(entrada: dict, clave: str) -> date | None:
    """Fecha AAAA-MM-DD (por ejemplo, la de ingreso de una tarea)."""
    valor = _texto(entrada, clave, 12)
    if valor is None:
        return None
    try:
        dia = datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise ErrorHerramienta(f"«{clave}» debe tener el formato AAAA-MM-DD.") from None
    if not date.today() - timedelta(days=10 * 365) <= dia <= date.today() + timedelta(days=3 * 365):
        raise ErrorHerramienta(f"«{clave}» está fuera de rango.")
    return dia


def _fecha_hora(entrada: dict, clave: str, pasado: bool = False) -> datetime | None:
    """Fecha y hora AAAA-MM-DD HH:MM. Los recordatorios deben ser futuros;
    con `pasado=True` (cuándo se terminó una tarea) debe ser pasada."""
    valor = _texto(entrada, clave, 20)
    if valor is None:
        return None
    try:
        momento = datetime.strptime(valor, _FORMATO_FECHA_HORA)
    except ValueError:
        raise ErrorHerramienta(f"«{clave}» debe tener el formato AAAA-MM-DD HH:MM.") from None
    ahora = datetime.now()
    if pasado:
        if not ahora - timedelta(days=10 * 365) <= momento <= ahora + timedelta(minutes=5):
            raise ErrorHerramienta(f"«{clave}» debe ser una fecha pasada.")
        return momento
    if momento < ahora - timedelta(minutes=5):
        raise ErrorHerramienta("Esa fecha y hora ya pasaron; pide al usuario otra.")
    if momento > ahora + timedelta(days=3 * 365):
        raise ErrorHerramienta("La fecha está demasiado lejos (máximo 3 años).")
    return momento


def _booleano(entrada: dict, clave: str) -> bool:
    return entrada.get(clave) is True


# --- Formatos de salida (lo mínimo) ----------------------------------------------


def _tarea(p) -> dict:
    return {
        "id": p.id,
        "titulo": p.titulo,
        "cliente": p.cliente.nombre if p.cliente else None,
        "estado": p.estado,
        "importancia": Importancia(p.importancia).etiqueta,
        "ingreso": p.fecha_ingreso.isoformat(),
        "terminada": p.fecha_realizado.strftime(_FORMATO_FECHA_HORA) if p.fecha_realizado else None,
        "descripcion": (p.descripcion[:200] + "…") if len(p.descripcion) > 200 else p.descripcion,
    }


def _nota(n) -> dict:
    return {
        "id": n.id,
        "titulo": n.titulo,
        "contenido": (n.contenido[:300] + "…") if len(n.contenido) > 300 else n.contenido,
        "recordatorio": n.recordatorio.strftime(_FORMATO_FECHA_HORA) if n.recordatorio else None,
        "ya_avisado": bool(n.recordatorio and n.notificado),
    }


def _lista(elementos: list, formato) -> dict:
    return {
        "total": len(elementos),
        "mostrados": min(len(elementos), MAX_RESULTADOS),
        "elementos": [formato(e) for e in elementos[:MAX_RESULTADOS]],
    }


# --- Definiciones para la IA -------------------------------------------------------

_NULO_TEXTO = {"type": ["string", "null"]}


def _esquema(propiedades: dict, requeridas: list[str]) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": requeridas,
        "additionalProperties": False,
    }


DEFINICIONES: list[dict] = [
    {
        "name": "buscar_tareas",
        "description": "Busca tareas del usuario. Úsala antes de crear (para no duplicar), editar, cambiar estado o eliminar, y para responder preguntas sobre sus tareas.",
        "input_schema": _esquema(
            {
                "texto": {**_NULO_TEXTO, "description": "Palabras a buscar en título, descripción o cliente."},
                "estado": {"type": ["string", "null"], "enum": [*_ESTADOS, None]},
                "cliente": {**_NULO_TEXTO, "description": "Nombre del cliente."},
            },
            ["texto", "estado", "cliente"],
        ),
    },
    {
        "name": "resumen_tareas",
        "description": "Cantidad de tareas por estado y cuántas se terminaron hoy.",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "crear_tarea",
        "description": "Crea una tarea. Si ya existe una igual sin terminar, no la crea y devuelve la existente.",
        "input_schema": _esquema(
            {
                "titulo": {"type": "string"},
                "descripcion": _NULO_TEXTO,
                "cliente": {**_NULO_TEXTO, "description": "Nombre exacto de un cliente existente."},
                "importancia": {"type": ["string", "null"], "enum": [*_IMPORTANCIAS, None]},
                "estado": {"type": ["string", "null"], "enum": [*_ESTADOS, None]},
                "fecha_ingreso": {**_NULO_TEXTO, "description": "AAAA-MM-DD; si es null, hoy."},
            },
            ["titulo", "descripcion", "cliente", "importancia", "estado", "fecha_ingreso"],
        ),
    },
    {
        "name": "editar_tarea",
        "description": "Cambia cualquier dato de una tarea existente: título, descripción, cliente, importancia, estado, fecha de ingreso o fecha en que se terminó. Deja en null lo que no cambia; quitar_cliente=true la deja sin cliente.",
        "input_schema": _esquema(
            {
                "id": {"type": "integer"},
                "titulo": _NULO_TEXTO,
                "descripcion": _NULO_TEXTO,
                "cliente": _NULO_TEXTO,
                "quitar_cliente": {"type": "boolean"},
                "importancia": {"type": ["string", "null"], "enum": [*_IMPORTANCIAS, None]},
                "estado": {"type": ["string", "null"], "enum": [*_ESTADOS, None]},
                "fecha_ingreso": {**_NULO_TEXTO, "description": "AAAA-MM-DD"},
                "fecha_realizado": {**_NULO_TEXTO, "description": "AAAA-MM-DD HH:MM; solo si está Realizado"},
            },
            [
                "id", "titulo", "descripcion", "cliente", "quitar_cliente", "importancia", "estado",
                "fecha_ingreso", "fecha_realizado",
            ],
        ),
    },
    {
        "name": "cambiar_estado_tarea",
        "description": "Marca una tarea como Pendiente, En proceso o Realizado.",
        "input_schema": _esquema(
            {"id": {"type": "integer"}, "estado": {"type": "string", "enum": list(_ESTADOS)}},
            ["id", "estado"],
        ),
    },
    {
        "name": "eliminar_tareas",
        "description": "Elimina una o varias tareas (por ejemplo, todas las que pidió el usuario). Solo funciona si el usuario pidió eliminar en este mensaje. Se puede deshacer unos minutos.",
        "input_schema": _esquema(
            {"ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": _MAX_A_ELIMINAR}},
            ["ids"],
        ),
    },
    {
        "name": "buscar_notas",
        "description": "Busca notas y recordatorios. Úsala antes de crear uno (para no duplicar), editar o eliminar.",
        "input_schema": _esquema(
            {
                "texto": _NULO_TEXTO,
                "solo_recordatorios_pendientes": {"type": "boolean"},
            },
            ["texto", "solo_recordatorios_pendientes"],
        ),
    },
    {
        "name": "crear_nota",
        "description": "Crea una nota. Con «recordatorio» (AAAA-MM-DD HH:MM, hora local) Notivoz avisará a esa hora. Si ya existe una igual, no la crea y devuelve la existente.",
        "input_schema": _esquema(
            {"titulo": {"type": "string"}, "contenido": _NULO_TEXTO, "recordatorio": _NULO_TEXTO},
            ["titulo", "contenido", "recordatorio"],
        ),
    },
    {
        "name": "editar_nota",
        "description": "Cambia una nota o su recordatorio. Deja en null lo que no cambia; quitar_recordatorio=true lo borra.",
        "input_schema": _esquema(
            {
                "id": {"type": "integer"},
                "titulo": _NULO_TEXTO,
                "contenido": _NULO_TEXTO,
                "recordatorio": _NULO_TEXTO,
                "quitar_recordatorio": {"type": "boolean"},
            },
            ["id", "titulo", "contenido", "recordatorio", "quitar_recordatorio"],
        ),
    },
    {
        "name": "eliminar_notas",
        "description": "Elimina una o varias notas o recordatorios. Solo funciona si el usuario pidió eliminar en este mensaje. Se puede deshacer unos minutos.",
        "input_schema": _esquema(
            {"ids": {"type": "array", "items": {"type": "integer"}, "minItems": 1, "maxItems": _MAX_A_ELIMINAR}},
            ["ids"],
        ),
    },
    {
        "name": "deshacer_eliminacion",
        "description": "Recupera lo último que se eliminó (si fue hace pocos minutos).",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "leer_nota",
        "description": "Lee el contenido completo de una nota.",
        "input_schema": _esquema({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "leer_correo_tarea",
        "description": "Arma el correo de aviso al cliente de una tarea (el mismo que genera la app al marcarla como Realizada): devuelve asunto y cuerpo para leérselo al usuario. No lo envía.",
        "input_schema": _esquema({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "listar_rutinas",
        "description": "Lista las rutinas programadas (qué hacen, qué días y a qué hora).",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "ver_configuracion",
        "description": "Muestra la configuración actual de Notivoz (voz, personalidad, tema, inicio con Windows, avisos…). Solo lectura.",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "abrir_ventana",
        "description": "Abre la ventana de Notivoz (si estaba en la bandeja) y, si se indica, va a una sección.",
        "input_schema": _esquema(
            {"seccion": {"type": ["string", "null"], "enum": [*SECCIONES, None]}},
            ["seccion"],
        ),
    },
    {
        "name": "listar_clientes",
        "description": "Lista los clientes del usuario.",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "crear_cliente",
        "description": "Crea un cliente nuevo. Úsala solo si el usuario lo pide o lo confirma.",
        "input_schema": _esquema({"nombre": {"type": "string"}}, ["nombre"]),
    },
    {
        "name": "abrir_aplicacion",
        "description": "Abre una aplicación instalada en el equipo por su nombre (por ejemplo «Spotify»).",
        "input_schema": _esquema({"nombre": {"type": "string"}}, ["nombre"]),
    },
    {
        "name": "cerrar_aplicacion",
        "description": "Cierra una aplicación abierta (como al pulsar la X). Si no se cierra, Notivoz pregunta al usuario si quiere forzar el cierre: pregúntale «¿Quieres que la fuerce a cerrarse?».",
        "input_schema": _esquema({"nombre": {"type": "string"}}, ["nombre"]),
    },
    {
        "name": "listar_modos",
        "description": "Lista los modos o comandos de voz del usuario (por ejemplo «modo relax»).",
        "input_schema": _esquema({}, []),
    },
    {
        "name": "activar_modo",
        "description": "Activa un modo o comando de voz del usuario (abre sus apps). Notivoz anuncia el modo por su cuenta: no añadas más respuesta.",
        "input_schema": _esquema({"id": {"type": "integer"}}, ["id"]),
    },
    {
        "name": "cerrar_modo",
        "description": "Cierra las apps que abrió un modo o comando de voz.",
        "input_schema": _esquema({"id": {"type": "integer"}}, ["id"]),
    },
]

NOMBRES = {d["name"] for d in DEFINICIONES}
_DE_ESCRITURA = {
    "crear_tarea", "editar_tarea", "cambiar_estado_tarea", "eliminar_tareas", "crear_nota",
    "editar_nota", "eliminar_notas", "deshacer_eliminacion", "crear_cliente", "abrir_aplicacion",
    "cerrar_aplicacion", "activar_modo", "cerrar_modo",
}
# Acciones cuyo resultado no hace falta que la IA interprete: si salen bien, la
# frase que ella escribió junto con la acción basta (una llamada menos).
SIN_INTERPRETAR = {
    "crear_tarea", "editar_tarea", "cambiar_estado_tarea", "eliminar_tareas", "crear_nota",
    "editar_nota", "eliminar_notas", "deshacer_eliminacion", "crear_cliente", "abrir_aplicacion",
    "activar_modo", "abrir_ventana",
}


# --- Ejecución ---------------------------------------------------------------------


@dataclass
class AccionPendiente:
    """Forzar el cierre de una aplicación (podría perder cambios sin guardar):
    espera el «sí» del usuario."""

    titulo: str  # nombre de la aplicación
    vence: float
    procesos: frozenset[str] = frozenset()

    @property
    def vigente(self) -> bool:
        return time.monotonic() < self.vence

    def ejecutar(self) -> None:
        lanzador.cerrar_procesos(set(self.procesos), forzar=True)
        log.info("Cierre forzado confirmado por el usuario")


# --- Papelera: lo eliminado se puede recuperar unos minutos ---------------------------

_MINUTOS_PARA_DESHACER = 10
_papelera: dict[str, Any] = {}  # {"tipo", "filas", "titulo", "momento"}
_candado_papelera = threading.Lock()


def _a_la_papelera(tipo: str, elementos: list, titulo: str) -> None:
    columnas = {
        "tarea": ("titulo", "descripcion", "cliente_id", "importancia", "fecha_ingreso", "estado", "fecha_realizado"),
        "nota": ("titulo", "contenido", "recordatorio", "notificado", "creado_en"),
    }[tipo]
    with _candado_papelera:
        _papelera.clear()
        _papelera.update(
            tipo=tipo,
            filas=[{c: getattr(e, c) for c in columnas} for e in elementos],
            titulo=titulo,
            momento=time.monotonic(),
        )


def deshacer_ultima_eliminacion() -> tuple[str, str] | None:
    """Restaura lo último eliminado. Devuelve (tipo, título) o None si no hay nada."""
    from app.data.database import session_scope
    from app.data.models import Cliente, Nota, Pendiente

    with _candado_papelera:
        if not _papelera or time.monotonic() - _papelera["momento"] > _MINUTOS_PARA_DESHACER * 60:
            return None
        tipo, filas, titulo = _papelera["tipo"], _papelera["filas"], _papelera["titulo"]
        _papelera.clear()
    with session_scope() as s:
        for fila in filas:
            if tipo == "tarea":
                if fila["cliente_id"] is not None and s.get(Cliente, fila["cliente_id"]) is None:
                    fila = {**fila, "cliente_id": None}
                s.add(Pendiente(**fila))
            else:
                s.add(Nota(**fila))
    log.info("Eliminación deshecha: %d elementos", len(filas))
    return tipo, titulo


def hay_algo_para_deshacer() -> bool:
    with _candado_papelera:
        return bool(_papelera) and time.monotonic() - _papelera["momento"] <= _MINUTOS_PARA_DESHACER * 60


_PALABRAS_ELIMINAR = ("elimin", "borr", "quit", "limpi", "sac", "descart", "remov", "suprim", "deshaz")


def pidio_eliminar(pedido: str) -> bool:
    """¿El usuario pidió eliminar con sus palabras («elimina», «bórralas»…)?"""
    texto = normalizar(pedido)
    return any(p in texto for p in _PALABRAS_ELIMINAR)


@dataclass
class Efectos:
    """Lo que cambió en un turno, para refrescar la interfaz y avisar."""

    tareas: bool = False
    notas: bool = False
    comandos_activados: list[int] = field(default_factory=list)
    comandos_cerrados: list[str] = field(default_factory=list)  # frases a decir
    eliminado: str = ""  # lo que se eliminó, para el aviso flotante (con Deshacer)
    restaurado: str = ""  # lo que se recuperó
    abrir_ventana: str | None = None  # "" = solo mostrarla; si no, la sección


class Herramientas:
    def __init__(self, frases_actuales: Callable[[], Frases]):
        # Para cerrar modos con las frases de la personalidad elegida.
        self._frases_actuales = frases_actuales
        self.pendiente: AccionPendiente | None = None
        # Lo que dijo el usuario en este pedido (para comprobar que pidió eliminar).
        self.ultimo_pedido = ""
        self.efectos = Efectos()
        self._cambios_turno = 0
        # Apps que abrió la IA en esta sesión: nombre normalizado → procesos.
        self._abiertas: dict[str, set[str]] = {}

    def nuevo_turno(self) -> None:
        self._cambios_turno = 0
        self.efectos = Efectos()
        # Un pedido nuevo deja sin efecto un cierre forzado que no se confirmó.
        self.pendiente = None

    def ejecutar(self, nombre: str, entrada: Any) -> tuple[str, bool]:
        """Devuelve (resultado en JSON, ¿es error?)."""
        if nombre not in NOMBRES:
            return json.dumps({"error": "Herramienta desconocida."}), True
        if not isinstance(entrada, dict):
            return json.dumps({"error": "Datos inválidos."}), True
        if nombre in _DE_ESCRITURA:
            if self._cambios_turno >= MAX_CAMBIOS_POR_TURNO:
                return json.dumps(
                    {"error": "Límite de cambios por pedido alcanzado. Pide al usuario que lo haga en otro pedido."}
                ), True
            self._cambios_turno += 1
        try:
            resultado = getattr(self, f"_h_{nombre}")(entrada)
            log.info("IA usó la herramienta %s", nombre)
            return json.dumps(resultado, ensure_ascii=False, default=str), False
        except ErrorHerramienta as error:
            return json.dumps({"error": str(error)}, ensure_ascii=False), True
        except ValueError as error:  # validaciones de los servicios
            return json.dumps({"error": str(error)}, ensure_ascii=False), True
        except Exception:
            log.exception("Error al ejecutar la herramienta %s", nombre)
            return json.dumps({"error": "No se pudo completar la acción."}), True

    # --- Tareas ---

    def _cliente_id(self, nombre: str | None) -> int | None:
        if nombre is None:
            return None
        clientes = servicio_clientes.listar()
        cliente = cliente_parecido(nombre, clientes)
        if cliente is not None:
            return cliente.id
        raise ErrorHerramienta(
            f"No existe el cliente «{nombre}» ni uno parecido. Clientes: "
            f"{', '.join(c.nombre for c in clientes) or 'ninguno'}. Pregunta al usuario si quiere crearlo."
        )

    def _h_buscar_tareas(self, entrada: dict) -> dict:
        filtro = FiltroPendientes(
            texto=_texto(entrada, "texto", _LARGO_BUSQUEDA) or "",
            estado=_opcion(entrada, "estado", _ESTADOS),
            cliente_id=self._cliente_id(_texto(entrada, "cliente", _LARGO_NOMBRE)),
        )
        return _lista(servicio_pendientes.listar(filtro), _tarea)

    def _h_resumen_tareas(self, _entrada: dict) -> dict:
        conteo = servicio_pendientes.resumen()
        dia = servicio_pendientes.resumen_del_dia()
        return {
            "por_estado": {estado.value: total for estado, total in conteo.items()},
            "terminadas_hoy": len(dia.realizadas),
            "racha_dias": dia.racha,
            "sugerencias_de_subir_importancia": [
                {"tarea": servicio_pendientes.obtener(i).titulo, "sugerida": imp.etiqueta}
                for i, imp in list(servicio_pendientes.sugerencias_prioridad().items())[:10]
            ],
        }

    def _h_crear_tarea(self, entrada: dict) -> dict:
        titulo = _texto(entrada, "titulo", _LARGO_TITULO, obligatorio=True)
        cliente_id = self._cliente_id(_texto(entrada, "cliente", _LARGO_NOMBRE))
        for p in servicio_pendientes.listar(FiltroPendientes(cliente_id=cliente_id)):
            if p.estado != Estado.REALIZADO and normalizar(p.titulo) == normalizar(titulo):
                return {"creada": False, "motivo": "ya_existe", "tarea": _tarea(p)}
        nuevo_id = servicio_pendientes.guardar(
            DatosPendiente(
                titulo=titulo,
                descripcion=_texto(entrada, "descripcion", _LARGO_DESCRIPCION) or "",
                cliente_id=cliente_id,
                importancia=_opcion(entrada, "importancia", _IMPORTANCIAS) or Importancia.MEDIA,
                estado=_opcion(entrada, "estado", _ESTADOS) or Estado.PENDIENTE,
                fecha_ingreso=_fecha(entrada, "fecha_ingreso") or date.today(),
            )
        )
        self.efectos.tareas = True
        return {"creada": True, "tarea": _tarea(servicio_pendientes.obtener(nuevo_id))}

    def _tarea_existente(self, entrada: dict):
        tarea = servicio_pendientes.obtener(_id(entrada))
        if tarea is None:
            raise ErrorHerramienta("No existe una tarea con ese id. Búscala primero.")
        return tarea

    def _h_editar_tarea(self, entrada: dict) -> dict:
        tarea = self._tarea_existente(entrada)
        cliente = _texto(entrada, "cliente", _LARGO_NOMBRE)
        if _booleano(entrada, "quitar_cliente"):
            cliente_id = None
        else:
            cliente_id = self._cliente_id(cliente) if cliente else tarea.cliente_id
        estado = _opcion(entrada, "estado", _ESTADOS) or Estado(tarea.estado)
        fecha_realizado = _fecha_hora(entrada, "fecha_realizado", pasado=True)
        if fecha_realizado is not None and estado != Estado.REALIZADO:
            raise ErrorHerramienta("La fecha en que se terminó solo vale para tareas Realizadas.")
        servicio_pendientes.guardar(
            DatosPendiente(
                id=tarea.id,
                titulo=_texto(entrada, "titulo", _LARGO_TITULO) or tarea.titulo,
                descripcion=_texto(entrada, "descripcion", _LARGO_DESCRIPCION) or tarea.descripcion,
                cliente_id=cliente_id,
                importancia=_opcion(entrada, "importancia", _IMPORTANCIAS) or Importancia(tarea.importancia),
                fecha_ingreso=_fecha(entrada, "fecha_ingreso") or tarea.fecha_ingreso,
                estado=estado,
            )
        )
        if fecha_realizado is not None:
            servicio_pendientes.cambiar_fecha_realizado(tarea.id, fecha_realizado)
        self.efectos.tareas = True
        return {"editada": True, "tarea": _tarea(servicio_pendientes.obtener(tarea.id))}

    def _h_cambiar_estado_tarea(self, entrada: dict) -> dict:
        tarea = self._tarea_existente(entrada)
        estado = _opcion(entrada, "estado", _ESTADOS)
        if estado is None:
            raise ErrorHerramienta("Falta «estado».")
        if tarea.estado == estado:
            return {"cambiado": False, "motivo": f"ya estaba «{estado.value}»", "tarea": _tarea(tarea)}
        servicio_pendientes.cambiar_estado(tarea.id, estado)
        self.efectos.tareas = True
        return {"cambiado": True, "tarea": _tarea(servicio_pendientes.obtener(tarea.id))}

    def _ids(self, entrada: dict) -> list[int]:
        ids = entrada.get("ids")
        if not isinstance(ids, list) or not ids or len(ids) > _MAX_A_ELIMINAR:
            raise ErrorHerramienta(f"«ids» debe ser una lista de 1 a {_MAX_A_ELIMINAR} ids.")
        return list(dict.fromkeys(_id({"id": i}) for i in ids))

    def _eliminar(self, tipo: str, elementos: list) -> dict:
        if not pidio_eliminar(self.ultimo_pedido):
            raise ErrorHerramienta(
                "Solo se elimina si el usuario lo pide con sus palabras en este mensaje. Pregúntale si quiere eliminarlo."
            )
        nombre = "tarea" if tipo == "tarea" else "nota"
        titulo = elementos[0].titulo if len(elementos) == 1 else f"{len(elementos)} {nombre}s"
        _a_la_papelera(tipo, elementos, titulo)
        eliminar = servicio_pendientes.eliminar if tipo == "tarea" else servicio_notas.eliminar
        for elemento in elementos:
            eliminar(elemento.id)
        if tipo == "tarea":
            self.efectos.tareas = True
        else:
            self.efectos.notas = True
        self.efectos.eliminado = titulo
        log.info("Eliminados %d elementos (%s)", len(elementos), tipo)
        return {"eliminadas": True, "cantidad": len(elementos), "se_puede_deshacer": True}

    def _h_eliminar_tareas(self, entrada: dict) -> dict:
        tareas = [self._tarea_existente({"id": i}) for i in self._ids(entrada)]
        return self._eliminar("tarea", tareas)

    def _h_deshacer_eliminacion(self, _entrada: dict) -> dict:
        restaurado = deshacer_ultima_eliminacion()
        if restaurado is None:
            raise ErrorHerramienta("No hay nada reciente para recuperar.")
        tipo, titulo = restaurado
        if tipo == "tarea":
            self.efectos.tareas = True
        else:
            self.efectos.notas = True
        self.efectos.restaurado = titulo
        return {"restaurado": True, "que": titulo}

    # --- Notas ---

    def _nota_existente(self, entrada: dict):
        nota = servicio_notas.obtener(_id(entrada))
        if nota is None:
            raise ErrorHerramienta("No existe una nota con ese id. Búscala primero.")
        return nota

    def _h_buscar_notas(self, entrada: dict) -> dict:
        filtro = (
            servicio_notas.FiltroNotas.PROXIMAS
            if _booleano(entrada, "solo_recordatorios_pendientes")
            else servicio_notas.FiltroNotas.TODAS
        )
        notas = servicio_notas.listar(_texto(entrada, "texto", _LARGO_BUSQUEDA) or "", filtro)
        return _lista(notas, _nota)

    def _h_crear_nota(self, entrada: dict) -> dict:
        titulo = _texto(entrada, "titulo", _LARGO_TITULO, obligatorio=True)
        recordatorio = _fecha_hora(entrada, "recordatorio")
        for n in servicio_notas.listar():
            mismo_titulo = normalizar(n.titulo) == normalizar(titulo)
            if not mismo_titulo:
                continue
            # Mismo recordatorio pendiente, o la misma nota sin recordatorio.
            if (recordatorio is None and n.recordatorio is None) or (
                servicio_notas.es_proxima(n)
                and recordatorio is not None
                and abs((n.recordatorio - recordatorio).total_seconds()) < 3600
            ):
                return {"creada": False, "motivo": "ya_existe", "nota": _nota(n)}
        nuevo_id = servicio_notas.guardar(
            DatosNota(
                titulo=titulo,
                contenido=_texto(entrada, "contenido", _LARGO_CONTENIDO) or "",
                recordatorio=recordatorio,
            )
        )
        self.efectos.notas = True
        return {"creada": True, "nota": _nota(servicio_notas.obtener(nuevo_id))}

    def _h_editar_nota(self, entrada: dict) -> dict:
        nota = self._nota_existente(entrada)
        recordatorio = _fecha_hora(entrada, "recordatorio")
        if _booleano(entrada, "quitar_recordatorio"):
            recordatorio = None
        elif recordatorio is None:
            recordatorio = nota.recordatorio
        servicio_notas.guardar(
            DatosNota(
                id=nota.id,
                titulo=_texto(entrada, "titulo", _LARGO_TITULO) or nota.titulo,
                contenido=_texto(entrada, "contenido", _LARGO_CONTENIDO) or nota.contenido,
                recordatorio=recordatorio,
            )
        )
        self.efectos.notas = True
        return {"editada": True, "nota": _nota(servicio_notas.obtener(nota.id))}

    def _h_eliminar_notas(self, entrada: dict) -> dict:
        notas = [self._nota_existente({"id": i}) for i in self._ids(entrada)]
        return self._eliminar("nota", notas)

    def _h_leer_nota(self, entrada: dict) -> dict:
        nota = self._nota_existente(entrada)
        datos = _nota(nota)
        datos["contenido"] = nota.contenido[:_LARGO_CONTENIDO]
        return datos

    # --- Lectura del resto de la app ---

    def _h_leer_correo_tarea(self, entrada: dict) -> dict:
        tarea = self._tarea_existente(entrada)
        correo = RedactorCorreo(tarea, ajustes.obtener(Clave.NOMBRE)).otra_version()
        aviso = "" if tarea.estado == Estado.REALIZADO else "La tarea aún no está marcada como Realizada."
        return {"tarea": tarea.titulo, "asunto": correo.asunto, "cuerpo": correo.cuerpo, "aviso": aviso}

    def _h_listar_rutinas(self, _entrada: dict) -> dict:
        acciones = {
            "leer_pendientes": "leer tus pendientes",
            "resumen_dia": "decir el resumen del día",
            "ejecutar_comando": "activar un modo",
        }
        return {
            "rutinas": [
                {
                    "nombre": r.nombre,
                    "accion": acciones.get(r.accion, r.accion)
                    + (f" «{r.comando.frase}»" if r.comando is not None else ""),
                    "dias": servicio_rutinas.describir_dias(servicio_rutinas.dias_de(r)),
                    "hora": r.hora,
                    "activa": r.activo,
                }
                for r in servicio_rutinas.listar()[:50]
            ]
        }

    def _h_ver_configuracion(self, _entrada: dict) -> dict:
        from app.services import inicio_windows

        a = ajustes.obtener
        return {
            "tu_nombre": a(Clave.NOMBRE),
            "personalidad": a(Clave.PERSONALIDAD),
            "voz": a(Clave.VOZ_NOMBRE) or "voz de Windows",
            "velocidad_voz": a(Clave.VOZ_VELOCIDAD),
            "volumen_voz": a(Clave.VOZ_VOLUMEN),
            "tema": a(Clave.TEMA),
            "iniciar_con_windows": inicio_windows.esta_activo(),
            "arrancar_en_bandeja": a(Clave.INICIAR_EN_BANDEJA),
            "leer_pendientes_al_iniciar": a(Clave.LEER_AL_INICIAR),
            "cerrar_a_bandeja": a(Clave.CERRAR_A_BANDEJA),
            "celebrar_racha": a(Clave.CELEBRAR_RACHA),
            "resumen_al_apagar": a(Clave.RESUMEN_AL_APAGAR),
            "aviso_apps_de_ocio": a(Clave.AVISO_OCIO),
            "horario_de_trabajo": f"{a(Clave.HORARIO_INICIO)} a {a(Clave.HORARIO_FIN)}",
        }

    def _h_abrir_ventana(self, entrada: dict) -> dict:
        seccion = _opcion(entrada, "seccion", {s: s for s in SECCIONES})
        self.efectos.abrir_ventana = seccion or ""
        return {"abierta": True, "seccion": seccion}

    # --- Clientes ---

    def _h_listar_clientes(self, _entrada: dict) -> dict:
        return {"clientes": [c.nombre for c in servicio_clientes.listar()][:100]}

    def _h_crear_cliente(self, entrada: dict) -> dict:
        nombre = _texto(entrada, "nombre", _LARGO_NOMBRE, obligatorio=True)
        servicio_clientes.crear(nombre)
        self.efectos.tareas = True
        return {"creado": True, "cliente": nombre}

    # --- Aplicaciones ---

    @staticmethod
    def _bloqueada(nombre_app: str) -> bool:
        normal = normalizar(nombre_app)
        palabras = set(normal.split())
        return any(b in palabras or (" " in b and b in normal) for b in _APPS_BLOQUEADAS)

    def _buscar_app(self, nombre: str) -> tuple[str, str]:
        buscado = normalizar(nombre)
        if len(buscado) < 2:
            raise ErrorHerramienta("Nombre de aplicación demasiado corto.")
        apps = [(n, d) for n, d in lanzador.apps_instaladas() if not self._bloqueada(n)]
        exactas = [a for a in apps if normalizar(a[0]) == buscado]
        if exactas:
            return exactas[0]
        parecidas = [a for a in apps if buscado in normalizar(a[0])]
        if len(parecidas) == 1:
            return parecidas[0]
        if len(parecidas) > 1:
            raise ErrorHerramienta(
                "Hay varias aplicaciones parecidas: "
                + ", ".join(n for n, _ in parecidas[:8])
                + ". Pregunta al usuario cuál."
            )
        raise ErrorHerramienta(f"No encontré «{nombre}» entre las aplicaciones instaladas.")

    def _h_abrir_aplicacion(self, entrada: dict) -> dict:
        nombre_app, destino = self._buscar_app(_texto(entrada, "nombre", _LARGO_NOMBRE, obligatorio=True))
        # Solo destinos del menú Inicio (shell:AppsFolder\…): nunca rutas ni comandos.
        if not destino.startswith("shell:AppsFolder\\"):
            raise ErrorHerramienta("Esa aplicación no se puede abrir.")
        resultado = lanzador.abrir_y_esperar([destino])
        if resultado.fallidos:
            raise ErrorHerramienta(f"Windows no pudo abrir {nombre_app}.")
        if resultado.procesos_nuevos:
            self._abiertas[normalizar(nombre_app)] = set(resultado.procesos_nuevos)
        return {"abierta": True, "aplicacion": nombre_app}

    def _h_cerrar_aplicacion(self, entrada: dict) -> dict:
        nombre = _texto(entrada, "nombre", _LARGO_NOMBRE, obligatorio=True)
        buscado = normalizar(nombre)
        procesos: set[str] = set()
        for abierta, suyos in self._abiertas.items():
            if buscado in abierta:
                procesos |= suyos
        if not procesos and len(buscado) >= 3:
            ventanas = lanzador.ventanas_visibles()
            # Programas cuyo ejecutable se llama como la app («spotify.exe»)…
            clave = buscado.replace(" ", "")
            procesos = {exe for exe, _ in ventanas if clave in exe.lower()}
            if not procesos:
                # …o cuya ventana termina con su nombre («Sin título - Bloc de notas»).
                # Solo al final del título: así una pestaña del navegador que dice
                # «Spotify» no cierra el navegador.
                procesos = {exe for exe, titulo in ventanas if normalizar(titulo).endswith(buscado)}
        procesos.discard(_PROPIO)
        procesos = {p for p in procesos if not self._bloqueada(p.removesuffix(".exe"))}
        abiertos = set(lanzador.procesos_en_ejecucion().values())
        procesos = {p for p in procesos if p in abiertos}
        if not procesos:
            return {"cerrada": False, "motivo": f"No encontré «{nombre}» abierta."}
        lanzador.cerrar_procesos(procesos)
        # Comprobar que de verdad se cerró (algunas apps ignoran el pedido amable).
        siguen = lanzador.esperar_cierre(procesos)
        if not siguen:
            return {"cerrada": True, "aplicacion": nombre}
        self.pendiente = AccionPendiente(nombre, time.monotonic() + SEGUNDOS_PARA_CONFIRMAR, frozenset(siguen))
        return {
            "cerrada": False,
            "motivo": "La aplicación no se cerró (puede seguir en segundo plano o tener cambios sin guardar).",
            "requiere_confirmacion_del_usuario_para_forzar": True,
        }

    # --- Modos (comandos de voz) ---

    def _h_listar_modos(self, _entrada: dict) -> dict:
        return {
            "modos": [
                {"id": c.id, "frase": c.frase, "activo": c.activo, "apps": [a.nombre for a in c.apps][:10]}
                for c in servicio_comandos.listar()[:50]
            ]
        }

    def _modo(self, entrada: dict):
        comando = servicio_comandos.obtener(_id(entrada))
        if comando is None:
            raise ErrorHerramienta("No existe ese modo. Usa listar_modos.")
        return comando

    def _h_activar_modo(self, entrada: dict) -> dict:
        comando = self._modo(entrada)
        if not comando.activo:
            raise ErrorHerramienta(f"El modo «{comando.frase}» está desactivado.")
        self.efectos.comandos_activados.append(comando.id)
        return {"activado": True, "modo": comando.frase, "nota": "Notivoz lo anuncia por su cuenta."}

    def _h_cerrar_modo(self, entrada: dict) -> dict:
        comando = self._modo(entrada)
        frase = servicio_comandos.cerrar(comando.id, self._frases_actuales())
        return {"cerrado": True, "modo": comando.frase, "resultado": frase}


# --- Confirmaciones rápidas (sin gastar IA) ---------------------------------------

_SI = set("""
si sip sii simon claro dale ok okay okey vale va listo ya bueno exacto correcto
afirmativo confirmo confirmado adelante procede hazlo obvio seguro porfa
elimina eliminalo eliminala eliminalos eliminalas borra borralo borrala borralos borralas
""".split())
_NO_AL_INICIO = {"no", "nop", "nel", "cancela", "cancelar", "espera", "mejor", "olvidalo", "olvidala", "deja", "detente"}
_NO = {"no", "nop", "nel", "cancela", "cancelar"}


def respuesta_confirmacion(texto: str) -> bool | None:
    """True = el usuario confirma, False = no, None = no está claro (lo decide la IA).

    Solo respuestas cortas se resuelven aquí: «sí, dale» confirma; «no» o «mejor
    no» cancelan. Algo como «sí, total ya las terminé» queda para la IA."""
    palabras = normalizar(texto).replace(",", " ").replace(".", " ").replace("!", " ").replace("?", " ").split()
    if not palabras:
        return None
    if palabras[0] in _NO_AL_INICIO or (len(palabras) <= 4 and set(palabras) & _NO):
        return False
    if len(palabras) <= 6 and set(palabras) & _SI and not set(palabras) & _NO:
        return True
    return None


def fecha_de_hoy_texto() -> str:
    hoy = date.today()
    return f"{datetime.now().strftime(_FORMATO_FECHA_HORA)} ({['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'][hoy.weekday()]})"

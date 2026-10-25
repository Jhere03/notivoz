"""Lógica de negocio de los comandos de voz."""

import logging
import re
import threading
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.database import session_scope
from app.data.models import Comando, ComandoApp
from app.services import lanzador
from app.services.personalidad import Frases
from app.services.voz import voz

log = logging.getLogger(__name__)


@dataclass
class DatosApp:
    nombre: str
    destino: str


@dataclass
class DatosComando:
    frase: str
    apps: list[DatosApp] = field(default_factory=list)
    respuesta: str = ""
    activo: bool = True
    id: int | None = None


def normalizar_frase(texto: str) -> str:
    """'¡Modo  trabajo!' → 'modo trabajo' (minúsculas, sin signos; se conservan tildes y ñ)."""
    texto = re.sub(r"[^\w\s]", " ", texto.lower())
    return " ".join(texto.split())


def respuesta_de(comando: Comando, frases: Frases) -> str:
    """La respuesta propia del comando o, si no tiene, una según la personalidad
    y el tipo de modo («¡A chambear!», «¡A relajarse!»…)."""
    if comando.respuesta.strip():
        return comando.respuesta.strip()
    return frases.comando_activado(comando.frase, [app.nombre for app in comando.apps])


def listar() -> list[Comando]:
    stmt = select(Comando).options(selectinload(Comando.apps)).order_by(Comando.frase)
    with session_scope() as s:
        return list(s.scalars(stmt))


def frases_activas() -> dict[str, int]:
    """frase normalizada → id, solo de los comandos activos con al menos una app."""
    return {c.frase: c.id for c in listar() if c.activo and c.apps}


def obtener(comando_id: int) -> Comando | None:
    stmt = select(Comando).options(selectinload(Comando.apps)).where(Comando.id == comando_id)
    with session_scope() as s:
        return s.scalars(stmt).first()


def guardar(datos: DatosComando) -> int:
    frase = normalizar_frase(datos.frase)
    if not frase:
        raise ValueError("Escribe la frase que vas a decir.")
    if not datos.apps:
        raise ValueError("Agrega al menos una aplicación para abrir.")
    with session_scope() as s:
        repetido = s.scalars(
            select(Comando.id).where(Comando.frase == frase, Comando.id != (datos.id or -1))
        ).first()
        if repetido is not None:
            raise ValueError(f"Ya existe un comando con la frase «{frase}».")
        if datos.id is None:
            comando = Comando()
            s.add(comando)
        else:
            comando = s.get(Comando, datos.id)
            if comando is None:
                raise ValueError("El comando ya no existe.")
        comando.frase = frase
        comando.respuesta = datos.respuesta.strip()
        comando.activo = datos.activo
        comando.apps = [
            ComandoApp(nombre=app.nombre.strip() or app.destino, destino=app.destino.strip(), orden=i)
            for i, app in enumerate(datos.apps)
        ]
        s.flush()
        return comando.id


def cambiar_activo(comando_id: int, activo: bool) -> None:
    with session_scope() as s:
        comando = s.get(Comando, comando_id)
        if comando is not None:
            comando.activo = activo


def eliminar(comando_id: int) -> None:
    with session_scope() as s:
        comando = s.get(Comando, comando_id)
        if comando is not None:
            s.delete(comando)


def ejecutar(comando_id: int, frases: Frases) -> None:
    """Abre todas las apps del comando en segundo plano y, cuando están listas,
    lo anuncia en voz alta («Modo trabajo activado»). Recuerda qué procesos
    abrió, para poder cerrarlos después."""
    comando = obtener(comando_id)
    if comando is None:
        return
    destinos = [app.destino for app in comando.apps]
    respuesta = respuesta_de(comando, frases)

    def trabajar() -> None:
        log.info("Ejecutando comando «%s» (%d apps)", comando.frase, len(destinos))
        resultado = lanzador.abrir_y_esperar(destinos)
        if resultado.procesos_nuevos:
            # Si todo ya estaba abierto no hay nada nuevo: se conserva lo aprendido antes.
            _guardar_procesos(comando_id, resultado.procesos_nuevos)
        fallidos = resultado.fallidos
        if fallidos and len(fallidos) == len(destinos):
            voz().hablar(f"No pude abrir las aplicaciones de {comando.frase}.")
            return
        voz().hablar(respuesta)
        if fallidos:
            voz().hablar(f"No pude abrir {len(fallidos)} de ellas.")

    threading.Thread(target=trabajar, name="Comando", daemon=True).start()


def procesos_de(comando: Comando) -> set[str]:
    return {p for p in comando.procesos.split(";") if p}


def _guardar_procesos(comando_id: int, procesos: set[str]) -> None:
    with session_scope() as s:
        comando = s.get(Comando, comando_id)
        if comando is not None:
            comando.procesos = ";".join(sorted(procesos))


def cerrar(comando_id: int, frases: Frases) -> str:
    """Cierra (amablemente) lo que el comando abrió. Devuelve la frase a decir."""
    comando = obtener(comando_id)
    if comando is None:
        return ""
    cerrados = lanzador.cerrar_procesos(procesos_de(comando))
    log.info("Comando «%s» cerrado: %d programas", comando.frase, cerrados)
    clave = "comando_cerrado" if cerrados else "comando_nada_que_cerrar"
    return frases.frase(clave, modo=comando.frase.capitalize())

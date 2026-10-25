"""Redacción por plantillas: textos formales y fechas en español."""

import random
from dataclasses import dataclass
from datetime import date, datetime

from app.data.models import Pendiente

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fecha_larga(fecha: date | datetime) -> str:
    """date(2026, 10, 25) → '25 de octubre de 2026'."""
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def saludo_hora(ahora: datetime | None = None) -> str:
    hora = (ahora or datetime.now()).hour
    if 5 <= hora < 12:
        return "Buenos días"
    if 12 <= hora < 19:
        return "Buenas tardes"
    return "Buenas noches"


def tras_dos_puntos(texto: str) -> str:
    """En español, tras dos puntos va minúscula: 'Incluir…' → 'incluir…'.
    Las siglas se respetan ('API', 'SUNAT')."""
    texto = texto.strip()
    primera = texto.split(" ", 1)[0]
    if len(primera) > 1 and primera.isupper():
        return texto
    return texto[:1].lower() + texto[1:]


def con_punto(texto: str) -> str:
    texto = texto.strip()
    return texto if not texto or texto[-1] in ".!?" else f"{texto}."


# --- Correo de tarea realizada --------------------------------------------------

_ASUNTOS = [
    "Tarea culminada: {titulo}",
    "Finalización de la tarea: {titulo}",
    "Confirmación de tarea realizada: {titulo}",
    "{titulo}: tarea completada",
]
_APERTURAS = [
    "Por medio del presente, le informo que",
    "Le escribo para informarle que",
    "Me complace informarle que",
    "Le comunico que",
]
_CULMINADA = [
    "ha sido culminada con éxito",
    "se completó satisfactoriamente",
    "quedó finalizada con éxito",
    "fue concluida satisfactoriamente",
]
_INTRO_DETALLE = [
    "Como detalle de lo realizado:",
    "Para su referencia, el trabajo comprendió lo siguiente:",
    "En resumen, se trabajó en lo siguiente:",
]
_CIERRES = [
    "Quedo atento a cualquier consulta u observación.",
    "Quedo a su disposición para cualquier consulta adicional.",
    "Cualquier comentario o ajuste adicional, no dude en escribirme.",
    "Agradezco su confianza y quedo atento a sus comentarios.",
]


@dataclass(frozen=True)
class Correo:
    asunto: str
    cuerpo: str


class RedactorCorreo:
    """Arma el correo de una tarea realizada. Cada llamada a `otra_version()`
    cambia las frases, sin repetir la versión anterior."""

    def __init__(self, pendiente: Pendiente, firma: str, semilla: int | None = None):
        self._pendiente = pendiente
        self._firma = firma.strip()
        self._azar = random.Random(semilla)
        self._ultima: tuple[int, ...] | None = None

    def otra_version(self, ahora: datetime | None = None) -> Correo:
        opciones = (_ASUNTOS, _APERTURAS, _CULMINADA, _INTRO_DETALLE, _CIERRES)
        while True:
            eleccion = tuple(self._azar.randrange(len(o)) for o in opciones)
            if eleccion != self._ultima:
                break
        self._ultima = eleccion
        asunto, apertura, culminada, intro, cierre = (o[i] for o, i in zip(opciones, eleccion))

        p = self._pendiente
        titulo = p.titulo.strip().rstrip(".")
        cliente = p.cliente.nombre if p.cliente else ""
        fecha = p.fecha_realizado or datetime.now()

        parrafos = [
            f"{saludo_hora(ahora)}, {cliente}:" if cliente else f"{saludo_hora(ahora)}:",
            f"{apertura} la tarea «{titulo}» {culminada} el día {fecha_larga(fecha)}.",
        ]
        if p.descripcion.strip():
            parrafos.append(f"{intro} {tras_dos_puntos(con_punto(p.descripcion))}")
        parrafos.append(cierre)
        parrafos.append("Saludos cordiales," + (f"\n{self._firma}" if self._firma else ""))
        return Correo(asunto=asunto.format(titulo=titulo), cuerpo="\n\n".join(parrafos))

"""Preferencias del usuario guardadas en la base de datos."""

import json
from enum import StrEnum
from typing import Any

from app.data.database import session_scope
from app.data.models import Ajuste
from app.services.voz import VOZ_POR_DEFECTO


class Clave(StrEnum):
    LEER_AL_INICIAR = "leer_al_iniciar"
    INICIAR_EN_BANDEJA = "iniciar_en_bandeja"
    CERRAR_A_BANDEJA = "cerrar_a_bandeja"
    AVISO_BANDEJA_MOSTRADO = "aviso_bandeja_mostrado"
    NOMBRE = "nombre"
    VOZ_VELOCIDAD = "voz_velocidad"
    VOZ_VOLUMEN = "voz_volumen"
    VOZ_NOMBRE = "voz_nombre"
    ESCUCHA_ACTIVA = "escucha_activa"
    MICROFONO = "microfono"


_POR_DEFECTO: dict[Clave, Any] = {
    Clave.LEER_AL_INICIAR: True,
    Clave.INICIAR_EN_BANDEJA: True,
    Clave.CERRAR_A_BANDEJA: True,
    Clave.AVISO_BANDEJA_MOSTRADO: False,
    Clave.NOMBRE: "",
    Clave.VOZ_VELOCIDAD: 0,  # SAPI: de -10 (lento) a 10 (rápido)
    Clave.VOZ_VOLUMEN: 100,  # 0 a 100
    Clave.VOZ_NOMBRE: VOZ_POR_DEFECTO,  # "" = solo la voz de Windows
    Clave.ESCUCHA_ACTIVA: False,  # el micrófono solo se enciende si el usuario lo pide
    Clave.MICROFONO: "",  # "" = el predeterminado de Windows
}


def obtener(clave: Clave) -> Any:
    with session_scope() as s:
        fila = s.get(Ajuste, str(clave))
        if fila is None:
            return _POR_DEFECTO[clave]
        try:
            return json.loads(fila.valor)
        except ValueError:
            return _POR_DEFECTO[clave]


def guardar(clave: Clave, valor: Any) -> None:
    with session_scope() as s:
        s.merge(Ajuste(clave=str(clave), valor=json.dumps(valor)))

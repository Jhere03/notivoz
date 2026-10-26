"""Clave del API de Claude, guardada en el Administrador de credenciales de Windows.

La clave nunca se escribe en el código, en la base de datos, en los ajustes ni
en el registro de la app: Windows la cifra con la cuenta del usuario (DPAPI),
así que otra cuenta del equipo no puede leerla. Notivoz no trae ninguna clave
incluida; cada persona usa la suya.
"""

import logging
import re

log = logging.getLogger(__name__)

_SERVICIO = "Notivoz"
_USUARIO = "anthropic_api_key"
# Formato de las claves de Anthropic. Se valida antes de guardar para no
# almacenar texto arbitrario pegado por error.
_FORMATO = re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,200}$")


def formato_valido(clave: str) -> bool:
    return bool(_FORMATO.match(clave.strip()))


def guardar(clave: str) -> None:
    import keyring

    clave = clave.strip()
    if not formato_valido(clave):
        raise ValueError("La clave no tiene el formato de una clave de Anthropic (sk-ant-…).")
    keyring.set_password(_SERVICIO, _USUARIO, clave)
    log.info("Clave del API guardada en el Administrador de credenciales.")


def obtener() -> str | None:
    import keyring

    try:
        return keyring.get_password(_SERVICIO, _USUARIO)
    except Exception:
        log.warning("No se pudo leer el Administrador de credenciales.")
        return None


def borrar() -> None:
    import keyring
    from keyring.errors import PasswordDeleteError

    try:
        keyring.delete_password(_SERVICIO, _USUARIO)
    except PasswordDeleteError:
        pass
    log.info("Clave del API borrada.")


def hay_clave() -> bool:
    return bool(obtener())


def pista() -> str:
    """Solo los últimos 4 caracteres, para mostrar qué clave hay sin revelarla."""
    clave = obtener()
    return f"sk-ant-…{clave[-4:]}" if clave else ""

"""Rutinas automáticas: acciones que Notivoz hace solo, ciertos días a cierta hora."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.data.database import session_scope
from app.data.models import AccionRutina, Comando, Rutina

DIAS_CORTOS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
# Si la PC estaba apagada a la hora de la rutina, se ejecuta al encenderla
# solo si no pasó más de este tiempo (abrir apps horas tarde sorprendería).
TOLERANCIA = timedelta(minutes=60)


@dataclass
class DatosRutina:
    nombre: str
    accion: AccionRutina = AccionRutina.LEER_PENDIENTES
    dias: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    hora: time = time(9, 0)
    comando_id: int | None = None
    activo: bool = True
    id: int | None = None


def dias_de(rutina: Rutina) -> list[int]:
    return sorted({int(d) for d in rutina.dias.split(",") if d.strip().isdigit()})


def hora_de(rutina: Rutina) -> time:
    horas, minutos = rutina.hora.split(":")
    return time(int(horas), int(minutos))


def describir_dias(dias: list[int]) -> str:
    """[0..4] → 'Lunes a viernes'; todos → 'Todos los días'; si no, 'Lun, Mié, Vie'."""
    dias = sorted(set(dias))
    if dias == list(range(7)):
        return "Todos los días"
    if dias == list(range(5)):
        return "Lunes a viernes"
    if dias == [5, 6]:
        return "Fines de semana"
    return ", ".join(DIAS_CORTOS[d] for d in dias)


def listar() -> list[Rutina]:
    stmt = select(Rutina).options(selectinload(Rutina.comando)).order_by(Rutina.hora, Rutina.nombre)
    with session_scope() as s:
        return list(s.scalars(stmt))


def obtener(rutina_id: int) -> Rutina | None:
    stmt = select(Rutina).options(selectinload(Rutina.comando)).where(Rutina.id == rutina_id)
    with session_scope() as s:
        return s.scalars(stmt).first()


def guardar(datos: DatosRutina) -> int:
    nombre = datos.nombre.strip()
    if not nombre:
        raise ValueError("Ponle un nombre a la rutina.")
    if not datos.dias:
        raise ValueError("Elige al menos un día.")
    accion = AccionRutina(datos.accion)
    if accion == AccionRutina.EJECUTAR_COMANDO and datos.comando_id is None:
        raise ValueError("Elige qué comando ejecutar.")
    with session_scope() as s:
        if accion == AccionRutina.EJECUTAR_COMANDO and s.get(Comando, datos.comando_id) is None:
            raise ValueError("El comando elegido ya no existe.")
        if datos.id is None:
            rutina = Rutina()
            s.add(rutina)
        else:
            rutina = s.get(Rutina, datos.id)
            if rutina is None:
                raise ValueError("La rutina ya no existe.")
        nueva_hora = datos.hora.strftime("%H:%M")
        if rutina.hora != nueva_hora:
            rutina.ultima_ejecucion = None  # con otra hora puede volver a correr hoy
        rutina.nombre = nombre
        rutina.accion = accion
        rutina.comando_id = datos.comando_id if accion == AccionRutina.EJECUTAR_COMANDO else None
        rutina.dias = ",".join(str(d) for d in sorted(set(datos.dias)))
        rutina.hora = nueva_hora
        rutina.activo = datos.activo
        s.flush()
        return rutina.id


def cambiar_activo(rutina_id: int, activo: bool) -> None:
    with session_scope() as s:
        rutina = s.get(Rutina, rutina_id)
        if rutina is not None:
            rutina.activo = activo


def eliminar(rutina_id: int) -> None:
    with session_scope() as s:
        rutina = s.get(Rutina, rutina_id)
        if rutina is not None:
            s.delete(rutina)


def para_ejecutar(ahora: datetime | None = None) -> list[Rutina]:
    """Rutinas activas cuya hora de hoy ya llegó (hace menos de TOLERANCIA) y
    que todavía no se ejecutaron hoy."""
    ahora = ahora or datetime.now()
    hoy = ahora.date()
    listas = []
    for rutina in listar():
        if not rutina.activo or hoy.weekday() not in dias_de(rutina) or rutina.ultima_ejecucion == hoy:
            continue
        momento = datetime.combine(hoy, hora_de(rutina))
        if momento <= ahora <= momento + TOLERANCIA:
            listas.append(rutina)
    return listas


def marcar_ejecutada(rutina_id: int, dia: date | None = None) -> None:
    with session_scope() as s:
        rutina = s.get(Rutina, rutina_id)
        if rutina is not None:
            rutina.ultima_ejecucion = dia or date.today()

"""
Avisos de la Agenda: qué tareas avisan y cuándo (el "proveedor" de core/avisos.py).

Cada tarea guarda aviso_min = minutos ANTES de su hora:
    10:00 con 15  -> aviso a las 9:45
    sin hora      -> la base es HORA_SIN_HORA (8:00 am de ese día)
    None          -> sin aviso

Las recurrentes avisan cada vez que tocan (la renta: cada mes). Lo ya hecho no
avisa. Las fechas salen de services.occurrences(), lo mismo que el calendario.

Reprogramar solo: cualquier cambio en tareas o en su historial (crear, editar,
marcar hecha, deshacer, borrar) dispara core.avisos.request_sync() con un
"evento" de SQLAlchemy (como un @api.model_create_multi/write/unlink de Odoo
que avisa a otro módulo). Así ninguna pantalla tiene que acordarse.
"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import event

from core import avisos
from modulos.agenda import services
from modulos.agenda.models import Cumplimiento, Tarea

HORA_SIN_HORA = time(8, 0)

# Opciones del formulario. La clave es el texto del Dropdown ("no" = None).
AVISO_CON_HORA = {
    "no": "Sin aviso",
    "0": "A la hora",
    "5": "5 min antes",
    "15": "15 min antes",
    "30": "30 min antes",
    "60": "1 hora antes",
    "1440": "1 día antes",
}
AVISO_SIN_HORA = {
    "no": "Sin aviso",
    "0": "Ese día a las 8:00",
    "1440": "Un día antes a las 8:00",
}


def options_for(con_hora: bool) -> dict[str, str]:  # propio
    return AVISO_CON_HORA if con_hora else AVISO_SIN_HORA


def to_key(aviso_min: int | None, con_hora: bool) -> str:  # propio
    """aviso_min -> clave del Dropdown (si no existe en esa lista, "a la hora")."""
    clave = "no" if aviso_min is None else str(aviso_min)
    return clave if clave in options_for(con_hora) else "0"


def from_key(clave: str | None) -> int | None:  # propio
    return None if clave in (None, "no") else int(clave)


def notify_time(fecha: date, hora: time | None, aviso_min: int | None) -> datetime | None:  # propio
    """Cuándo avisar de una tarea que toca en `fecha` (None = sin aviso)."""
    if aviso_min is None:
        return None
    return datetime.combine(fecha, hora or HORA_SIN_HORA) - timedelta(minutes=aviso_min)


def _body(t: Tarea, fecha: date, hoy: date) -> str:  # propio
    """'Hoy 10:00 · 📁 App mamá · ↻ Cada mes'"""
    if fecha == hoy:
        cuando = "Hoy"
    elif fecha == hoy + timedelta(days=1):
        cuando = "Mañana"
    else:
        cuando = f"{fecha:%d/%m}"
    partes = [f"{cuando} {t.horario}" if t.horario else f"{cuando} · todo el día"]
    if t.proyecto:
        partes.append(f"📁 {t.proyecto.nombre}")
    if t.recurrente:
        partes.append(f"↻ {t.frecuencia_label}")
    return " · ".join(partes)


def provider(desde: datetime, hasta: datetime) -> list[avisos.Aviso]:  # propio
    """Las tareas pendientes cuyo aviso cae entre `desde` y `hasta`."""
    # +1 día: una tarea de pasado mañana con "1 día antes" avisa mañana
    ocurrencias = services.occurrences(desde.date(), hasta.date() + timedelta(days=1),
                                       hoy=desde.date())
    resultado = []
    for o in ocurrencias:
        if o.estado == "hecha":
            continue
        cuando = notify_time(o.fecha, o.tarea.hora_inicio, o.tarea.aviso_min)
        if cuando is not None and desde < cuando <= hasta:
            resultado.append(avisos.Aviso(cuando, o.tarea.titulo,
                                          _body(o.tarea, o.fecha, desde.date())))
    return resultado


# --- Registro --------------------------------------------------------------
avisos.register_provider(provider)


def _changed(*_):  # propio
    avisos.request_sync()


for _modelo in (Tarea, Cumplimiento):
    for _evento in ("after_insert", "after_update", "after_delete"):
        if not event.contains(_modelo, _evento, _changed):
            event.listen(_modelo, _evento, _changed)

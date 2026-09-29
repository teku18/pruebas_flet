"""
Lógica de la Agenda (el "cocinero" del chismoso): nada de esto se guarda,
se calcula cada vez que abres la pantalla.

  Urgencia de una tarea pendiente, según su fecha:
    fecha <  hoy     -> "vencida"  🔴
    fecha == hoy     -> "hoy"      🟡
    fecha == mañana  -> "manana"   ⚪
  "hecha" 🟢 = tiene un Cumplimiento con hecho_en de hoy

  Marcar como hecha:
    única      -> completada = True
    recurrente -> la fecha salta al siguiente periodo DESDE LA FECHA QUE TOCABA
                  (no desde hoy): si debes la renta de octubre y noviembre,
                  marcar una vez solo paga octubre.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from core.database import SessionLocal
from modulos.agenda.models import Cumplimiento, Tarea


# ============================================================================
# Siguiente fecha de una tarea recurrente
# ============================================================================
def next_date(fecha: date, frecuencia: str) -> date:  # propio
    """
    La fecha que sigue a "fecha" según la frecuencia.
      diaria  -> +1 día          semanal -> +7 días
      lun_vie -> siguiente día hábil (viernes -> lunes)
      mensual -> mismo día del mes siguiente (31 ene -> 28/29 feb)
    """
    if frecuencia == "diaria":
        return fecha + timedelta(days=1)
    if frecuencia == "semanal":
        return fecha + timedelta(days=7)
    if frecuencia == "lun_vie":
        siguiente = fecha + timedelta(days=1)
        while siguiente.weekday() >= 5:  # 5 = sábado, 6 = domingo
            siguiente += timedelta(days=1)
        return siguiente
    if frecuencia == "mensual":
        anio, mes = (fecha.year + 1, 1) if fecha.month == 12 else (fecha.year, fecha.month + 1)
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return date(anio, mes, min(fecha.day, ultimo_dia))
    raise ValueError(f"'{frecuencia}' no es recurrente")


def first_date(fecha: date, frecuencia: str) -> date:  # propio
    """Una tarea de L a V que se crea en fin de semana empieza el lunes."""
    if frecuencia == "lun_vie":
        while fecha.weekday() >= 5:
            fecha += timedelta(days=1)
    return fecha


# ============================================================================
# El chismoso
# ============================================================================
@dataclass
class Chisme:
    """Lo que muestra la pantalla del día, ya clasificado."""
    vencidas: list[Tarea] = field(default_factory=list)
    hoy: list[Tarea] = field(default_factory=list)
    manana: list[Tarea] = field(default_factory=list)
    hechas: list[Cumplimiento] = field(default_factory=list)  # hechas hoy

    @property
    def vacio(self) -> bool:  # propio
        return not (self.vencidas or self.hoy or self.manana or self.hechas)


def gossip(hoy: date | None = None) -> Chisme:  # propio
    """Tareas pendientes hasta mañana + lo que ya hiciste hoy."""
    hoy = hoy or date.today()
    manana = hoy + timedelta(days=1)
    chisme = Chisme()
    with SessionLocal() as session:
        pendientes = session.scalars(
            select(Tarea)
            .where(Tarea.completada.is_(False), Tarea.fecha <= manana)
            .options(selectinload(Tarea.proyecto))
            .order_by(Tarea.fecha, Tarea.hora_inicio.is_(None), Tarea.hora_inicio, Tarea.id)
        )
        for t in pendientes:
            if t.fecha < hoy:
                chisme.vencidas.append(t)
            elif t.fecha == hoy:
                chisme.hoy.append(t)
            else:
                chisme.manana.append(t)

        inicio_dia = datetime.combine(hoy, datetime.min.time())
        chisme.hechas = list(session.scalars(
            select(Cumplimiento)
            .where(Cumplimiento.hecho_en >= inicio_dia,
                   Cumplimiento.hecho_en < inicio_dia + timedelta(days=1))
            .options(selectinload(Cumplimiento.tarea).selectinload(Tarea.proyecto))
            .order_by(Cumplimiento.hecho_en.desc())
        ))
    return chisme


def all_pending() -> list[Tarea]:  # propio
    """Todas las tareas que siguen vivas (para la pestaña "Todas")."""
    with SessionLocal() as session:
        return list(session.scalars(
            select(Tarea)
            .where(Tarea.completada.is_(False))
            .options(selectinload(Tarea.proyecto))
            .order_by(Tarea.fecha, Tarea.hora_inicio.is_(None), Tarea.hora_inicio, Tarea.id)
        ))


def get_task(tarea_id: int) -> Tarea | None:  # propio
    """Una tarea con su proyecto ya cargado."""
    with SessionLocal() as session:
        return session.get(Tarea, tarea_id, options=[selectinload(Tarea.proyecto)])


# ============================================================================
# Marcar hecha / deshacer
# ============================================================================
def complete(tarea_id: int, ahora: datetime | None = None) -> Cumplimiento:  # propio
    """Guarda el cumplimiento y mueve la tarea (o la da por completada)."""
    ahora = ahora or datetime.now()
    with SessionLocal() as session:
        tarea = session.get(Tarea, tarea_id)
        if tarea is None or tarea.completada:
            raise ValueError("La tarea ya no está pendiente")
        cumplimiento = Cumplimiento(
            tarea_id=tarea.id, fecha_programada=tarea.fecha, hecho_en=ahora
        )
        session.add(cumplimiento)
        if tarea.recurrente:
            tarea.fecha = next_date(tarea.fecha, tarea.frecuencia)
        else:
            tarea.completada = True
        session.commit()
        session.refresh(cumplimiento)
        return cumplimiento


def undo(cumplimiento_id: int) -> None:  # propio
    """Te equivocaste al marcarla: la tarea regresa a la fecha que tocaba."""
    with SessionLocal() as session:
        cumplimiento = session.get(Cumplimiento, cumplimiento_id)
        if cumplimiento is None:
            return
        tarea = cumplimiento.tarea
        tarea.fecha = cumplimiento.fecha_programada
        tarea.completada = False
        session.delete(cumplimiento)
        session.commit()


# ============================================================================
# Para Proyectos
# ============================================================================
def pending_by_project(proyecto_id: int) -> int:  # propio
    """Cuántas tareas pendientes tiene un proyecto."""
    with SessionLocal() as session:
        return session.scalar(
            select(func.count()).select_from(Tarea).where(
                Tarea.proyecto_id == proyecto_id, Tarea.completada.is_(False)
            )
        )


def delete_project_tasks(proyecto_id: int) -> None:  # propio
    """Al borrar un proyecto se borran sus tareas (y su historial)."""
    for tarea in Tarea.search(Tarea.proyecto_id == proyecto_id):
        Tarea.delete(tarea.id)

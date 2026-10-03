"""
Cálculos de Proyectos (como los campos compute sin store de Odoo):
nada de esto se guarda en la BD, se calcula cada vez que se pide.

  duración          = fecha_fin - fecha_inicio   (o hoy - inicio si sigue vivo)
  última actividad  = fecha de la entrada más reciente
  días sin avance   = hoy - última actividad (o - inicio si no hay entradas)
  estancado         = en una etapa "en curso" y con DIAS_ESTANCADO o más sin avance

Aquí también vive:
  - el chismoso de la Agenda  -> stalled_projects()
  - el resumen del año        -> year_highlights()
  - las tareas del proyecto y su Kanban -> project_tasks(), move_task()…
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import case, extract, func, select

from core.database import SessionLocal
from modulos.proyectos.models import (
    EtapaProyecto,
    EtapaTarea,
    Entrada,
    Proyecto,
    TipoEntrada,
)

# A partir de cuántos días sin avance un proyecto activo se marca "estancado"
DIAS_ESTANCADO = 14


# ============================================================================
# Textos
# ============================================================================
def human_duration(dias: int) -> str:  # propio
    """5 -> '5 días' · 45 -> '1 mes' · 400 -> '1 año 1 mes'"""
    if dias < 31:
        return "1 día" if dias == 1 else f"{dias} días"
    if dias < 365:
        meses = dias // 30
        return "1 mes" if meses == 1 else f"{meses} meses"
    anios, resto = divmod(dias, 365)
    texto = "1 año" if anios == 1 else f"{anios} años"
    meses = resto // 30
    if meses:
        texto += " 1 mes" if meses == 1 else f" {meses} meses"
    return texto


# ============================================================================
# Números de un proyecto
# ============================================================================
@dataclass
class ProjectStats:
    entradas: int = 0
    hitos: int = 0
    ultima: date | None = None       # fecha de la última entrada
    duracion_dias: int = 0
    dias_sin_avance: int = 0
    estancado: bool = False

    @property
    def duracion_texto(self) -> str:  # propio
        return human_duration(self.duracion_dias)


def _counts() -> dict[int, tuple[int, int, datetime | None]]:  # propio
    """{proyecto_id: (entradas, hitos, última fecha_hora)} en UNA consulta."""
    with SessionLocal() as session:
        consulta = select(
            Entrada.proyecto_id,
            func.count(),
            func.sum(case((TipoEntrada.es_hito.is_(True), 1), else_=0)),
            func.max(Entrada.fecha_hora),
        ).join(TipoEntrada, Entrada.tipo_id == TipoEntrada.id).group_by(Entrada.proyecto_id)
        return {pid: (n, h or 0, ultima) for pid, n, h, ultima in session.execute(consulta)}


def _stats(pro: Proyecto, datos: tuple, hoy: date) -> ProjectStats:  # propio
    n, hitos, ultima = datos
    ultima_fecha = ultima.date() if ultima else None
    fin = pro.fecha_fin or hoy
    sin_avance = (hoy - (ultima_fecha or pro.fecha_inicio)).days
    return ProjectStats(
        entradas=n,
        hitos=hitos,
        ultima=ultima_fecha,
        duracion_dias=max((fin - pro.fecha_inicio).days, 0),
        dias_sin_avance=max(sin_avance, 0),
        estancado=pro.etapa.clase == "en_curso" and sin_avance >= DIAS_ESTANCADO,
    )


def all_stats(hoy: date | None = None) -> dict[int, ProjectStats]:  # propio
    """{proyecto_id: ProjectStats} de todos los proyectos (para la lista)."""
    hoy = hoy or date.today()
    conteos = _counts()
    return {
        pro.id: _stats(pro, conteos.get(pro.id, (0, 0, None)), hoy)
        for pro in Proyecto.search_all()
    }


def project_stats(pro: Proyecto, hoy: date | None = None) -> ProjectStats:  # propio
    """ProjectStats de un solo proyecto (para su ficha)."""
    return _stats(pro, _counts().get(pro.id, (0, 0, None)), hoy or date.today())


# ============================================================================
# Para otros módulos
# ============================================================================
def stalled_projects(hoy: date | None = None) -> list[tuple[Proyecto, ProjectStats]]:  # propio
    """
    Proyectos activos que llevan DIAS_ESTANCADO o más sin avance, el más
    olvidado primero. Lo usará el chismoso: "La app de X lleva 23 días sin avance".
    """
    stats = all_stats(hoy)
    resultado = [
        (pro, stats[pro.id]) for pro in Proyecto.search_all() if stats[pro.id].estancado
    ]
    return sorted(resultado, key=lambda par: par[1].dias_sin_avance, reverse=True)


@dataclass
class YearHighlights:
    anio: int
    terminados: list[Proyecto] = field(default_factory=list)   # destacados que acabaron ese año
    hitos: list[Entrada] = field(default_factory=list)         # hitos de cualquier proyecto


def year_highlights(anio: int) -> YearHighlights:  # propio
    """
    Material para el resumen del año (la futura "tarjeta de Navidad"):
    proyectos destacados terminados ese año + todos los hitos del año.
    """
    terminados = Proyecto.search(
        Proyecto.destacado.is_(True),
        Proyecto.etapa.has(EtapaProyecto.clase == "terminada"),
        extract("year", Proyecto.fecha_fin) == anio,
    )
    with SessionLocal() as session:
        consulta = (
            select(Entrada)
            .where(Entrada.tipo.has(TipoEntrada.es_hito.is_(True)),
                   extract("year", Entrada.fecha_hora) == anio)
            .order_by(Entrada.fecha_hora)
        )
        hitos = list(session.scalars(consulta))
    return YearHighlights(anio=anio, terminados=terminados, hitos=hitos)


# ============================================================================
# Kanban de proyectos
# ============================================================================
def projects_by_stage(proyectos: list[Proyecto]) -> list[tuple[EtapaProyecto, list[Proyecto]]]:  # propio
    """[(etapa, sus proyectos)] en el orden de las etapas (columnas del Kanban)."""
    etapas = EtapaProyecto.search_all()
    return [(e, [p for p in proyectos if p.etapa_id == e.id]) for e in etapas]


def move_project(proyecto_id: int, etapa_id: int) -> Proyecto:  # propio
    """Cambia de etapa (columna). La fecha fin se pone/quita sola (Proyecto._validate)."""
    return Proyecto.update(proyecto_id, etapa_id=etapa_id)


# ============================================================================
# Tareas del proyecto (viven en la tabla de la Agenda)
# ============================================================================
#   Etapas que usa un proyecto = las que eligió en su ficha (o todas).
#   Una tarea sin etapa (creada en la Agenda) se pinta en la primera abierta,
#   o en la primera cerrada si ya está completada.
#   Llevarla a una etapa cerrada = marcarla hecha (con historial, como la Agenda).
#   Sacarla de una cerrada = deshacer ese "hecho".

def task_stages(pro: Proyecto) -> list[EtapaTarea]:  # propio
    """Columnas del Kanban de tareas de este proyecto."""
    return list(pro.etapas_tarea) or EtapaTarea.search_all()


def set_task_stages(proyecto_id: int, etapa_ids: list[int]) -> None:  # propio
    """Guarda qué etapas de tarea usa el proyecto (Many2many; vacío = todas)."""
    with SessionLocal() as session:
        pro = session.get(Proyecto, proyecto_id)
        pro.etapas_tarea = list(session.scalars(
            select(EtapaTarea).where(EtapaTarea.id.in_(etapa_ids)))) if etapa_ids else []
        session.commit()


def stage_of(tarea, etapas: list[EtapaTarea]) -> EtapaTarea | None:  # propio
    """En qué columna va la tarea."""
    if not etapas:
        return None
    por_id = {e.id: e for e in etapas}
    if tarea.etapa_id in por_id and por_id[tarea.etapa_id].cerrada == tarea.completada:
        return por_id[tarea.etapa_id]
    buscadas = [e for e in etapas if e.cerrada == tarea.completada]
    return buscadas[0] if buscadas else (etapas[-1] if tarea.completada else etapas[0])


def project_tasks(proyecto_id: int):  # propio
    """Todas las tareas del proyecto (pendientes y hechas), las de fecha más próxima arriba."""
    from modulos.agenda.models import Tarea

    tareas = Tarea.search(Tarea.proyecto_id == proyecto_id)
    return sorted(tareas, key=lambda t: (t.completada, t.fecha is None, t.fecha or date.max, t.id))


def tasks_by_stage(pro: Proyecto) -> list[tuple[EtapaTarea, list]]:  # propio
    """[(etapa, tareas)] para el Kanban de tareas del proyecto."""
    etapas = task_stages(pro)
    tareas = project_tasks(pro.id)
    columnas = {e.id: [] for e in etapas}
    for t in tareas:
        e = stage_of(t, etapas)
        if e is not None:
            columnas[e.id].append(t)
    return [(e, columnas[e.id]) for e in etapas]


def first_open_stage(pro: Proyecto) -> EtapaTarea | None:  # propio
    return next((e for e in task_stages(pro) if not e.cerrada), None)


def move_task(tarea_id: int, etapa_id: int) -> str:  # propio
    """
    Mueve una tarea de columna. Regresa qué pasó: "movida" | "hecha" | "reabierta".
      abierta -> cerrada : se marca hecha (Cumplimiento, igual que en la Agenda)
      cerrada -> abierta : se deshace el último "hecho"
    """
    from modulos.agenda import services as agenda
    from modulos.agenda.models import Cumplimiento, Tarea

    tarea = Tarea.get(tarea_id)
    etapa = EtapaTarea.get(etapa_id)
    if tarea is None or etapa is None:
        raise ValueError("La tarea o la etapa ya no existen")

    resultado = "movida"
    if etapa.cerrada and not tarea.completada:
        if tarea.recurrente:
            raise ValueError("Las tareas que se repiten se marcan como hechas en la Agenda")
        agenda.complete(tarea_id)
        resultado = "hecha"
    elif not etapa.cerrada and tarea.completada:
        ultimo = Cumplimiento.search(Cumplimiento.tarea_id == tarea_id)
        if ultimo:
            agenda.undo(ultimo[0].id)  # _orden: el más reciente primero
        else:
            Tarea.update(tarea_id, completada=False)
        resultado = "reabierta"
    Tarea.update(tarea_id, etapa_id=etapa_id)
    return resultado


def task_counts() -> dict[int, tuple[int, int]]:  # propio
    """{proyecto_id: (tareas hechas, tareas totales)} en UNA consulta (para la lista)."""
    from modulos.agenda.models import Tarea

    with SessionLocal() as session:
        consulta = select(
            Tarea.proyecto_id,
            func.sum(case((Tarea.completada.is_(True), 1), else_=0)),
            func.count(),
        ).where(Tarea.proyecto_id.is_not(None)).group_by(Tarea.proyecto_id)
        return {pid: (hechas or 0, total) for pid, hechas, total in session.execute(consulta)}

"""
Cálculos de Proyectos (como los campos compute sin store de Odoo):
nada de esto se guarda en la BD, se calcula cada vez que se pide.

  duración          = fecha_fin - fecha_inicio   (o hoy - inicio si sigue vivo)
  última actividad  = fecha de la entrada más reciente
  días sin avance   = hoy - última actividad (o - inicio si no hay entradas)
  estancado         = activo y con DIAS_ESTANCADO o más sin avance

Aquí también vive lo que usarán después:
  - el chismoso de la Agenda  -> stalled_projects()
  - el resumen del año        -> year_highlights()
"""
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import case, extract, func, select

from core.database import SessionLocal
from modulos.proyectos.models import Entrada, Proyecto

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
            func.sum(case((Entrada.tipo == "hito", 1), else_=0)),
            func.max(Entrada.fecha_hora),
        ).group_by(Entrada.proyecto_id)
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
        estancado=pro.estado == "activo" and sin_avance >= DIAS_ESTANCADO,
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
# Para otros módulos (todavía sin pantalla)
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
        Proyecto.estado == "terminado",
        extract("year", Proyecto.fecha_fin) == anio,
    )
    with SessionLocal() as session:
        consulta = (
            select(Entrada)
            .where(Entrada.tipo == "hito", extract("year", Entrada.fecha_hora) == anio)
            .order_by(Entrada.fecha_hora)
        )
        hitos = list(session.scalars(consulta))
    return YearHighlights(anio=anio, terminados=terminados, hitos=hitos)

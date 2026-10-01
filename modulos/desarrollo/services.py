"""
Consultas del módulo Desarrollo (la vista pregunta y pinta, aquí se decide).

  overview()          -> módulos ordenados por prioridad, con cuántos pendientes
                         tiene cada uno y cuántos son de prioridad alta
  pending_by_priority -> TODOS los pendientes abiertos de la app, alta primero
  module_items()      -> pendientes (o hechos) de un módulo
  toggle_done()       -> marcar / desmarcar hecho
"""
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from core.database import SessionLocal
from modulos.desarrollo.models import PRIORIDAD_ORDEN, ModuloApp, Pendiente


def _priority_key(registro) -> tuple:  # propio
    """Alta > Media > Baja; a igual prioridad, el más viejo primero."""
    return (PRIORIDAD_ORDEN.get(registro.prioridad, 9), registro.id)


# ============================================================================
# Módulos
# ============================================================================
@dataclass
class ModuleSummary:
    pendientes: int = 0   # abiertos (no hechos)
    altas: int = 0        # abiertos de prioridad alta
    hechos: int = 0


def _counts() -> dict[int, ModuleSummary]:  # propio
    """{modulo_id: ModuleSummary} en UNA consulta."""
    abierto = Pendiente.hecho.is_(False)
    with SessionLocal() as session:
        consulta = select(
            Pendiente.modulo_id,
            func.sum(case((abierto, 1), else_=0)),
            func.sum(case((abierto & (Pendiente.prioridad == "alta"), 1), else_=0)),
            func.sum(case((Pendiente.hecho.is_(True), 1), else_=0)),
        ).group_by(Pendiente.modulo_id)
        return {
            mid: ModuleSummary(p or 0, a or 0, h or 0)
            for mid, p, a, h in session.execute(consulta)
        }


def overview() -> list[tuple[ModuloApp, ModuleSummary]]:  # propio
    conteos = _counts()
    modulos = sorted(ModuloApp.search_all(), key=lambda m: (PRIORIDAD_ORDEN[m.prioridad], m.nombre))
    return [(m, conteos.get(m.id, ModuleSummary())) for m in modulos]


def module_summary(modulo_id: int) -> ModuleSummary:  # propio
    return _counts().get(modulo_id, ModuleSummary())


# ============================================================================
# Pendientes
# ============================================================================
def pending_by_priority() -> list[Pendiente]:  # propio
    """Todos los pendientes abiertos (con su módulo ya cargado), alta primero."""
    with SessionLocal() as session:
        consulta = (
            select(Pendiente)
            .where(Pendiente.hecho.is_(False))
            .options(selectinload(Pendiente.modulo), selectinload(Pendiente.adjuntos))
        )
        return sorted(session.scalars(consulta), key=_priority_key)


def module_items(modulo_id: int, hechos: bool = False) -> list[Pendiente]:  # propio
    """Pendientes abiertos de un módulo (alta primero) o los hechos (recientes primero)."""
    with SessionLocal() as session:
        items = list(session.scalars(
            select(Pendiente)
            .where(Pendiente.modulo_id == modulo_id, Pendiente.hecho.is_(hechos))
            .options(selectinload(Pendiente.adjuntos))
        ))
    if hechos:
        return sorted(items, key=lambda p: p.hecho_en or p.creado_en, reverse=True)
    return sorted(items, key=_priority_key)


def get_item(pendiente_id: int) -> Pendiente | None:  # propio
    """Un pendiente con su módulo y sus adjuntos ya cargados (para el formulario)."""
    with SessionLocal() as session:
        return session.get(
            Pendiente, pendiente_id,
            options=[selectinload(Pendiente.modulo), selectinload(Pendiente.adjuntos)],
        )


def all_for_export() -> list[tuple[ModuloApp, list[Pendiente]]]:  # propio
    """
    Para el Excel: cada módulo (orden de prioridad) con TODOS sus pendientes:
    primero los abiertos (alta → baja), luego los hechos (recientes primero).
    """
    with SessionLocal() as session:
        todos = list(session.scalars(
            select(Pendiente).options(selectinload(Pendiente.adjuntos))
        ))
    por_modulo: dict[int, list[Pendiente]] = {}
    for p in todos:
        por_modulo.setdefault(p.modulo_id, []).append(p)

    resultado = []
    for m, _ in overview():
        items = por_modulo.get(m.id, [])
        abiertos = sorted((p for p in items if not p.hecho), key=_priority_key)
        hechos = sorted((p for p in items if p.hecho),
                        key=lambda p: p.hecho_en or p.creado_en, reverse=True)
        resultado.append((m, abiertos + hechos))
    return resultado


def toggle_done(pendiente_id: int) -> Pendiente:  # propio
    """○ -> ✓ y ✓ -> ○ (el modelo pone o quita hecho_en)."""
    actual = Pendiente.get(pendiente_id)
    return Pendiente.update(pendiente_id, hecho=not actual.hecho)

"""
Historial de Red: cada prueba que corres, con su resultado completo.
Cuántas se guardan: Ajustes.red_historial_max (0 = sin límite).
"""
from sqlalchemy import delete, func, select

from core.database import SessionLocal
from modulos.kraken.models import Ajustes, HistorialRed


def record(herramienta: str, objetivo: str, resultado) -> HistorialRed:  # propio
    """`resultado` es cualquier *Resultado (tiene summary() y to_dict())."""
    resumen, exito = resultado.summary()
    fila = HistorialRed.create(herramienta=herramienta, objetivo=(objetivo or "")[:255] or "—",
                               resumen=resumen[:255], exito=exito, detalle=resultado.to_dict(),
                               tiempo_ms=getattr(resultado, "tiempo_ms", None))
    prune(Ajustes.current().red_historial_max)
    return fila


def prune(maximo: int) -> int:  # propio
    if not maximo:
        return 0
    with SessionLocal() as session:
        sobran = list(session.scalars(select(HistorialRed.id).order_by(
            HistorialRed.creado_en.desc(), HistorialRed.id.desc()).offset(maximo)))
        if sobran:
            session.execute(delete(HistorialRed).where(HistorialRed.id.in_(sobran)))
            session.commit()
        return len(sobran)


def history(herramienta: str | None = None, limite: int = 300) -> list[HistorialRed]:  # propio
    with SessionLocal() as session:
        consulta = select(HistorialRed)
        if herramienta:
            consulta = consulta.where(HistorialRed.herramienta == herramienta)
        return list(session.scalars(consulta.order_by(
            HistorialRed.creado_en.desc(), HistorialRed.id.desc()).limit(limite)))


def recent_targets(herramienta: str, n: int = 6) -> list[str]:  # propio
    """Lo último que probaste con esa herramienta (sin repetir), para tocar y repetir."""
    vistos: list[str] = []
    for h in history(herramienta, 60):
        if h.objetivo not in vistos:
            vistos.append(h.objetivo)
        if len(vistos) == n:
            break
    return vistos


def count() -> int:  # propio
    with SessionLocal() as session:
        return session.scalar(select(func.count(HistorialRed.id))) or 0


def clear() -> None:  # propio
    with SessionLocal() as session:
        session.execute(delete(HistorialRed))
        session.commit()

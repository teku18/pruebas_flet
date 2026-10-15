"""
Lógica de Notas (el "cocinero"): buscar, crear rápido, guardar, fijar, archivar.

Buscar: el texto se busca en el título, en el cuerpo y en las casillas de las
listas. Para las casillas se usa EXISTS (¿hay alguna casilla de esta nota que
contenga el texto?), como un dominio de Odoo sobre un One2many:
    [("items.texto", "ilike", "leche")]

Guardar: el editor manda la foto completa de la nota (título, cuerpo y
casillas) y aquí se reemplazan las casillas. Es más simple que llevar la cuenta
de cuál casilla se agregó, movió o borró, y una lista del súper es chica.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import exists, func, or_, select

from core.database import SessionLocal
from modulos.notas.models import Nota, NotaItem


# ============================================================================
# Leer
# ============================================================================
def search(texto: str = "", etiqueta_id: int | None = None,  # propio
           archivadas: bool = False) -> list[Nota]:
    """Notas del tablero: fijadas primero, luego lo último que editaste."""
    condiciones = [Nota.archivada.is_(archivadas)]
    if etiqueta_id:
        condiciones.append(Nota.etiqueta_id == etiqueta_id)
    texto = (texto or "").strip()
    if texto:
        patron = f"%{texto.lower()}%"
        en_items = exists().where(NotaItem.nota_id == Nota.id,
                                  func.lower(NotaItem.texto).like(patron))
        condiciones.append(or_(func.lower(Nota.titulo).like(patron),
                               func.lower(Nota.cuerpo).like(patron), en_items))
    return Nota.search(*condiciones)


def get(nota_id: int) -> Nota | None:  # propio
    return Nota.get(nota_id)


def count_archived() -> int:  # propio
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(Nota)
                              .where(Nota.archivada.is_(True)))


# ============================================================================
# Crear
# ============================================================================
def quick_note(texto: str, etiqueta_id: int | None = None) -> Nota:  # propio
    """
    Captura rápida (un renglón + Enter): se guarda tal cual como nota de texto,
    sin título (no hay que pensar en uno). Si estás filtrando por una etiqueta,
    la nota nace con esa etiqueta.
    """
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escribe algo")
    return Nota.create(tipo="texto", cuerpo=texto, etiqueta_id=etiqueta_id)


def new_note(tipo: str, etiqueta_id: int | None = None) -> Nota:  # propio
    """Nota vacía para el editor (si sales sin escribir nada, se borra sola)."""
    nota = Nota.create(tipo=tipo, etiqueta_id=etiqueta_id)
    if tipo == "lista":
        NotaItem.create(nota_id=nota.id, texto="", secuencia=1)
    return Nota.get(nota.id)


# ============================================================================
# Guardar (lo llama el editor, con su foto completa)
# ============================================================================
@dataclass
class ItemData:
    texto: str
    hecho: bool = False


def save_note(nota_id: int, titulo: str | None, cuerpo: str | None,  # propio
              items: list[ItemData] | None) -> Nota | None:
    """Guarda título, cuerpo y casillas; actualizado_en = ahora."""
    with SessionLocal() as session:
        nota = session.get(Nota, nota_id)
        if nota is None:
            return None
        nota.titulo = (titulo or "").strip() or None
        nota.cuerpo = (cuerpo or "").rstrip() or None
        if items is not None:
            nota.items = [NotaItem(texto=(i.texto or "")[:300], hecho=i.hecho, secuencia=n)
                          for n, i in enumerate(items, start=1)]
        nota.actualizado_en = datetime.now()
        session.commit()
    return Nota.get(nota_id)


def delete_if_empty(nota_id: int) -> bool:  # propio
    """Al salir del editor: una nota sin nada escrito no se queda en el tablero."""
    nota = Nota.get(nota_id)
    if nota is not None and nota.vacia:
        Nota.delete(nota_id)
        return True
    return False


def convert(nota_id: int) -> Nota:  # propio
    """
    Texto <-> lista.
      texto -> lista: cada renglón del cuerpo es una casilla
      lista -> texto: cada casilla es un renglón ("✓ " si estaba hecha)
    """
    with SessionLocal() as session:
        nota = session.get(Nota, nota_id)
        if nota.tipo == "texto":
            renglones = [r.strip() for r in (nota.cuerpo or "").splitlines() if r.strip()]
            # "✓ Pan" (como queda al convertir una lista) regresa como casilla hecha
            nota.items = [NotaItem(texto=r.removeprefix("✓").strip()[:300],
                                   hecho=r.startswith("✓"), secuencia=n)
                          for n, r in enumerate(renglones or [""], start=1)]
            nota.cuerpo, nota.tipo = None, "lista"
        else:
            nota.cuerpo = "\n".join(("✓ " if i.hecho else "") + i.texto
                                    for i in nota.items if i.texto.strip()) or None
            nota.items, nota.tipo = [], "texto"
        nota.actualizado_en = datetime.now()
        session.commit()
    return Nota.get(nota_id)


# ============================================================================
# Acciones rápidas (no cambian actualizado_en: no mueven la nota de lugar)
# ============================================================================
def set_pinned(nota_id: int, fijada: bool) -> Nota:  # propio
    return Nota.update(nota_id, fijada=fijada)


def set_archived(nota_id: int, archivada: bool) -> Nota:  # propio
    # Archivar quita el "fijada" (como Keep): al regresar, no estorba arriba
    valores = {"archivada": archivada}
    if archivada:
        valores["fijada"] = False
    return Nota.update(nota_id, **valores)


def set_color(nota_id: int, color: str | None) -> Nota:  # propio
    return Nota.update(nota_id, color=color)


def set_label(nota_id: int, etiqueta_id: int | None) -> Nota:  # propio
    return Nota.update(nota_id, etiqueta_id=etiqueta_id)


def toggle_item(item_id: int) -> NotaItem:  # propio
    """Palomear una casilla desde el tablero (sin abrir la nota)."""
    item = NotaItem.get(item_id)
    return NotaItem.update(item_id, hecho=not item.hecho)

"""
Lógica de Memorias (el "cocinero"):

  search()       línea de tiempo con filtros: texto, etiquetas y rango de fechas
  timeline()     agrupa por año y mes:  2026 > octubre > [memorias]
  on_this_day()  "Un día como hoy": mismo día y mes en años anteriores
  photos()       todas las fotos (galería), la memoria más reciente primero
  save()         crea/actualiza la memoria, sus etiquetas y sus fotos

Fechas en SQLite: se guardan como texto 'AAAA-MM-DD', así que el mes y el día
se comparan con strftime('%m-%d', fecha) (como un campo computado en SQL).
"""
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from core.adjuntos import Adjunto
from core.database import SessionLocal
from core.ui import MESES
from modulos.memorias import imagenes
from modulos.memorias.models import MEMORIAS_DIR, MODELO_ADJUNTOS, EtiquetaMemoria, Memoria

MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ============================================================================
# Leer
# ============================================================================
@dataclass
class Filtros:
    texto: str = ""
    etiqueta_ids: set[int] = field(default_factory=set)  # cualquiera de ellas
    desde: date | None = None
    hasta: date | None = None

    @property
    def activos(self) -> int:  # propio
        """Cuántos filtros (sin contar el texto) hay puestos: para el ícono."""
        return bool(self.etiqueta_ids) + bool(self.desde) + bool(self.hasta)


def _query(*condiciones):  # propio
    return (select(Memoria).where(*condiciones)
            .options(selectinload(Memoria.fotos), selectinload(Memoria.etiquetas))
            .order_by(Memoria.fecha.desc(), Memoria.id.desc()))


def search(f: Filtros | None = None) -> list[Memoria]:  # propio
    f = f or Filtros()
    condiciones = []
    texto = (f.texto or "").strip().lower()
    if texto:
        patron = f"%{texto}%"
        condiciones.append(or_(func.lower(Memoria.titulo).like(patron),
                               func.lower(Memoria.relato).like(patron),
                               func.lower(Memoria.lugar).like(patron)))
    if f.etiqueta_ids:
        condiciones.append(Memoria.etiquetas.any(EtiquetaMemoria.id.in_(f.etiqueta_ids)))
    if f.desde:
        condiciones.append(Memoria.fecha >= f.desde)
    if f.hasta:
        condiciones.append(Memoria.fecha <= f.hasta)
    with SessionLocal() as session:
        return list(session.scalars(_query(*condiciones)))


def get(memoria_id: int) -> Memoria | None:  # propio
    with SessionLocal() as session:
        return session.scalars(_query(Memoria.id == memoria_id)).first()


def timeline(memorias: list[Memoria]) -> "OrderedDict[int, OrderedDict[int, list[Memoria]]]":  # propio
    """{año: {mes: [memorias]}} conservando el orden (lo más reciente primero)."""
    grupos: OrderedDict = OrderedDict()
    for m in memorias:
        grupos.setdefault(m.fecha.year, OrderedDict()).setdefault(m.fecha.month, []).append(m)
    return grupos


def on_this_day(hoy: date | None = None) -> list[Memoria]:  # propio
    """Memorias de este mismo día y mes, de años anteriores (la más antigua primero)."""
    hoy = hoy or date.today()
    with SessionLocal() as session:
        consulta = _query(func.strftime("%m-%d", Memoria.fecha) == hoy.strftime("%m-%d"),
                          Memoria.fecha < hoy).order_by(None).order_by(Memoria.fecha)
        return list(session.scalars(consulta))


def years_ago(m: Memoria, hoy: date | None = None) -> str:  # propio
    """'Hace 1 año' / 'Hace 7 años'."""
    n = (hoy or date.today()).year - m.fecha.year
    return "Hace 1 año" if n == 1 else f"Hace {n} años"


def long_date(d: date) -> str:  # propio
    """date(2019, 12, 24) -> '24 de diciembre de 2019'"""
    return f"{d.day} de {MESES_LARGOS[d.month - 1]} de {d.year}"


def short_month(mes: int) -> str:  # propio
    return MESES[mes - 1]


@dataclass
class Foto:
    adjunto: Adjunto
    memoria: Memoria


def photos(memorias: list[Memoria]) -> list[Foto]:  # propio
    """Todas las fotos de esas memorias (para la galería), en orden de la línea de tiempo."""
    return [Foto(a, m) for m in memorias for a in m.fotos
            if (a.mimetype or "").startswith("image/")]


# ============================================================================
# Guardar
# ============================================================================
@dataclass
class FotoNueva:
    nombre: str
    datos: bytes


def save(memoria_id: int | None, *, fecha: date, titulo: str, relato: str | None,  # propio
         lugar: str | None, animo: str | None, etiqueta_ids: list[int],
         fotos_nuevas: list[FotoNueva], fotos_borrar: list[int]) -> Memoria:
    """Crea o actualiza la memoria con sus etiquetas; copia fotos nuevas y borra las quitadas."""
    valores = dict(fecha=fecha, titulo=(titulo or "").strip(),
                   relato=(relato or "").strip() or None,
                   lugar=(lugar or "").strip() or None, animo=animo or None)
    with SessionLocal() as session:
        if memoria_id is None:
            memoria = Memoria(origen="texto", **valores)
            session.add(memoria)
        else:
            memoria = session.get(Memoria, memoria_id)
            for campo, valor in valores.items():
                setattr(memoria, campo, valor)
        memoria._validate()
        memoria.etiquetas = list(session.scalars(
            select(EtiquetaMemoria).where(EtiquetaMemoria.id.in_(etiqueta_ids or [0]))))
        session.commit()
        memoria_id = memoria.id

    for adjunto_id in fotos_borrar:
        adjunto = Adjunto.get(adjunto_id)
        if adjunto is not None:
            imagenes.delete_photo_files(adjunto.ruta)
            Adjunto.delete(adjunto_id)
    carpeta = MEMORIAS_DIR / str(memoria_id)
    for foto in fotos_nuevas:
        ruta, tamano, mime = imagenes.save_photo(foto.datos, foto.nombre, carpeta)
        Adjunto.create(modelo=MODELO_ADJUNTOS, registro_id=memoria_id, nombre=foto.nombre,
                       ruta=ruta, tamano=tamano, mimetype=mime)
    return get(memoria_id)


def create_label(nombre: str) -> EtiquetaMemoria:  # propio
    colores = ["teal", "orange", "pink", "amber", "purple", "blue", "green", "red"]
    EtiquetaMemoria.check_unique(nombre)
    return EtiquetaMemoria.create(nombre=nombre.strip(),
                                  color=colores[len(EtiquetaMemoria.search_all()) % len(colores)])

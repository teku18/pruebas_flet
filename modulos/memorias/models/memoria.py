"""
Modelos de Memorias: una bitácora de MOMENTOS importantes (no pendientes).
"Fui al cine en mi aniversario", "el viaje a Oaxaca", "cuando salí de X".

  Memoria  N ──< >── N  EtiquetaMemoria      (viaje, familia, pareja, logro…)
     │
     └── fotos: tabla única "adjuntos" (core/adjuntos.py), modelo "memoria",
         archivos en data/memorias/<id>/ y miniaturas en data/memorias/<id>/mini/

Campos:
  fecha    -> cuándo PASÓ (puede ser de hace años), no cuándo la capturaste
  animo    -> un emoji opcional ("🥰", "😢"…)
  origen   -> "texto" hoy; "voz" cuando exista el dictado (el audio irá como
              adjunto con mimetype audio/… y el relato será su transcripción).
              Así agregar la voz no requiere cambiar tablas.
"""
from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.adjuntos import Adjunto, attachments_relation
from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from core.storage import DATA_DIR, delete_folder

MODELO_ADJUNTOS = "memoria"
MEMORIAS_DIR = DATA_DIR / "memorias"

ORIGEN_SELECTION = {"texto": "Escrita", "voz": "Dictada"}
ANIMOS = ["🥰", "😄", "🤩", "😌", "🥲", "😢", "😮", "😤", "🙏", "🎉"]

memoria_etiqueta_rel = Table(
    "memoria_etiqueta_rel",
    Base.metadata,
    Column("memoria_id", ForeignKey("memorias.id"), primary_key=True),
    Column("etiqueta_id", ForeignKey("memoria_etiquetas.id"), primary_key=True),
)


class EtiquetaMemoria(CrudMixin, Base):
    __tablename__ = "memoria_etiquetas"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="bluegrey")

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        iguales = [e for e in cls.search(func.lower(cls.nombre) == nombre.strip().lower())
                   if e.id != excluir_id]
        if iguales:
            raise ValueError("Ya existe esa etiqueta")

    def __repr__(self) -> str:
        return f"<EtiquetaMemoria {self.nombre}>"


class Memoria(CrudMixin, Base):
    __tablename__ = "memorias"
    _orden = "fecha desc, id desc"  # lo más reciente arriba (línea de tiempo)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    relato: Mapped[str | None] = mapped_column(Text, nullable=True)
    lugar: Mapped[str | None] = mapped_column(String(150), nullable=True)
    animo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origen: Mapped[str] = mapped_column(String(10), nullable=False, default="texto")
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                     default=datetime.now,
                                                     onupdate=datetime.now)

    # selectin: etiquetas y fotos llegan con la memoria (la sesión ya cerró al pintar)
    etiquetas: Mapped[list["EtiquetaMemoria"]] = relationship(
        secondary=memoria_etiqueta_rel, lazy="selectin", order_by=EtiquetaMemoria.nombre)
    fotos: Mapped[list[Adjunto]] = attachments_relation("Memoria", MODELO_ADJUNTOS)

    def _validate(self) -> None:  # propio
        if not (self.titulo or "").strip():
            raise ValueError("Ponle un título")
        if self.fecha and self.fecha > date.today():
            raise ValueError("Una memoria es algo que ya pasó: la fecha no puede ser futura")

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """La fila (y su relación con etiquetas), sus fotos y su carpeta."""
        Adjunto.delete_for(MODELO_ADJUNTOS, registro_id)
        with SessionLocal() as session:
            memoria = session.get(cls, registro_id)
            if memoria is not None:
                memoria.etiquetas = []
                session.delete(memoria)
                session.commit()
        delete_folder(MEMORIAS_DIR / str(registro_id))

    def __repr__(self) -> str:
        return f"<Memoria id={self.id} {self.fecha} {self.titulo!r}>"

"""
Modelos de Notas:

  EtiquetaNota  1 ──< N  Nota  1 ──< N  NotaItem
  (Súper, Ideas…)        (texto o lista)  (las casillas de una lista)

Una nota es de uno de dos tipos:
  "texto" -> usa `cuerpo` (texto libre)
  "lista" -> usa sus `items` (cada uno con su casilla ✓)
Así una misma tabla guarda ambas y se puede convertir de una a otra.

`actualizado_en` ordena el tablero (lo último que tocaste, arriba) y lo pone
services.save_note(); no se usa onupdate de SQLAlchemy para que FIJAR o
ARCHIVAR no cuenten como "editar" y no muevan la nota de lugar.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

TIPO_NOTA_SELECTION = {"texto": "Nota", "lista": "Lista"}

# Colores de fondo de una nota (texto que entiende Flet; None = sin color)
COLORES_NOTA = ["red", "orange", "amber", "lightgreen", "teal", "lightblue",
                "indigo", "purple", "pink", "brown", "bluegrey"]


class EtiquetaNota(CrudMixin, Base):
    __tablename__ = "nota_etiquetas"
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

    @classmethod
    def usage_count(cls) -> dict[int, int]:  # propio
        with SessionLocal() as session:
            consulta = (select(Nota.etiqueta_id, func.count())
                        .where(Nota.etiqueta_id.is_not(None)).group_by(Nota.etiqueta_id))
            return dict(session.execute(consulta).all())

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Las notas que la usaban se quedan sin etiqueta (no se borran)."""
        with SessionLocal() as session:
            for nota in session.scalars(select(Nota).where(Nota.etiqueta_id == registro_id)):
                nota.etiqueta_id = None
            session.commit()
        super().delete(registro_id)

    def __repr__(self) -> str:
        return f"<EtiquetaNota {self.nombre}>"


class Nota(CrudMixin, Base):
    __tablename__ = "notas"
    _orden = "fijada desc, actualizado_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="texto")
    titulo: Mapped[str | None] = mapped_column(String(150), nullable=True)
    cuerpo: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    etiqueta_id: Mapped[int | None] = mapped_column(ForeignKey("nota_etiquetas.id"),
                                                    nullable=True)
    fijada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archivada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                     default=datetime.now)

    etiqueta: Mapped["EtiquetaNota | None"] = relationship(lazy="joined")
    # selectin: las casillas llegan con la nota (sin consultas extra al pintar)
    items: Mapped[list["NotaItem"]] = relationship(
        back_populates="nota", cascade="all, delete-orphan", lazy="selectin",
        order_by="NotaItem.secuencia",
    )

    @property
    def es_lista(self) -> bool:  # propio
        return self.tipo == "lista"

    @property
    def vacia(self) -> bool:  # propio
        """Sin título, sin texto y sin casillas con texto: se borra al salir del editor."""
        sin_items = not any((i.texto or "").strip() for i in self.items)
        return not (self.titulo or "").strip() and not (self.cuerpo or "").strip() and sin_items

    @property
    def avance(self) -> tuple[int, int]:  # propio
        """(hechas, total) de una lista."""
        return sum(1 for i in self.items if i.hecho), len(self.items)

    def __repr__(self) -> str:
        return f"<Nota id={self.id} {self.tipo} {self.titulo!r}>"


class NotaItem(CrudMixin, Base):
    __tablename__ = "nota_items"
    _orden = "secuencia asc, id asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("notas.id"), nullable=False)
    texto: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    hecho: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    nota: Mapped["Nota"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<NotaItem {'☑' if self.hecho else '☐'} {self.texto!r}>"

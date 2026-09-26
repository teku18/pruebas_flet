"""Modelos Entrada (un avance de la bitácora) y Adjunto (evidencia de la entrada)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from core.storage import delete_file


class Entrada(CrudMixin, Base):
    __tablename__ = "proyecto_entradas"
    _orden = "fecha_hora desc, id desc"  # la más reciente arriba

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notas: Mapped[str] = mapped_column(Text, nullable=False)

    proyecto: Mapped["Proyecto"] = relationship(back_populates="entradas")  # noqa: F821
    adjuntos: Mapped[list["Adjunto"]] = relationship(
        back_populates="entrada", cascade="all, delete-orphan"
    )

    def _validate(self) -> None:  # propio
        if not (self.notas or "").strip():
            raise ValueError("La entrada necesita notas")

    @classmethod
    def search_by_project(cls, proyecto_id: int) -> list["Entrada"]:  # propio
        """Entradas de un proyecto con sus adjuntos ya cargados."""
        from sqlalchemy import select, text

        with SessionLocal() as session:
            consulta = (
                select(cls)
                .where(cls.proyecto_id == proyecto_id)
                .options(selectinload(cls.adjuntos))
                .order_by(text(cls._orden))
            )
            return list(session.scalars(consulta))

    @classmethod
    def get_with_attachments(cls, entrada_id: int) -> "Entrada | None":  # propio
        with SessionLocal() as session:
            return session.get(cls, entrada_id, options=[selectinload(cls.adjuntos)])

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de las filas, borra los archivos de sus adjuntos."""
        entrada = cls.get_with_attachments(registro_id)
        rutas = [a.ruta for a in entrada.adjuntos] if entrada else []
        super().delete(registro_id)
        for ruta in rutas:
            delete_file(ruta)

    def __repr__(self) -> str:
        return f"<Entrada id={self.id} proyecto={self.proyecto_id} {self.fecha_hora}>"


class Adjunto(CrudMixin, Base):
    __tablename__ = "proyecto_adjuntos"
    _orden = "id asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entrada_id: Mapped[int] = mapped_column(ForeignKey("proyecto_entradas.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)   # nombre original
    ruta: Mapped[str] = mapped_column(String(500), nullable=False)     # relativa a data/
    tamano: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes

    entrada: Mapped["Entrada"] = relationship(back_populates="adjuntos")

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        adjunto = cls.get(registro_id)
        super().delete(registro_id)
        if adjunto:
            delete_file(adjunto.ruta)

    def __repr__(self) -> str:
        return f"<Adjunto id={self.id} {self.nombre}>"

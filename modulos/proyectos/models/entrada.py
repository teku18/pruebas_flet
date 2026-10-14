"""
Modelo Entrada: un avance de la bitácora de un proyecto.

Su evidencia (fotos, PDFs, capturas) va en la tabla única "adjuntos"
(core/adjuntos.py) con modelo "proyecto.entrada"; los archivos viven en
data/adjuntos/<proyecto_id>/<entrada_id>/.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from core.adjuntos import Adjunto, attachments_relation
from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from modulos.proyectos.models.catalogos import TipoEntrada

MODELO_ADJUNTOS = "proyecto.entrada"

# El tipo de entrada es un catálogo (TipoEntrada, en Ajustes). Los que tienen
# es_hito son los momentos importantes: con ellos se arma la línea de tiempo
# y el resumen del año; lo demás es el día a día.


class Entrada(CrudMixin, Base):
    __tablename__ = "proyecto_entradas"
    _orden = "fecha_hora desc, id desc"  # la más reciente arriba

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proyecto_id: Mapped[int] = mapped_column(ForeignKey("proyectos.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notas: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_id: Mapped[int] = mapped_column(ForeignKey("proyecto_tipos_entrada.id"), nullable=False)

    tipo: Mapped["TipoEntrada"] = relationship(lazy="joined")  # viene con la entrada

    proyecto: Mapped["Proyecto"] = relationship(back_populates="entradas")  # noqa: F821
    # Solo lectura: se agregan/quitan con Adjunto.create / Adjunto.delete
    adjuntos: Mapped[list[Adjunto]] = attachments_relation("Entrada", MODELO_ADJUNTOS)

    @property
    def tipo_label(self) -> str:  # propio
        return self.tipo.nombre if self.tipo else ""

    @property
    def es_hito(self) -> bool:  # propio
        return bool(self.tipo and self.tipo.es_hito)

    def _validate(self) -> None:  # propio
        if not (self.notas or "").strip():
            raise ValueError("La entrada necesita notas")

    @classmethod
    def search_by_project(cls, proyecto_id: int, tipo_id: int | None = None) -> list["Entrada"]:  # propio
        """Entradas de un proyecto (todas, o solo de un tipo) con sus adjuntos ya cargados."""
        from sqlalchemy import select, text

        with SessionLocal() as session:
            consulta = (
                select(cls)
                .where(cls.proyecto_id == proyecto_id)
                .options(selectinload(cls.adjuntos))
                .order_by(text(cls._order_sql()))
            )
            if tipo_id:
                consulta = consulta.where(cls.tipo_id == tipo_id)
            return list(session.scalars(consulta))

    @classmethod
    def get_with_attachments(cls, entrada_id: int) -> "Entrada | None":  # propio
        with SessionLocal() as session:
            return session.get(cls, entrada_id, options=[selectinload(cls.adjuntos)])

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de la fila, borra sus adjuntos (filas y archivos)."""
        Adjunto.delete_for(MODELO_ADJUNTOS, registro_id)
        super().delete(registro_id)

    def __repr__(self) -> str:
        return f"<Entrada id={self.id} proyecto={self.proyecto_id} {self.fecha_hora}>"

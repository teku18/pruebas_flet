"""Modelo Periodo: cabecera que agrupa movimientos en un rango de fechas."""
from datetime import date

from sqlalchemy import Date, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, SessionLocal
from core.mixins import CrudMixin


class Periodo(CrudMixin, Base):
    __tablename__ = "periodos"
    _orden = "fecha_inicio desc, id desc"  # del más reciente al más antiguo

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)

    # Un periodo tiene muchos movimientos (One2many).
    # cascade: al borrar el periodo se borran también sus movimientos.
    movimientos: Mapped[list["Movimiento"]] = relationship(  # noqa: F821
        back_populates="periodo", cascade="all, delete-orphan"
    )

    # --- Validación (la llama CrudMixin en create y update) ----------------
    def _validate(self) -> None:  # propio
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha fin no puede ser anterior a la fecha inicio")

    # --- Consultas propias de este modelo ----------------------------------
    @classmethod
    def count_movements(cls) -> dict[int, int]:  # propio
        """{periodo_id: cantidad de movimientos} para mostrar en la lista."""
        # Import local para evitar importación circular entre los dos modelos
        from modulos.finanzas.models.movimiento import Movimiento

        with SessionLocal() as session:
            consulta = select(Movimiento.periodo_id, func.count()).group_by(
                Movimiento.periodo_id
            )
            return dict(session.execute(consulta).all())

    def __repr__(self) -> str:
        return f"<Periodo id={self.id} {self.nombre} {self.fecha_inicio}..{self.fecha_fin}>"

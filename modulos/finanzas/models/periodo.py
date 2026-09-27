"""
Modelo Periodo: un "libro" de movimientos en un rango de fechas
(p. ej. "Inversiones 2026" y "Gastos 2026" pueden estar abiertos a la vez).

Ciclo de vida:
  1. Se crea en la app            -> abre en $0 (sin saldos iniciales)
  2. Se registran movimientos
  3. Se cierra                    -> queda en solo lectura (cerrado=True) y se
                                     crea el siguiente con un saldo inicial por
                                     cada concepto/plataforma (origen_id = este)
El acumulado global suma solo los periodos ABIERTOS, así el dinero de un
periodo cerrado no se cuenta dos veces (ya vive en los saldos del siguiente).
"""
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, func, select
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

    # Cerrado = solo lectura y fuera del acumulado global
    cerrado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Periodo del que viene (el que se cerró para abrir este). None = creado a mano
    origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("periodos.id", name="fk_periodos_origen"), nullable=True
    )

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

    @classmethod
    def children(cls, periodo_id: int) -> list["Periodo"]:  # propio
        """Periodos que se abrieron al cerrar este."""
        return cls.search(cls.origen_id == periodo_id)

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Al borrar un periodo, los que se abrieron con su cierre quedan sin origen."""
        with SessionLocal() as session:
            for hijo in session.scalars(select(cls).where(cls.origen_id == registro_id)):
                hijo.origen_id = None
            session.delete(cls._get_or_raise(session, registro_id))
            session.commit()

    def __repr__(self) -> str:
        return f"<Periodo id={self.id} {self.nombre} {self.fecha_inicio}..{self.fecha_fin}>"

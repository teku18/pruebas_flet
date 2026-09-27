"""
Catálogos de Finanzas: Plataforma e Inversión.

Antes eran Selection (listas fijas en el código); ahora son tablas, para
poder darlas de alta desde la app. Movimiento las apunta con un Many2one
(plataforma_id, inversion_id).

"activo" funciona como `active` en Odoo: lo archivado ya no sale en los
desplegables, pero los movimientos viejos lo siguen mostrando.
"""
from sqlalchemy import Boolean, Float, Integer, String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, SessionLocal
from core.mixins import CrudMixin


class CatalogMixin(CrudMixin):
    """Campos y métodos comunes de un catálogo sencillo (nombre + activo)."""

    _orden = "activo desc, nombre asc"   # activos primero, luego alfabético
    _campo_movimiento = ""               # columna de Movimiento que lo apunta

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def _validate(self) -> None:  # propio
        self.nombre = (self.nombre or "").strip()
        if not self.nombre:
            raise ValueError("El nombre es obligatorio")

    # --- Consultas -----------------------------------------------------
    @classmethod
    def search_for_dropdown(cls, incluir_id: int | None = None) -> list:  # propio
        """Los activos, más el actual aunque esté archivado (al ver un registro viejo)."""
        condicion = cls.activo.is_(True)
        if incluir_id is not None:
            condicion = condicion | (cls.id == incluir_id)
        return cls.search(condicion)

    @classmethod
    def find_by_name(cls, nombre: str, session=None):  # propio
        """Busca sin importar mayúsculas: 'yotepresto' encuentra 'YoTepresto'."""
        consulta = select(cls).where(func.lower(cls.nombre) == nombre.strip().lower())
        if session is not None:
            return session.scalars(consulta).first()
        with SessionLocal() as s:
            return s.scalars(consulta).first()

    @classmethod
    def get_or_create(cls, nombre: str, session):  # propio
        """Para el importador: usa el existente o lo crea dentro de la misma sesión."""
        registro = cls.find_by_name(nombre, session)
        if registro is None:
            registro = cls(nombre=nombre.strip(), activo=True)
            registro._validate()
            session.add(registro)
            session.flush()  # asigna el id sin cerrar la transacción
        return registro

    @classmethod
    def usage_count(cls) -> dict[int, int]:  # propio
        """{id: cuántos movimientos lo usan} -> para saber si se puede borrar."""
        from modulos.finanzas.models.movimiento import Movimiento

        columna = getattr(Movimiento, cls._campo_movimiento)
        with SessionLocal() as session:
            consulta = select(columna, func.count()).group_by(columna)
            return dict(session.execute(consulta).all())

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        """Error claro si ya existe otro con el mismo nombre."""
        otro = cls.find_by_name(nombre)
        if otro is not None and otro.id != excluir_id:
            raise ValueError(f"Ya existe «{otro.nombre}»")


class Plataforma(CatalogMixin, Base):
    __tablename__ = "plataformas"
    _campo_movimiento = "plataforma_id"

    def __repr__(self) -> str:
        return f"<Plataforma id={self.id} {self.nombre}>"


class Inversion(CatalogMixin, Base):
    """En pantalla se llama "Concepto" (Reto Ahorro, Casa...)."""
    __tablename__ = "inversiones"
    _campo_movimiento = "inversion_id"

    # Cuánto quieres juntar en este concepto (opcional). Los reportes muestran
    # el avance: Meta $520,000 · Falta $14,026.69
    meta: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<Inversion id={self.id} {self.nombre}>"

"""Modelo Movimiento: detalle de un periodo."""
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from database import Base
from models.mixins import CrudMixin

# ---------------------------------------------------------------------------
# Opciones de los campos Selection  ->  {clave_guardada_en_bd: "Etiqueta visible"}
# Edita estas listas libremente; la BD guarda solo la clave.
# ---------------------------------------------------------------------------
INVERSION_SELECTION = {
    "reto_ahorro": "Reto Ahorro",
    "casa": "Casa",
}

PLATAFORMA_SELECTION = {
    "gbm": "GBM+",
    "cetes_directo": "Cetes Directo",
    "nu": "Nu",
    "bitso": "Bitso",
    "yotepresto": "YoTepresto",
    "finsus": "Finsus",
    "mercado_pago": "Mercado pago",
    "uala": "Uala",
    "stori": "Stori",
}

TIPO_SELECTION = {
    "deposito": "Depósito",
    "retiro": "Retiro",
    "rendimiento": "Rendimiento",
}


class Movimiento(CrudMixin, Base):
    __tablename__ = "movimientos"
    _orden = "fecha desc, id desc"  # del más reciente al más antiguo

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inversion: Mapped[str] = mapped_column(String(50), nullable=False)    # Selection
    monto: Mapped[float] = mapped_column(Float, nullable=False)           # Float
    plataforma: Mapped[str] = mapped_column(String(50), nullable=False)   # Selection
    fecha: Mapped[date] = mapped_column(Date, nullable=False)             # Date
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)         # Selection
    comentarios: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Char

    # Periodo al que pertenece (Many2one / llave foránea)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos.id"), nullable=False)
    periodo: Mapped["Periodo"] = relationship(back_populates="movimientos")  # noqa: F821

    # --- Validaciones de los campos Selection -----------------------------
    @validates("inversion")
    def _validar_inversion(self, key, value):
        return _validar_seleccion(key, value, INVERSION_SELECTION)

    @validates("plataforma")
    def _validar_plataforma(self, key, value):
        return _validar_seleccion(key, value, PLATAFORMA_SELECTION)

    @validates("tipo")
    def _validar_tipo(self, key, value):
        return _validar_seleccion(key, value, TIPO_SELECTION)

    # --- Etiquetas legibles (como display_name de un Selection) -----------
    @property
    def inversion_label(self) -> str:
        return INVERSION_SELECTION.get(self.inversion, self.inversion)

    @property
    def plataforma_label(self) -> str:
        return PLATAFORMA_SELECTION.get(self.plataforma, self.plataforma)

    @property
    def tipo_label(self) -> str:
        return TIPO_SELECTION.get(self.tipo, self.tipo)

    # --- Consultas propias de este modelo ----------------------------------
    # create / get / search / search_all / update / delete vienen de CrudMixin
    @classmethod
    def search_by_periodo(cls, periodo_id: int) -> list["Movimiento"]:
        """Detalle de un periodo, del más reciente al más antiguo."""
        return cls.search(cls.periodo_id == periodo_id)

    def __repr__(self) -> str:
        return (
            f"<Movimiento id={self.id} {self.tipo} {self.monto} "
            f"{self.inversion}@{self.plataforma} {self.fecha}>"
        )


def _validar_seleccion(campo: str, valor: str, opciones: dict) -> str:
    if valor not in opciones:
        raise ValueError(
            f"Valor '{valor}' no válido para '{campo}'. Opciones: {list(opciones)}"
        )
    return valor

"""Modelos ORM de la aplicación."""
from datetime import date

from sqlalchemy import Date, Float, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, validates

from database import Base, SessionLocal

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


class Movimiento(Base):
    __tablename__ = "movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inversion: Mapped[str] = mapped_column(String(50), nullable=False)    # Selection
    monto: Mapped[float] = mapped_column(Float, nullable=False)           # Float
    plataforma: Mapped[str] = mapped_column(String(50), nullable=False)   # Selection
    fecha: Mapped[date] = mapped_column(Date, nullable=False)             # Date
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)         # Selection
    comentarios: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Char

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

    # --- Métodos de acceso a datos (sin SQL a mano) ------------------------
    @classmethod
    def create(cls, **valores) -> "Movimiento":
        with SessionLocal() as session:
            movimiento = cls(**valores)
            session.add(movimiento)
            session.commit()
            session.refresh(movimiento)
            return movimiento

    @classmethod
    def search_all(cls) -> list["Movimiento"]:
        with SessionLocal() as session:
            consulta = select(cls).order_by(cls.id.desc())
            return list(session.scalars(consulta))

    @classmethod
    def update(cls, movimiento_id: int, **valores) -> "Movimiento":
        with SessionLocal() as session:
            movimiento = session.get(cls, movimiento_id)
            if movimiento is None:
                raise ValueError(f"No existe el movimiento con id={movimiento_id}")
            for campo, valor in valores.items():
                setattr(movimiento, campo, valor)
            session.commit()
            session.refresh(movimiento)
            return movimiento

    @classmethod
    def delete(cls, movimiento_id: int) -> None:
        with SessionLocal() as session:
            movimiento = session.get(cls, movimiento_id)
            if movimiento is None:
                raise ValueError(f"No existe el movimiento con id={movimiento_id}")
            session.delete(movimiento)
            session.commit()

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

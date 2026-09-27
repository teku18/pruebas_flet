"""
Modelo Movimiento: detalle de un periodo.

Cada movimiento es una entrada (+) o una salida (-) de dinero en una plataforma.
El "tipo" dice qué clase de entrada o salida es, y eso decide cómo cuenta
en los reportes:

  Tipo              Signo  ¿Cuenta como ingreso/gasto?
  saldo_inicial       +    No: es con lo que arrancas (se usa la primera vez)
  deposito            +    Sí, ingreso (ahorro, pagos que recibes, regalos)
  rendimiento         +    Sí, ingreso (ganancias de la inversión)
  retiro              -    Sí, gasto (pagos, retiros)
  traspaso_salida     -    No: el dinero solo se mueve de plataforma
  traspaso_entrada    +    No: la otra mitad del traspaso

Un traspaso son DOS movimientos ligados por el mismo traspaso_grupo; se crean,
y se borran, siempre juntos. Puede mover dinero entre plataformas (Nu -> Finsus),
entre conceptos (Vacaciones -> Mio) o ambas cosas a la vez.

Saldo inicial: normalmente positivo; puede ser negativo solo si el periodo
anterior cerró en negativo en ese concepto/plataforma (p. ej. una deuda).
"""
import uuid
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

TIPO_SELECTION = {
    "saldo_inicial": "Saldo inicial",
    "deposito": "Depósito",
    "rendimiento": "Rendimiento",
    "retiro": "Retiro",
    "traspaso_salida": "Traspaso (sale)",
    "traspaso_entrada": "Traspaso (entra)",
}

# +1 entra dinero, -1 sale dinero
SIGNO_TIPO = {
    "saldo_inicial": 1,
    "deposito": 1,
    "rendimiento": 1,
    "retiro": -1,
    "traspaso_salida": -1,
    "traspaso_entrada": 1,
}

# Los que se capturan a mano en el formulario (los traspasos tienen su herramienta)
TIPOS_MANUALES = ["deposito", "rendimiento", "retiro", "saldo_inicial"]
TIPOS_TRASPASO = {"traspaso_salida", "traspaso_entrada"}
TIPOS_INGRESO = {"deposito", "rendimiento"}
TIPOS_GASTO = {"retiro"}


class Movimiento(CrudMixin, Base):
    __tablename__ = "movimientos"
    _orden = "fecha desc, id desc"  # del más reciente al más antiguo

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monto: Mapped[float] = mapped_column(Float, nullable=False)          # siempre positivo
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)        # Selection
    comentarios: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Many2one a los catálogos. lazy="joined": se cargan junto con el movimiento,
    # así mov.plataforma.nombre funciona aunque la sesión ya se haya cerrado.
    inversion_id: Mapped[int] = mapped_column(
        ForeignKey("inversiones.id", name="fk_movimientos_inversion"), nullable=False
    )
    plataforma_id: Mapped[int] = mapped_column(
        ForeignKey("plataformas.id", name="fk_movimientos_plataforma"), nullable=False
    )
    inversion: Mapped["Inversion"] = relationship(lazy="joined")    # noqa: F821
    plataforma: Mapped["Plataforma"] = relationship(lazy="joined")  # noqa: F821

    # Liga las dos mitades de un traspaso (None en un movimiento normal)
    traspaso_grupo: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Periodo al que pertenece (Many2one)
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodos.id"), nullable=False)
    periodo: Mapped["Periodo"] = relationship(back_populates="movimientos")  # noqa: F821

    # --- Validaciones ------------------------------------------------------
    @validates("tipo")
    def _validate_tipo(self, key, value):  # propio
        if value not in TIPO_SELECTION:
            raise ValueError(f"Tipo no válido: {value}. Opciones: {list(TIPO_SELECTION)}")
        return value

    def _validate(self) -> None:  # propio
        if self.monto is None or self.monto == 0:
            raise ValueError("El monto no puede ser cero")
        if self.monto < 0 and self.tipo != "saldo_inicial":
            raise ValueError("El monto debe ser mayor a cero")

    # --- Propiedades de apoyo ----------------------------------------------
    @property
    def tipo_label(self) -> str:  # propio
        return TIPO_SELECTION.get(self.tipo, self.tipo)

    @property
    def inversion_label(self) -> str:  # propio
        return self.inversion.nombre if self.inversion else ""

    @property
    def plataforma_label(self) -> str:  # propio
        return self.plataforma.nombre if self.plataforma else ""

    @property
    def signo(self) -> int:  # propio
        return SIGNO_TIPO.get(self.tipo, 1)

    @property
    def monto_con_signo(self) -> float:  # propio
        return self.signo * self.monto

    @property
    def es_traspaso(self) -> bool:  # propio
        return self.tipo in TIPOS_TRASPASO

    # --- Consultas -----------------------------------------------------------
    @classmethod
    def search_by_period(cls, periodo_id: int) -> list["Movimiento"]:  # propio
        """Detalle de un periodo, del más reciente al más antiguo."""
        return cls.search(cls.periodo_id == periodo_id)

    @classmethod
    def search_transfer(cls, grupo: str) -> list["Movimiento"]:  # propio
        """Las dos mitades de un traspaso."""
        return cls.search(cls.traspaso_grupo == grupo)

    # --- Traspasos: se crean y borran en pareja ------------------------------
    @classmethod
    def create_transfer(  # propio
        cls, *, periodo_id: int, monto: float, fecha: date,
        origen_inversion_id: int, origen_plataforma_id: int,
        destino_inversion_id: int, destino_plataforma_id: int,
        comentarios: str | None = None,
    ) -> str:
        """
        Crea la salida del origen y la entrada al destino en UNA transacción.
        Origen y destino son (concepto, plataforma); al menos uno debe cambiar.
        """
        if (origen_inversion_id, origen_plataforma_id) == (destino_inversion_id,
                                                          destino_plataforma_id):
            raise ValueError("El origen y el destino deben ser distintos")
        grupo = uuid.uuid4().hex
        comunes = dict(periodo_id=periodo_id, monto=monto, fecha=fecha,
                       comentarios=comentarios, traspaso_grupo=grupo)
        mitades = (("traspaso_salida", origen_inversion_id, origen_plataforma_id),
                   ("traspaso_entrada", destino_inversion_id, destino_plataforma_id))
        with SessionLocal() as session:
            for tipo, inversion_id, plataforma_id in mitades:
                mov = cls(tipo=tipo, inversion_id=inversion_id,
                          plataforma_id=plataforma_id, **comunes)
                mov._validate()
                session.add(mov)
            session.commit()  # si algo falla, no se guarda ninguna de las dos
        return grupo

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Si es parte de un traspaso, borra también su pareja."""
        with SessionLocal() as session:
            mov = cls._get_or_raise(session, registro_id)
            if mov.traspaso_grupo:
                pareja = select(cls).where(cls.traspaso_grupo == mov.traspaso_grupo)
                for m in session.scalars(pareja).unique():
                    session.delete(m)
            else:
                session.delete(mov)
            session.commit()

    def __repr__(self) -> str:
        return f"<Movimiento id={self.id} {self.tipo} {self.monto} {self.fecha}>"

"""Configuración de la base de datos (SQLAlchemy ORM + SQLite)."""
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# El archivo .db se crea junto a main.py
DB_PATH = Path(__file__).resolve().parent / "movimientos.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


def init_db():
    """Crea las tablas de todos los modelos si aún no existen."""
    import models  # noqa: F401  (registra los modelos en Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrar_periodo_en_movimientos()


def _migrar_periodo_en_movimientos():
    """
    Migración para BDs creadas antes de que existiera Periodo.

    create_all() crea tablas nuevas, pero NO agrega columnas a tablas que
    ya existen. Aquí se agrega movimientos.periodo_id y los movimientos que
    ya había se asignan a un periodo "Movimientos anteriores".
    No borra ningún dato. En una BD nueva no hace nada.
    """
    columnas = [c["name"] for c in inspect(engine).get_columns("movimientos")]

    with engine.begin() as conn:
        if "periodo_id" not in columnas:
            conn.execute(
                text(
                    "ALTER TABLE movimientos "
                    "ADD COLUMN periodo_id INTEGER REFERENCES periodos(id)"
                )
            )

        cantidad, primera_fecha, ultima_fecha = conn.execute(
            text(
                "SELECT COUNT(*), MIN(fecha), MAX(fecha) "
                "FROM movimientos WHERE periodo_id IS NULL"
            )
        ).one()
        if cantidad:
            nuevo_id = conn.execute(
                text(
                    "INSERT INTO periodos (nombre, fecha_inicio, fecha_fin) "
                    "VALUES ('Movimientos anteriores', :inicio, :fin)"
                ),
                {"inicio": primera_fecha, "fin": ultima_fecha},
            ).lastrowid
            conn.execute(
                text("UPDATE movimientos SET periodo_id = :id WHERE periodo_id IS NULL"),
                {"id": nuevo_id},
            )

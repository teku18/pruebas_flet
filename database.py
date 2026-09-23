"""Configuración de la base de datos (SQLAlchemy ORM + SQLite)."""
from pathlib import Path

from sqlalchemy import create_engine
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

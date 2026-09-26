"""
Configuración de la base de datos (SQLAlchemy ORM + SQLite) y migraciones (Alembic).

Flujo al abrir la app (init_db):
  1. Si la BD es de antes de Alembic, se marca como "ya tiene la versión 0001"
  2. alembic upgrade head -> aplica las migraciones que falten, sin perder datos
"""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Raíz del proyecto (core/ está un nivel abajo, por eso .parent.parent)
ROOT_DIR = Path(__file__).resolve().parent.parent

# El archivo .db vive en la raíz del proyecto, junto a main.py
DB_PATH = ROOT_DIR / "movimientos.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Revisión que corresponde a las tablas que ya existían antes de Alembic
BASELINE_REVISION = "0001"


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


def import_models():  # propio
    """
    Registra en Base.metadata los modelos de todos los módulos.
    Alembic lo usa para comparar tus modelos contra la BD (--autogenerate).
    Al crear un módulo con modelos, agrega aquí su import.
    """
    import modulos.finanzas.models  # noqa: F401
    import modulos.proyectos.models  # noqa: F401


def alembic_config() -> Config:  # propio
    """Configuración de Alembic armada desde Python (no depende de alembic.ini)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    return cfg


def init_db():  # propio
    """Deja la BD al día: aplica las migraciones pendientes."""
    import_models()
    cfg = alembic_config()

    tablas = inspect(engine).get_table_names()
    if "movimientos" in tablas and "alembic_version" not in tablas:
        # BD creada antes de usar Alembic: ya tiene lo de la migración 0001.
        # "stamp" solo anota la versión, no toca tus datos.
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")

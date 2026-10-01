"""
Configuración de la base de datos (SQLAlchemy ORM + SQLite) y migraciones (Alembic).

Flujo al abrir la app (init_db):
  1. Si la BD es de antes de Alembic, se marca como "ya tiene la versión 0001"
  2. Si hay migraciones pendientes (actualizaste la app), copia de seguridad
     local en respaldos/ (core/backup.py)
  3. alembic upgrade head -> aplica las migraciones que falten, sin perder datos
Si la BD no existía, BD_NUEVA queda en True: la app ofrece restaurar un respaldo.
"""
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Raíz del proyecto (core/ está un nivel abajo, por eso .parent.parent)
ROOT_DIR = Path(__file__).resolve().parent.parent

# ¿Corre INSTALADA en el celular (APK)? Android define ANDROID_ROOT/ANDROID_DATA.
# Con `flet run` + QR, Python corre en la compu: eso NO cuenta como celular.
ES_MOVIL = bool(os.getenv("ANDROID_ROOT") or os.getenv("ANDROID_DATA")) or sys.platform in (
    "android", "ios")

# Dónde viven los DATOS (BD, data/, respaldos/):
#   compu   -> la raíz del proyecto, como siempre
#   celular -> la carpeta privada de la app (FLET_APP_STORAGE_DATA), que NO se
#              borra al actualizar el APK (la carpeta del código sí puede cambiar)
# Ojo: `flet run` también define FLET_APP_STORAGE_DATA (.flet/storage/data);
# por eso solo se usa en el celular, si no la BD de la compu "desaparecería".
_DATOS_APP = os.getenv("FLET_APP_STORAGE_DATA")
DATA_ROOT = Path(_DATOS_APP) if ES_MOVIL and _DATOS_APP else ROOT_DIR
DATA_ROOT.mkdir(parents=True, exist_ok=True)

# El archivo .db: en la compu, junto a main.py
DB_PATH = DATA_ROOT / "ControlKraken.db"
# Nombre que tenía antes: los respaldos viejos lo traen así (se aceptan al restaurar)
DB_NOMBRES_ANTERIORES = ("movimientos.db",)
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# True si al abrir la app no había BD (equipo nuevo): se ofrece restaurar
BD_NUEVA = False

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
    import modulos.agenda.models  # noqa: F401
    import modulos.desarrollo.models  # noqa: F401


def alembic_config() -> Config:  # propio
    """Configuración de Alembic armada desde Python (no depende de alembic.ini)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    # En el APK las migraciones pueden quedar como .pyc (sin el .py):
    # "sourceless" le permite a Alembic encontrarlas igual.
    cfg.set_main_option("sourceless", "true")
    return cfg


def init_db():  # propio
    """Deja la BD al día: aplica las migraciones pendientes."""
    global BD_NUEVA
    from core.backup import backup_before_migrate  # aquí para evitar import circular

    BD_NUEVA = not DB_PATH.exists()
    import_models()
    cfg = alembic_config()

    tablas = inspect(engine).get_table_names()
    if "movimientos" in tablas and "alembic_version" not in tablas:
        # BD creada antes de usar Alembic: ya tiene lo de la migración 0001.
        # "stamp" solo anota la versión, no toca tus datos.
        command.stamp(cfg, BASELINE_REVISION)

    backup_before_migrate()  # solo hace algo si hay migraciones pendientes
    command.upgrade(cfg, "head")

"""
Entorno de Alembic: le dice a qué BD conectarse y qué modelos comparar.
Lo usan tanto la terminal (alembic ...) como init_db() al abrir la app.
"""
from logging.config import fileConfig

from alembic import context

from core.database import DATABASE_URL, Base, engine, import_models

config = context.config

# Logs solo cuando se corre desde la terminal (con alembic.ini)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Todos los modelos registrados -> autogenerate puede detectar los cambios
import_models()
target_metadata = Base.metadata


def run_migrations_offline() -> None:  # propio
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:  # propio
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite casi no sabe hacer ALTER TABLE; el modo "batch" copia la
            # tabla con el cambio y la reemplaza. Necesario para renombrar o
            # quitar columnas en SQLite.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Desarrollo: módulos de la app y sus pendientes (roadmap)

- dev_modulos:    nombre, descripción, prioridad (alta|media|baja) y % de avance
- dev_pendientes: tarea | error | comentario de un módulo, con prioridad y
                  si ya está hecho (hecho_en = cuándo)

Datos iniciales: los módulos actuales con su avance de hoy
(Finanzas 95 %, Proyectos 50 %, Agenda 50 %, Memorias 0 %).

Revisión: 0009
Anterior: 0008
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    modulos = op.create_table(
        "dev_modulos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("prioridad", sa.String(length=10), nullable=False),
        sa.Column("avance", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "dev_pendientes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("modulo_id", sa.Integer(), sa.ForeignKey("dev_modulos.id"), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("prioridad", sa.String(length=10), nullable=False),
        sa.Column("hecho", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
        sa.Column("hecho_en", sa.DateTime(), nullable=True),
    )

    # Punto de partida (luego se ajusta desde la app)
    ahora = datetime.now().replace(microsecond=0)
    op.bulk_insert(
        modulos,
        [
            dict(nombre="Finanzas", descripcion="Periodos, movimientos y reportes",
                 prioridad="media", avance=95, creado_en=ahora),
            dict(nombre="Proyectos", descripcion="Bitácora de avances",
                 prioridad="media", avance=50, creado_en=ahora),
            dict(nombre="Agenda", descripcion="Pendientes, tareas y chismoso",
                 prioridad="media", avance=50, creado_en=ahora),
            dict(nombre="Memorias", descripcion="Pensamientos por voz (próximamente)",
                 prioridad="baja", avance=0, creado_en=ahora),
        ],
    )


def downgrade() -> None:
    op.drop_table("dev_pendientes")
    op.drop_table("dev_modulos")

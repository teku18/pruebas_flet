"""Proyectos: proyectos, entradas de bitácora y adjuntos

Revisión: 0002
Anterior: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proyectos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
    )
    op.create_table(
        "proyecto_entradas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos.id"), nullable=False),
        sa.Column("fecha_hora", sa.DateTime(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=False),
    )
    op.create_table(
        "proyecto_adjuntos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "entrada_id", sa.Integer(), sa.ForeignKey("proyecto_entradas.id"), nullable=False
        ),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("proyecto_adjuntos")
    op.drop_table("proyecto_entradas")
    op.drop_table("proyectos")

"""Finanzas inicial: periodos y movimientos

Es la foto de las tablas que ya existían antes de usar Alembic.
En tu BD actual no se ejecuta: init_db() solo la marca como aplicada (stamp).
En una BD nueva (otro celular, otra compu) crea las tablas desde cero.

Revisión: 0001
Anterior: (ninguna)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "periodos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
    )
    op.create_table(
        "movimientos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("inversion", sa.String(length=50), nullable=False),
        sa.Column("monto", sa.Float(), nullable=False),
        sa.Column("plataforma", sa.String(length=50), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("comentarios", sa.String(length=255), nullable=True),
        sa.Column("periodo_id", sa.Integer(), sa.ForeignKey("periodos.id"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("movimientos")
    op.drop_table("periodos")

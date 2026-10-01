"""Desarrollo: adjuntos de los pendientes (archivos, capturas y grabaciones)

- dev_adjuntos: nombre, ruta relativa a data/ y tamaño, de un pendiente.
  Los archivos viven en data/desarrollo/<pendiente_id>/

Revisión: 0010
Anterior: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dev_adjuntos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pendiente_id", sa.Integer(), sa.ForeignKey("dev_pendientes.id"),
                  nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("dev_adjuntos")

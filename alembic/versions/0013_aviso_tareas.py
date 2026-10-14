"""Agenda: aviso por tarea (notificaciones en el celular)

- tareas.aviso_min: minutos ANTES de la hora de la tarea para avisar.
    0    = a la hora (sin hora: a las 8:00 am de ese día)
    15   = 15 minutos antes ...  1440 = un día antes
    NULL = sin aviso
  Las tareas que ya existían quedan con aviso a la hora (0).

Revisión: 0013
Anterior: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tareas") as batch:
        batch.add_column(sa.Column("aviso_min", sa.Integer(), nullable=True))
    op.execute("UPDATE tareas SET aviso_min = 0")


def downgrade() -> None:
    with op.batch_alter_table("tareas") as batch:
        batch.drop_column("aviso_min")

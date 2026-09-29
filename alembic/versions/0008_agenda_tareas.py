"""Agenda: tareas y su historial de cumplimientos

- tareas: con o sin proyecto (proyecto_id NULL = tarea suelta), próxima
  fecha, horario opcional y frecuencia (única, diaria, L-V, semanal, mensual)
- tarea_cumplimientos: cada vez que se marca una tarea como hecha

Revisión: 0008
Anterior: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tareas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos.id"), nullable=True),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=True),
        sa.Column("hora_fin", sa.Time(), nullable=True),
        sa.Column("frecuencia", sa.String(length=20), nullable=False),
        sa.Column("completada", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "tarea_cumplimientos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tarea_id", sa.Integer(), sa.ForeignKey("tareas.id"), nullable=False),
        sa.Column("fecha_programada", sa.Date(), nullable=False),
        sa.Column("hecho_en", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tarea_cumplimientos")
    op.drop_table("tareas")

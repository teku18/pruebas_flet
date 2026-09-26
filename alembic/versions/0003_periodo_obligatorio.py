"""Movimiento.periodo_id obligatorio (NOT NULL)

La migración manual de antes agregó periodo_id con ALTER TABLE, y SQLite la
dejó como "puede ser nulo", aunque el modelo dice nullable=False.
`alembic check` lo detectó; esta migración alinea la BD con el modelo.

SQLite no permite cambiar NOT NULL con ALTER, por eso se usa batch_alter_table:
copia la tabla con el cambio y la reemplaza (tus datos se conservan).

Revisión: 0003
Anterior: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sin_periodo = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM movimientos WHERE periodo_id IS NULL")
    ).scalar()
    if sin_periodo:
        raise RuntimeError(
            f"Hay {sin_periodo} movimiento(s) sin periodo; asígnalos antes de migrar."
        )
    with op.batch_alter_table("movimientos") as batch:
        batch.alter_column("periodo_id", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("movimientos") as batch:
        batch.alter_column("periodo_id", existing_type=sa.Integer(), nullable=True)

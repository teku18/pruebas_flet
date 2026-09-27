"""Periodo cerrado + periodo de origen

- periodos.cerrado: True = solo lectura y fuera del acumulado global
- periodos.origen_id: el periodo que se cerró para abrir este (NULL si se creó a mano)

Los periodos que ya existen quedan abiertos (cerrado = 0) y sin origen.

Revisión: 0006
Anterior: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("periodos") as batch:
        # server_default: las filas existentes reciben 0 (abierto)
        batch.add_column(sa.Column("cerrado", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column("origen_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_periodos_origen", "periodos", ["origen_id"], ["id"])
    # Ya con los datos llenos, se quita el default de la BD (el modelo pone False)
    with op.batch_alter_table("periodos") as batch:
        batch.alter_column("cerrado", existing_type=sa.Boolean(), server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("periodos") as batch:
        batch.drop_constraint("fk_periodos_origen", type_="foreignkey")
        batch.drop_column("origen_id")
        batch.drop_column("cerrado")

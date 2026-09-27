"""Meta por concepto (inversiones.meta)

Cambio sencillo de estructura: una columna nueva y opcional. No mueve datos,
así que esta receta es la que autogenerate escribiría casi igual.

Revisión: 0005
Anterior: 0004
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("inversiones") as batch:
        batch.add_column(sa.Column("meta", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("inversiones") as batch:
        batch.drop_column("meta")

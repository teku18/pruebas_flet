"""Proyectos: seguimiento (fecha fin, destacado, tipo de entrada)

- proyectos.fecha_fin:  cuándo terminó (o se canceló). NULL = sigue vivo
- proyectos.destacado:  para el resumen del año
- proyectos.creado_en:  cuándo se registró en la app
- proyecto_entradas.tipo: avance | hito | problema | cierre

Datos que ya existen:
  - proyectos terminados -> fecha_fin = fecha de su última entrada
    (o la de inicio si no tiene entradas)
  - creado_en = fecha_inicio (no sabemos cuándo se capturaron)
  - todas las entradas quedan como "avance"

Revisión: 0007
Anterior: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("proyectos") as batch:
        batch.add_column(sa.Column("fecha_fin", sa.Date(), nullable=True))
        batch.add_column(sa.Column("destacado", sa.Boolean(), nullable=False,
                                   server_default=sa.false()))
        batch.add_column(sa.Column("creado_en", sa.DateTime(), nullable=True))
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.add_column(sa.Column("tipo", sa.String(length=20), nullable=False,
                                   server_default="avance"))

    # Rellenar lo que ya existe
    op.execute("UPDATE proyectos SET creado_en = fecha_inicio || ' 00:00:00.000000'")
    op.execute(
        """
        UPDATE proyectos
        SET fecha_fin = COALESCE(
            (SELECT date(max(e.fecha_hora)) FROM proyecto_entradas e
             WHERE e.proyecto_id = proyectos.id),
            fecha_inicio)
        WHERE estado = 'terminado'
        """
    )

    # Ya con los datos llenos, se quitan los defaults de la BD (el modelo los pone)
    with op.batch_alter_table("proyectos") as batch:
        batch.alter_column("destacado", existing_type=sa.Boolean(), server_default=None)
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.alter_column("tipo", existing_type=sa.String(length=20), server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.drop_column("tipo")
    with op.batch_alter_table("proyectos") as batch:
        batch.drop_column("creado_en")
        batch.drop_column("destacado")
        batch.drop_column("fecha_fin")

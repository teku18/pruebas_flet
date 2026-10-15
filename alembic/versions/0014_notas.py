"""Notas: notas de texto y listas con casillas

- nota_etiquetas: catálogo (vienen Súper, Ideas y Pendientes; se pueden cambiar)
- notas:          tipo (texto | lista), título, cuerpo, color, etiqueta,
                  fijada, archivada, creada y actualizada
- nota_items:     las casillas de una lista (texto, hecho, orden)
- Desarrollo: agrega el módulo "Notas" a tu roadmap (si aún no está), para
  poder reportarle pendientes.

Revisión: 0014
Anterior: 0013
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ETIQUETAS = [("Súper", "green"), ("Ideas", "amber"), ("Pendientes", "blue")]


def upgrade() -> None:
    etiquetas = op.create_table(
        "nota_etiquetas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=40), nullable=False, unique=True),
        sa.Column("color", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "notas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=True),
        sa.Column("cuerpo", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("etiqueta_id", sa.Integer(), sa.ForeignKey("nota_etiquetas.id"),
                  nullable=True),
        sa.Column("fijada", sa.Boolean(), nullable=False),
        sa.Column("archivada", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "nota_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nota_id", sa.Integer(), sa.ForeignKey("notas.id"), nullable=False),
        sa.Column("texto", sa.String(length=300), nullable=False),
        sa.Column("hecho", sa.Boolean(), nullable=False),
        sa.Column("secuencia", sa.Integer(), nullable=False),
    )
    op.create_index("ix_nota_items_nota", "nota_items", ["nota_id"])
    op.bulk_insert(etiquetas, [{"nombre": n, "color": c} for n, c in ETIQUETAS])

    # Roadmap de Desarrollo: el módulo nuevo (solo si no lo agregaste tú)
    conn = op.get_bind()
    ya = conn.execute(sa.text("SELECT COUNT(*) FROM dev_modulos WHERE nombre = 'Notas'")).scalar()
    if not ya:
        conn.execute(sa.text(
            "INSERT INTO dev_modulos (nombre, descripcion, prioridad, avance, creado_en) "
            "VALUES ('Notas', 'Notas rápidas y listas', 'media', 0, :ahora)"
        ), {"ahora": datetime.now()})


def downgrade() -> None:
    op.drop_index("ix_nota_items_nota", table_name="nota_items")
    op.drop_table("nota_items")
    op.drop_table("notas")
    op.drop_table("nota_etiquetas")
    # La fila "Notas" de Desarrollo se queda: puede tener pendientes tuyos.

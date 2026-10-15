"""Memorias: bitácora de momentos importantes

- memoria_etiquetas:    catálogo (Viaje, Familia, Pareja, Logro, Amigos, Trabajo)
- memorias:             fecha del suceso, título, relato, lugar, ánimo (emoji),
                        origen (texto | voz: listo para el dictado)
- memoria_etiqueta_rel: qué etiquetas tiene cada memoria (Many2many)
- Las fotos van en la tabla "adjuntos" (modelo "memoria"): no hay tabla nueva.
- Desarrollo: la descripción del módulo deja de decir "Pensamientos por voz
  (próximamente)" (solo si sigue con ese texto: si la cambiaste, se respeta).

Revisión: 0015
Anterior: 0014
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, Sequence[str], None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ETIQUETAS = [("Viaje", "teal"), ("Familia", "orange"), ("Pareja", "pink"),
             ("Logro", "amber"), ("Amigos", "purple"), ("Trabajo", "blue")]
DESCRIPCION_VIEJA = "Pensamientos por voz (próximamente)"
DESCRIPCION_NUEVA = "Momentos importantes: línea de tiempo y fotos"


def upgrade() -> None:
    etiquetas = op.create_table(
        "memoria_etiquetas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=40), nullable=False, unique=True),
        sa.Column("color", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "memorias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("relato", sa.Text(), nullable=True),
        sa.Column("lugar", sa.String(length=150), nullable=True),
        sa.Column("animo", sa.String(length=16), nullable=True),
        sa.Column("origen", sa.String(length=10), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_memorias_fecha", "memorias", ["fecha"])
    op.create_table(
        "memoria_etiqueta_rel",
        sa.Column("memoria_id", sa.Integer(), sa.ForeignKey("memorias.id"), primary_key=True),
        sa.Column("etiqueta_id", sa.Integer(), sa.ForeignKey("memoria_etiquetas.id"),
                  primary_key=True),
    )
    op.bulk_insert(etiquetas, [{"nombre": n, "color": c} for n, c in ETIQUETAS])
    op.get_bind().execute(sa.text(
        "UPDATE dev_modulos SET descripcion = :nueva "
        "WHERE nombre = 'Memorias' AND descripcion = :vieja"
    ), {"nueva": DESCRIPCION_NUEVA, "vieja": DESCRIPCION_VIEJA})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE dev_modulos SET descripcion = :vieja "
        "WHERE nombre = 'Memorias' AND descripcion = :nueva"
    ), {"nueva": DESCRIPCION_NUEVA, "vieja": DESCRIPCION_VIEJA})
    op.drop_table("memoria_etiqueta_rel")
    op.drop_index("ix_memorias_fecha", table_name="memorias")
    op.drop_table("memorias")
    op.drop_table("memoria_etiquetas")
    # Las fotos (filas de "adjuntos" con modelo "memoria") se quedan, por si
    # vuelves a subir de versión.

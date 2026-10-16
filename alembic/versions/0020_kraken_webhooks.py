"""Kraken Tools · Webhooks: receptores en tus servidores y lo recibido

- kt_webhooks: receptor (equipo SSH, puerto, clave secreta de la URL, qué
  responder, cuántos guardar, hasta qué id ya se trajo)
- kt_webhooks_recibidos: copia local de cada webhook (entra al respaldo)

Revisión: 0020
Anterior: 0019
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kt_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("equipo_id", sa.Integer(), sa.ForeignKey("kt_equipos.id"), nullable=True),
        sa.Column("puerto", sa.Integer(), nullable=False, server_default="9555"),
        sa.Column("clave", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("respuesta", sa.Text(), nullable=True),
        sa.Column("max_guardados", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("ultimo_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("instalado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kt_webhooks_recibidos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("receptor_id", sa.Integer(), sa.ForeignKey("kt_webhooks.id"), nullable=False),
        sa.Column("remoto_id", sa.Integer(), nullable=False),
        sa.Column("recibido_en", sa.DateTime(), nullable=False),
        sa.Column("metodo", sa.String(length=10), nullable=False),
        sa.Column("ruta", sa.Text(), nullable=False, server_default="/"),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("es_base64", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tamano", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("visto", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_kt_webhooks_recibidos_receptor", "kt_webhooks_recibidos",
                    ["receptor_id", "remoto_id"])


def downgrade() -> None:
    op.drop_index("ix_kt_webhooks_recibidos_receptor", table_name="kt_webhooks_recibidos")
    op.drop_table("kt_webhooks_recibidos")
    op.drop_table("kt_webhooks")

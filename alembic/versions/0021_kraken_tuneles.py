"""Kraken Tools: túneles públicos (ngrok / Cloudflare) y reenvío de webhooks

- kt_tuneles_publicos: URL https hacia un puerto de un equipo SSH
  ("Exponer puerto" o el túnel de un receptor de webhooks)
- kt_webhooks: + reenviar (lista de URLs a las que se manda cada webhook)
- kt_webhooks_recibidos: + reenvios (qué contestó cada destino)
- kt_ajustes: + ngrok_token

Revisión: 0021
Anterior: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kt_tuneles_publicos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("equipo_id", sa.Integer(), sa.ForeignKey("kt_equipos.id"), nullable=True),
        sa.Column("puerto", sa.Integer(), nullable=False, server_default="8069"),
        sa.Column("servicio", sa.String(length=12), nullable=False, server_default="ngrok"),
        sa.Column("dominio", sa.String(length=255), nullable=True),
        sa.Column("receptor_id", sa.Integer(), sa.ForeignKey("kt_webhooks.id"), nullable=True),
        sa.Column("clave", sa.String(length=40), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("kt_webhooks") as tabla:
        tabla.add_column(sa.Column("reenviar", sa.JSON(), nullable=True))
    with op.batch_alter_table("kt_webhooks_recibidos") as tabla:
        tabla.add_column(sa.Column("reenvios", sa.JSON(), nullable=True))
    with op.batch_alter_table("kt_ajustes") as tabla:
        tabla.add_column(sa.Column("ngrok_token", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("kt_ajustes") as tabla:
        tabla.drop_column("ngrok_token")
    with op.batch_alter_table("kt_webhooks_recibidos") as tabla:
        tabla.drop_column("reenvios")
    with op.batch_alter_table("kt_webhooks") as tabla:
        tabla.drop_column("reenviar")
    op.drop_table("kt_tuneles_publicos")

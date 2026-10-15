"""Kraken Tools: herramienta Red

- kt_equipos:        tus servidores, router, PC (IP o dominio, puertos, MAC)
- kt_historial_red:  cada prueba (ping, puertos, DNS, IP, certificado, whois,
                     Wake-on-LAN): resumen y detalle completo
- kt_ajustes:        + dns_servidor (1.1.1.1, Cloudflare) y
                     + red_historial_max (200), con valor para la fila que ya existe

Revisión: 0017
Anterior: 0016
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kt_equipos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("puertos", sa.String(length=200), nullable=True),
        sa.Column("mac", sa.String(length=17), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kt_historial_red",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("herramienta", sa.String(length=20), nullable=False),
        sa.Column("objetivo", sa.String(length=255), nullable=False),
        sa.Column("resumen", sa.String(length=255), nullable=False),
        sa.Column("exito", sa.Boolean(), nullable=False),
        sa.Column("detalle", sa.JSON(), nullable=True),
        sa.Column("tiempo_ms", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kt_historial_red_creado", "kt_historial_red", ["creado_en"])
    # server_default: la fila de ajustes que ya existe recibe el valor al agregar la columna
    with op.batch_alter_table("kt_ajustes") as tabla:
        tabla.add_column(sa.Column("dns_servidor", sa.String(length=100), nullable=False,
                                   server_default="1.1.1.1"))
        tabla.add_column(sa.Column("red_historial_max", sa.Integer(), nullable=False,
                                   server_default="200"))


def downgrade() -> None:
    with op.batch_alter_table("kt_ajustes") as tabla:
        tabla.drop_column("red_historial_max")
        tabla.drop_column("dns_servidor")
    op.drop_index("ix_kt_historial_red_creado", table_name="kt_historial_red")
    op.drop_table("kt_historial_red")
    op.drop_table("kt_equipos")

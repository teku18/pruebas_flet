"""Kraken Tools: SSH (monitor de servidores)

- kt_equipos: + ssh_usuario, ssh_puerto, ssh_clave (texto normal, como el
  resto de Kraken), ssh_huella (la del servidor, para detectar si cambia),
  ssh_servicios (qué vigilar) y ssh_log (qué archivo leer)
- kt_ssh_comandos: comandos guardados ("Reiniciar Odoo"…) con confirmación.
  Vienen 4 para todos los servidores (se pueden cambiar o borrar).

Revisión: 0018
Anterior: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMANDOS = [
    ("Reiniciar Odoo", "sudo systemctl restart odoo", 10),
    ("Reiniciar PostgreSQL", "sudo systemctl restart postgresql", 20),
    ("Reiniciar Nginx", "sudo systemctl restart nginx", 30),
    ("¿Qué ocupa el disco?", "sudo du -xh / --max-depth=2 2>/dev/null | sort -rh | head -15", 40),
]


def upgrade() -> None:
    with op.batch_alter_table("kt_equipos") as tabla:
        tabla.add_column(sa.Column("ssh_usuario", sa.String(length=80), nullable=True))
        tabla.add_column(sa.Column("ssh_puerto", sa.Integer(), nullable=True))
        tabla.add_column(sa.Column("ssh_clave", sa.Text(), nullable=True))
        tabla.add_column(sa.Column("ssh_huella", sa.String(length=120), nullable=True))
        tabla.add_column(sa.Column("ssh_servicios", sa.String(length=200), nullable=True))
        tabla.add_column(sa.Column("ssh_log", sa.String(length=300), nullable=True))
    comandos = op.create_table(
        "kt_ssh_comandos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("equipo_id", sa.Integer(), sa.ForeignKey("kt_equipos.id"), nullable=True),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("comando", sa.Text(), nullable=False),
        sa.Column("confirmar", sa.Boolean(), nullable=False),
        sa.Column("secuencia", sa.Integer(), nullable=False),
    )
    op.bulk_insert(comandos, [{"equipo_id": None, "nombre": n, "comando": c, "confirmar": True,
                               "secuencia": s} for n, c, s in COMANDOS])


def downgrade() -> None:
    op.drop_table("kt_ssh_comandos")
    with op.batch_alter_table("kt_equipos") as tabla:
        for col in ("ssh_log", "ssh_servicios", "ssh_huella", "ssh_clave", "ssh_puerto",
                    "ssh_usuario"):
            tabla.drop_column(col)

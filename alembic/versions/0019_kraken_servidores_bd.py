"""Kraken Tools: explorador de bases con servidores PostgreSQL y MySQL

- kt_sqlite_conexiones (el nombre se queda por compatibilidad):
  + tipo (sqlite | postgres | mysql; las que ya tienes quedan "sqlite")
  + host, puerto, base_datos, usuario, clave (texto normal, como todo Kraken)
  + ssh_equipo_id: llegar por un túnel SSH a través de un equipo de Red/SSH
  archivo deja de ser obligatorio (un servidor no tiene archivo)

Revisión: 0019
Anterior: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("kt_sqlite_conexiones") as tabla:
        tabla.add_column(sa.Column("tipo", sa.String(length=10), nullable=False,
                                   server_default="sqlite"))
        tabla.alter_column("archivo", existing_type=sa.String(length=300), nullable=True)
        tabla.add_column(sa.Column("host", sa.String(length=255), nullable=True))
        tabla.add_column(sa.Column("puerto", sa.Integer(), nullable=True))
        tabla.add_column(sa.Column("base_datos", sa.String(length=120), nullable=True))
        tabla.add_column(sa.Column("usuario", sa.String(length=120), nullable=True))
        tabla.add_column(sa.Column("clave", sa.Text(), nullable=True))
        tabla.add_column(sa.Column("ssh_equipo_id", sa.Integer(), nullable=True))
        tabla.create_foreign_key("fk_kt_sqlite_conexiones_ssh_equipo", "kt_equipos",
                                 ["ssh_equipo_id"], ["id"])


def downgrade() -> None:
    # Los servidores no caben en el esquema anterior (archivo obligatorio): se borran
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM kt_sqlite_consultas WHERE conexion_id IN "
                         "(SELECT id FROM kt_sqlite_conexiones WHERE tipo != 'sqlite')"))
    conn.execute(sa.text("DELETE FROM kt_sqlite_conexiones WHERE tipo != 'sqlite'"))
    with op.batch_alter_table("kt_sqlite_conexiones") as tabla:
        tabla.drop_constraint("fk_kt_sqlite_conexiones_ssh_equipo", type_="foreignkey")
        for col in ("ssh_equipo_id", "clave", "usuario", "base_datos", "puerto", "host"):
            tabla.drop_column(col)
        tabla.alter_column("archivo", existing_type=sa.String(length=300), nullable=False)
        tabla.drop_column("tipo")

"""Una sola tabla de adjuntos para toda la app (como ir.attachment de Odoo)

  antes:  dev_adjuntos (pendiente_id)      proyecto_adjuntos (entrada_id)
  ahora:  adjuntos (modelo, registro_id)
            modelo = "dev.pendiente"     <- lo que había en dev_adjuntos
            modelo = "proyecto.entrada"  <- lo que había en proyecto_adjuntos
            modelo = "agenda.tarea"      <- nuevo: adjuntos de tareas

Los ARCHIVOS no se mueven: la ruta (relativa a data/) se copia tal cual.
Pasos: crear la tabla nueva -> copiar las filas -> borrar las viejas.
Downgrade: regresa las filas a sus tablas (los adjuntos de tareas se pierden
en la BD, porque antes no existían; sus archivos se quedan en data/tareas/).

Revisión: 0012
Anterior: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (tabla vieja, columna del dueño, modelo en la tabla nueva, ¿tenía creado_en?)
VIEJAS = [
    ("dev_adjuntos", "pendiente_id", "dev.pendiente", True),
    ("proyecto_adjuntos", "entrada_id", "proyecto.entrada", False),
]

# Extensión -> mimetype (copia fija: la migración no depende del código de la app)
MIMES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    ".heic": "image/heic", ".pdf": "application/pdf",
}


def _mime(nombre: str) -> str | None:
    punto = nombre.rfind(".")
    return MIMES.get(nombre[punto:].lower()) if punto >= 0 else None


def upgrade() -> None:
    conn = op.get_bind()
    op.create_table(
        "adjuntos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("modelo", sa.String(length=60), nullable=False),
        sa.Column("registro_id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=True),
        sa.Column("mimetype", sa.String(length=100), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_adjuntos_modelo_registro", "adjuntos", ["modelo", "registro_id"])

    for tabla, columna, modelo, con_fecha in VIEJAS:
        fecha = "creado_en" if con_fecha else "NULL"
        filas = conn.execute(sa.text(
            f"SELECT {columna}, nombre, ruta, tamano, {fecha} FROM {tabla} ORDER BY id"
        )).fetchall()
        for registro_id, nombre, ruta, tamano, creado in filas:
            conn.execute(sa.text(
                "INSERT INTO adjuntos (modelo, registro_id, nombre, ruta, tamano, mimetype, "
                "creado_en) VALUES (:m, :r, :n, :ru, :t, :mi, :c)"
            ), {"m": modelo, "r": registro_id, "n": nombre, "ru": ruta, "t": tamano,
                "mi": _mime(nombre), "c": creado})
        op.drop_table(tabla)


def downgrade() -> None:
    conn = op.get_bind()
    op.create_table(
        "dev_adjuntos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pendiente_id", sa.Integer(), sa.ForeignKey("dev_pendientes.id"),
                  nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "proyecto_adjuntos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entrada_id", sa.Integer(), sa.ForeignKey("proyecto_entradas.id"),
                  nullable=False),
        sa.Column("nombre", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=True),
    )
    conn.execute(sa.text(
        "INSERT INTO dev_adjuntos (pendiente_id, nombre, ruta, tamano, creado_en) "
        "SELECT registro_id, nombre, ruta, tamano, creado_en FROM adjuntos "
        "WHERE modelo = 'dev.pendiente' ORDER BY id"
    ))
    conn.execute(sa.text(
        "INSERT INTO proyecto_adjuntos (entrada_id, nombre, ruta, tamano) "
        "SELECT registro_id, nombre, ruta, tamano FROM adjuntos "
        "WHERE modelo = 'proyecto.entrada' ORDER BY id"
    ))
    op.drop_index("ix_adjuntos_modelo_registro", table_name="adjuntos")
    op.drop_table("adjuntos")

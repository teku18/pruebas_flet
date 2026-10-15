"""Kraken Tools: cliente HTTP y explorador SQLite

- kt_ajustes:            1 fila (historial HTTP, tamaño de respuesta guardado,
                         tiempo de espera y el entorno elegido)
- kt_colecciones:        carpetas de peticiones
- kt_peticiones:         peticiones guardadas (params, headers, body, auth)
- kt_entornos:           variables {{así}}; viene "Globales"
- kt_historial_http:     cada envío (lo mandado y lo recibido)
- kt_sqlite_conexiones:  bases .db copiadas a data/kraken/bases/
                         (solo lectura y "respaldar" por base)
- kt_sqlite_consultas:   historial de SQL; con nombre = favorita
- Desarrollo: agrega "Kraken Tools" a tu roadmap (si aún no está).

Revisión: 0016
Anterior: 0015
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kt_colecciones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=80), nullable=False, unique=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kt_peticiones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("coleccion_id", sa.Integer(), sa.ForeignKey("kt_colecciones.id"),
                  nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("metodo", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("body_tipo", sa.String(length=10), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("form", sa.JSON(), nullable=True),
        sa.Column("auth_tipo", sa.String(length=10), nullable=False),
        sa.Column("auth_usuario", sa.Text(), nullable=True),
        sa.Column("auth_clave", sa.Text(), nullable=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kt_peticiones_coleccion", "kt_peticiones", ["coleccion_id"])
    entornos = op.create_table(
        "kt_entornos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=60), nullable=False, unique=True),
        sa.Column("es_global", sa.Boolean(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=True),
    )
    ajustes = op.create_table(
        "kt_ajustes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("historial_max", sa.Integer(), nullable=False),
        sa.Column("respuesta_max_kb", sa.Integer(), nullable=False),
        sa.Column("timeout_s", sa.Integer(), nullable=False),
        sa.Column("entorno_id", sa.Integer(), sa.ForeignKey("kt_entornos.id"), nullable=True),
    )
    op.create_table(
        "kt_historial_http",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("peticion_id", sa.Integer(), sa.ForeignKey("kt_peticiones.id"),
                  nullable=True),
        sa.Column("metodo", sa.String(length=10), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("req_headers", sa.JSON(), nullable=True),
        sa.Column("req_body", sa.Text(), nullable=True),
        sa.Column("borrador", sa.JSON(), nullable=True),
        sa.Column("status", sa.Integer(), nullable=True),
        sa.Column("motivo", sa.String(length=80), nullable=True),
        sa.Column("tiempo_ms", sa.Integer(), nullable=True),
        sa.Column("tamano", sa.Integer(), nullable=True),
        sa.Column("resp_headers", sa.JSON(), nullable=True),
        sa.Column("resp_body", sa.Text(), nullable=True),
        sa.Column("recortado", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kt_historial_http_creado", "kt_historial_http", ["creado_en"])
    op.create_table(
        "kt_sqlite_conexiones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=80), nullable=False),
        sa.Column("archivo", sa.String(length=300), nullable=False),
        sa.Column("origen", sa.Text(), nullable=True),
        sa.Column("solo_lectura", sa.Boolean(), nullable=False),
        sa.Column("respaldar", sa.Boolean(), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kt_sqlite_consultas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conexion_id", sa.Integer(), sa.ForeignKey("kt_sqlite_conexiones.id"),
                  nullable=True),
        sa.Column("nombre", sa.String(length=80), nullable=True),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("filas", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kt_sqlite_consultas_conexion", "kt_sqlite_consultas", ["conexion_id"])

    op.bulk_insert(entornos, [{"nombre": "Globales", "es_global": True, "variables": []}])
    op.bulk_insert(ajustes, [{"id": 1, "historial_max": 200, "respuesta_max_kb": 256,
                              "timeout_s": 30, "entorno_id": None}])

    # Roadmap de Desarrollo: el módulo nuevo (solo si no lo agregaste tú)
    conn = op.get_bind()
    ya = conn.execute(sa.text(
        "SELECT COUNT(*) FROM dev_modulos WHERE nombre = 'Kraken Tools'")).scalar()
    if not ya:
        conn.execute(sa.text(
            "INSERT INTO dev_modulos (nombre, descripcion, prioridad, avance, creado_en) "
            "VALUES ('Kraken Tools', 'Cliente HTTP, explorador SQLite, red, SSH y webhooks', "
            "'media', 0, :ahora)"
        ), {"ahora": datetime.now()})


def downgrade() -> None:
    op.drop_index("ix_kt_sqlite_consultas_conexion", table_name="kt_sqlite_consultas")
    op.drop_table("kt_sqlite_consultas")
    op.drop_table("kt_sqlite_conexiones")
    op.drop_index("ix_kt_historial_http_creado", table_name="kt_historial_http")
    op.drop_table("kt_historial_http")
    op.drop_table("kt_ajustes")
    op.drop_table("kt_entornos")
    op.drop_index("ix_kt_peticiones_coleccion", table_name="kt_peticiones")
    op.drop_table("kt_peticiones")
    op.drop_table("kt_colecciones")
    # La fila "Kraken Tools" de Desarrollo se queda: puede tener pendientes tuyos.
    # Las copias de bases en data/kraken/bases/ tampoco se borran.

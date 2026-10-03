"""Proyectos: etapas configurables (Kanban), tipos de entrada como catálogo y
tareas dentro del proyecto

Mismo patrón que 0004 (Selection -> catálogo, con movimiento de datos):

  1. Catálogos nuevos y sus datos de fábrica
       proyecto_etapas         Activo, En pausa, Terminado, Cancelado
       tarea_etapas            Por hacer, En proceso, Hecho
       proyecto_tipos_entrada  Avance, Hito, Problema, Cierre
       proyecto_etapas_tarea   (Many2many proyecto <-> etapas de tarea, vacía)
  2. proyectos.estado (texto)          -> proyectos.etapa_id
  3. proyecto_entradas.tipo (texto)    -> proyecto_entradas.tipo_id
  4. tareas: + etapa_id (las de proyecto: Hecho si estaban completadas,
     si no Por hacer) y fecha OPCIONAL (tareas de proyecto sin fecha)
  5. tarea_cumplimientos.fecha_programada OPCIONAL (por esas tareas sin fecha)

La migración NO importa models/: copia aquí las opciones como estaban.

Revisión: 0011
Anterior: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# estado viejo -> (nombre, clase, color)
ETAPAS_PROYECTO = {
    "activo": ("Activo", "en_curso", "blue"),
    "pausa": ("En pausa", "pausa", "amber"),
    "terminado": ("Terminado", "terminada", "green"),
    "cancelado": ("Cancelado", "cancelada", "grey"),
}
# (nombre, cerrada, color)
ETAPAS_TAREA = [
    ("Por hacer", False, "grey"),
    ("En proceso", False, "blue"),
    ("Hecho", True, "green"),
]
# tipo viejo -> (nombre, es_hito, icono, color)
TIPOS_ENTRADA = {
    "avance": ("Avance", False, "TRENDING_UP", "bluegrey"),
    "hito": ("Hito", True, "STAR", "amber"),
    "problema": ("Problema", False, "REPORT_PROBLEM", "orange"),
    "cierre": ("Cierre", False, "FLAG", "green"),
}


def _ids_por_texto(conn, tabla_vieja: str, columna: str, opciones: dict, insertar) -> dict:
    """Inserta las opciones conocidas + valores raros que haya en la BD. {texto: id}."""
    usados = [r[0] for r in conn.execute(sa.text(f"SELECT DISTINCT {columna} FROM {tabla_vieja}"))]
    ids = {}
    for n, clave in enumerate(list(opciones) + [u for u in usados if u not in opciones], start=1):
        ids[clave] = insertar(clave, n)
    return ids


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Catálogos -------------------------------------------------------
    op.create_table(
        "proyecto_etapas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=60), nullable=False, unique=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("clase", sa.String(length=20), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "tarea_etapas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=60), nullable=False, unique=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("cerrada", sa.Boolean(), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "proyecto_tipos_entrada",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=60), nullable=False, unique=True),
        sa.Column("secuencia", sa.Integer(), nullable=False),
        sa.Column("es_hito", sa.Boolean(), nullable=False),
        sa.Column("icono", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "proyecto_etapas_tarea",
        sa.Column("proyecto_id", sa.Integer(), sa.ForeignKey("proyectos.id"), primary_key=True),
        sa.Column("etapa_id", sa.Integer(), sa.ForeignKey("tarea_etapas.id"), primary_key=True),
    )

    def etapa_proyecto(clave, n):
        nombre, clase, color = ETAPAS_PROYECTO.get(clave, (clave.capitalize(), "en_curso", "blue"))
        return conn.execute(sa.text(
            "INSERT INTO proyecto_etapas (nombre, secuencia, clase, color) VALUES (:a, :b, :c, :d)"
        ), {"a": nombre, "b": n, "c": clase, "d": color}).lastrowid

    def tipo_entrada(clave, n):
        nombre, hito, icono, color = TIPOS_ENTRADA.get(
            clave, (clave.capitalize(), False, "LABEL", "bluegrey"))
        return conn.execute(sa.text(
            "INSERT INTO proyecto_tipos_entrada (nombre, secuencia, es_hito, icono, color) "
            "VALUES (:a, :b, :c, :d, :e)"
        ), {"a": nombre, "b": n, "c": hito, "d": icono, "e": color}).lastrowid

    ids_etapa = _ids_por_texto(conn, "proyectos", "estado", ETAPAS_PROYECTO, etapa_proyecto)
    ids_tipo = _ids_por_texto(conn, "proyecto_entradas", "tipo", TIPOS_ENTRADA, tipo_entrada)
    ids_tarea = {}
    for n, (nombre, cerrada, color) in enumerate(ETAPAS_TAREA, start=1):
        ids_tarea[nombre] = conn.execute(sa.text(
            "INSERT INTO tarea_etapas (nombre, secuencia, cerrada, color) VALUES (:a, :b, :c, :d)"
        ), {"a": nombre, "b": n, "c": cerrada, "d": color}).lastrowid

    # 2. proyectos.estado -> etapa_id ---------------------------------------
    with op.batch_alter_table("proyectos") as batch:
        batch.add_column(sa.Column("etapa_id", sa.Integer(), nullable=True))
    for clave, nuevo_id in ids_etapa.items():
        conn.execute(sa.text("UPDATE proyectos SET etapa_id = :id WHERE estado = :c"),
                     {"id": nuevo_id, "c": clave})
    with op.batch_alter_table("proyectos") as batch:
        batch.alter_column("etapa_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_proyectos_etapa", "proyecto_etapas", ["etapa_id"], ["id"])
        batch.drop_column("estado")

    # 3. proyecto_entradas.tipo -> tipo_id ----------------------------------
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.add_column(sa.Column("tipo_id", sa.Integer(), nullable=True))
    for clave, nuevo_id in ids_tipo.items():
        conn.execute(sa.text("UPDATE proyecto_entradas SET tipo_id = :id WHERE tipo = :c"),
                     {"id": nuevo_id, "c": clave})
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.alter_column("tipo_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_entradas_tipo", "proyecto_tipos_entrada",
                                 ["tipo_id"], ["id"])
        batch.drop_column("tipo")

    # 4. tareas: etapa_id + fecha opcional -----------------------------------
    with op.batch_alter_table("tareas") as batch:
        batch.add_column(sa.Column("etapa_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_tareas_etapa", "tarea_etapas", ["etapa_id"], ["id"])
        batch.alter_column("fecha", existing_type=sa.Date(), nullable=True)
    conn.execute(sa.text(
        "UPDATE tareas SET etapa_id = :hecho WHERE proyecto_id IS NOT NULL AND completada = 1"
    ), {"hecho": ids_tarea["Hecho"]})
    conn.execute(sa.text(
        "UPDATE tareas SET etapa_id = :por WHERE proyecto_id IS NOT NULL AND completada = 0"
    ), {"por": ids_tarea["Por hacer"]})

    # 5. Cumplimientos de tareas sin fecha -----------------------------------
    with op.batch_alter_table("tarea_cumplimientos") as batch:
        batch.alter_column("fecha_programada", existing_type=sa.Date(), nullable=True)


def downgrade() -> None:
    """Regresa a texto. Las tareas sin fecha toman la fecha de hoy."""
    conn = op.get_bind()
    inverso_e = {v[0]: k for k, v in ETAPAS_PROYECTO.items()}
    clase_a_estado = {"en_curso": "activo", "pausa": "pausa",
                      "terminada": "terminado", "cancelada": "cancelado"}
    inverso_t = {v[0]: k for k, v in TIPOS_ENTRADA.items()}

    conn.execute(sa.text(
        "UPDATE tarea_cumplimientos SET fecha_programada = DATE(hecho_en) "
        "WHERE fecha_programada IS NULL"))
    with op.batch_alter_table("tarea_cumplimientos") as batch:
        batch.alter_column("fecha_programada", existing_type=sa.Date(), nullable=False)

    conn.execute(sa.text("UPDATE tareas SET fecha = DATE('now') WHERE fecha IS NULL"))
    with op.batch_alter_table("tareas") as batch:
        batch.alter_column("fecha", existing_type=sa.Date(), nullable=False)
        batch.drop_constraint("fk_tareas_etapa", type_="foreignkey")
        batch.drop_column("etapa_id")

    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.add_column(sa.Column("tipo", sa.String(length=20), nullable=True))
    for id_, nombre, hito in conn.execute(
            sa.text("SELECT id, nombre, es_hito FROM proyecto_tipos_entrada")):
        clave = inverso_t.get(nombre, "hito" if hito else "avance")
        conn.execute(sa.text("UPDATE proyecto_entradas SET tipo = :c WHERE tipo_id = :id"),
                     {"c": clave, "id": id_})
    with op.batch_alter_table("proyecto_entradas") as batch:
        batch.alter_column("tipo", existing_type=sa.String(length=20), nullable=False)
        batch.drop_constraint("fk_entradas_tipo", type_="foreignkey")
        batch.drop_column("tipo_id")

    with op.batch_alter_table("proyectos") as batch:
        batch.add_column(sa.Column("estado", sa.String(length=20), nullable=True))
    for id_, nombre, clase in conn.execute(
            sa.text("SELECT id, nombre, clase FROM proyecto_etapas")):
        clave = inverso_e.get(nombre, clase_a_estado.get(clase, "activo"))
        conn.execute(sa.text("UPDATE proyectos SET estado = :c WHERE etapa_id = :id"),
                     {"c": clave, "id": id_})
    with op.batch_alter_table("proyectos") as batch:
        batch.alter_column("estado", existing_type=sa.String(length=20), nullable=False)
        batch.drop_constraint("fk_proyectos_etapa", type_="foreignkey")
        batch.drop_column("etapa_id")

    op.drop_table("proyecto_etapas_tarea")
    op.drop_table("proyecto_tipos_entrada")
    op.drop_table("tarea_etapas")
    op.drop_table("proyecto_etapas")

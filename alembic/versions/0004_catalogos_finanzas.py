"""Plataforma e Inversión como catálogos + traspasos ligados

Primera migración con MOVIMIENTO DE DATOS, no solo de estructura:
los movimientos guardaban texto ("gbm") y ahora deben apuntar a un id.

  1. Crear tablas plataformas e inversiones       (estructura: autogenerate)
  2. Llenarlas con las opciones que había          (datos: a mano)
  3. Agregar plataforma_id, inversion_id, grupo    (estructura: autogenerate)
  4. Copiar "gbm" -> id de "GBM+"                  (datos: a mano)
  5. Hacerlas obligatorias, quitar texto viejo     (estructura: autogenerate)

Nota: la migración NO importa nada de models/. Copia aquí las opciones
tal como estaban, porque el código de models/ cambiará con el tiempo y
esta receta debe seguir funcionando igual dentro de un año.

Revisión: 0004
Anterior: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Foto de los Selection de antes: {clave guardada: nombre visible}
PLATAFORMAS_ANTES = {
    "gbm": "GBM+",
    "cetes_directo": "Cetes Directo",
    "nu": "Nu",
    "bitso": "Bitso",
    "yotepresto": "YoTepresto",
    "finsus": "Finsus",
    "mercado_pago": "Mercado Pago",
    "uala": "Uala",
    "stori": "Stori",
}
INVERSIONES_ANTES = {
    "reto_ahorro": "Reto Ahorro",
    "casa": "Casa",
}


def _catalog_table(nombre: str) -> None:
    op.create_table(
        nombre,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nombre", sa.String(length=100), nullable=False, unique=True),
        sa.Column("activo", sa.Boolean(), nullable=False),
    )


def _fill_catalog(tabla: str, opciones: dict, columna_texto: str) -> dict:
    """Inserta las opciones conocidas + cualquier valor raro que haya en la BD.
    Regresa {clave de texto: id nuevo}."""
    conn = op.get_bind()
    usados = [r[0] for r in conn.execute(
        sa.text(f"SELECT DISTINCT {columna_texto} FROM movimientos")
    )]
    ids = {}
    for clave in list(opciones) + [u for u in usados if u not in opciones]:
        nombre = opciones.get(clave, clave)  # un valor desconocido usa su clave como nombre
        ids[clave] = conn.execute(
            sa.text(f"INSERT INTO {tabla} (nombre, activo) VALUES (:n, 1)"), {"n": nombre}
        ).lastrowid
    return ids


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Catálogos
    _catalog_table("plataformas")
    _catalog_table("inversiones")

    # 2. Llenarlos
    ids_plataforma = _fill_catalog("plataformas", PLATAFORMAS_ANTES, "plataforma")
    ids_inversion = _fill_catalog("inversiones", INVERSIONES_ANTES, "inversion")

    # 3. Columnas nuevas (todavía opcionales, porque aún están vacías)
    with op.batch_alter_table("movimientos") as batch:
        batch.add_column(sa.Column("plataforma_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("inversion_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("traspaso_grupo", sa.String(length=32), nullable=True))

    # 4. Copiar texto -> id
    for clave, nuevo_id in ids_plataforma.items():
        conn.execute(sa.text("UPDATE movimientos SET plataforma_id = :id WHERE plataforma = :c"),
                     {"id": nuevo_id, "c": clave})
    for clave, nuevo_id in ids_inversion.items():
        conn.execute(sa.text("UPDATE movimientos SET inversion_id = :id WHERE inversion = :c"),
                     {"id": nuevo_id, "c": clave})

    # 5. Obligatorias + llaves foráneas + adiós columnas de texto
    with op.batch_alter_table("movimientos") as batch:
        batch.alter_column("plataforma_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("inversion_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key("fk_movimientos_plataforma", "plataformas",
                                 ["plataforma_id"], ["id"])
        batch.create_foreign_key("fk_movimientos_inversion", "inversiones",
                                 ["inversion_id"], ["id"])
        batch.drop_column("plataforma")
        batch.drop_column("inversion")


def downgrade() -> None:
    """Regresa a texto: guarda el nombre del catálogo en las columnas viejas."""
    conn = op.get_bind()
    with op.batch_alter_table("movimientos") as batch:
        batch.add_column(sa.Column("plataforma", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("inversion", sa.String(length=50), nullable=True))

    inverso_p = {v: k for k, v in PLATAFORMAS_ANTES.items()}
    inverso_i = {v: k for k, v in INVERSIONES_ANTES.items()}
    for id_, nombre in conn.execute(sa.text("SELECT id, nombre FROM plataformas")):
        conn.execute(sa.text("UPDATE movimientos SET plataforma = :c WHERE plataforma_id = :id"),
                     {"c": inverso_p.get(nombre, nombre), "id": id_})
    for id_, nombre in conn.execute(sa.text("SELECT id, nombre FROM inversiones")):
        conn.execute(sa.text("UPDATE movimientos SET inversion = :c WHERE inversion_id = :id"),
                     {"c": inverso_i.get(nombre, nombre), "id": id_})

    with op.batch_alter_table("movimientos") as batch:
        batch.alter_column("plataforma", existing_type=sa.String(length=50), nullable=False)
        batch.alter_column("inversion", existing_type=sa.String(length=50), nullable=False)
        batch.drop_constraint("fk_movimientos_plataforma", type_="foreignkey")
        batch.drop_constraint("fk_movimientos_inversion", type_="foreignkey")
        batch.drop_column("plataforma_id")
        batch.drop_column("inversion_id")
        batch.drop_column("traspaso_grupo")

    op.drop_table("inversiones")
    op.drop_table("plataformas")

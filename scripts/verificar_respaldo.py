"""
Prueba de ida y vuelta del respaldo: ¿entra TODO al zip y regresa igual?

    python scripts/verificar_respaldo.py

Trabaja en una carpeta temporal (variable CK_DATA_ROOT): NUNCA toca tu
ControlKraken.db ni tu data/.

Qué hace:
  1. Crea una BD nueva al día (todas las migraciones).
  2. Mete UN registro en CADA tabla que conocen los modelos (las de hoy y las
     que agregues mañana: las lee de Base.metadata, no de una lista fija).
  3. Pone un archivo en data/ por cada carpeta que usan los módulos.
  4. Respalda -> borra la BD y data/ (como un celular nuevo) -> restaura.
  5. Compara tabla por tabla (filas) y archivo por archivo (contenido).

Si un módulo nuevo quedara fuera del respaldo, aquí sale ✗ y termina con error.
"""
import hashlib
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

TMP = Path(tempfile.mkdtemp(prefix="ck_respaldo_"))
os.environ["CK_DATA_ROOT"] = str(TMP)  # antes de importar core: todo vive en TMP

import sqlalchemy as sa  # noqa: E402

from core import backup, database  # noqa: E402
from core.storage import DATA_DIR  # noqa: E402

# Carpetas de data/ que usa la app (si agregas una, súmala aquí)
CARPETAS_DATA = ["desarrollo/1", "adjuntos/1/1", "tareas/1", "capturas", "memorias/1/mini"]


def dummy_value(columna: sa.Column, tabla: str):  # propio
    """Un valor válido cualquiera según el tipo de la columna."""
    tipo = columna.type
    if isinstance(tipo, sa.Boolean):
        return False
    if isinstance(tipo, sa.DateTime):
        return datetime(2026, 1, 2, 3, 4, 5)
    if isinstance(tipo, sa.Date):
        return date(2026, 1, 2)
    if isinstance(tipo, sa.Time):
        return time(9, 30)
    if isinstance(tipo, (sa.Float, sa.Numeric)):
        return 1.5
    if isinstance(tipo, sa.Integer):
        return 1
    # Texto: único por tabla y columna (algunas tienen unique=True)
    largo = getattr(tipo, "length", None) or 40
    return f"prueba_{tabla}_{columna.name}"[:largo]


def fill_every_table() -> dict[str, int]:  # propio
    """Un registro en cada tabla (en orden de dependencias). Regresa {tabla: filas}."""
    database.import_models()
    with database.engine.begin() as conn:
        for tabla in database.Base.metadata.sorted_tables:
            valores = {}
            for col in tabla.columns:
                if col.primary_key and isinstance(col.type, sa.Integer) and not col.foreign_keys:
                    continue  # id autoincremental
                valores[col.name] = dummy_value(col, tabla.name)
            conn.execute(tabla.insert().values(**valores))
    return count_rows()


def count_rows() -> dict[str, int]:  # propio
    with database.engine.connect() as conn:
        return {
            t.name: conn.execute(sa.select(sa.func.count()).select_from(t)).scalar()
            for t in database.Base.metadata.sorted_tables
        }


def put_files() -> dict[str, str]:  # propio
    for carpeta in CARPETAS_DATA:
        destino = DATA_DIR / carpeta
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "prueba.bin").write_bytes(os.urandom(2048))
    return file_hashes()


def file_hashes() -> dict[str, str]:  # propio
    if not DATA_DIR.exists():
        return {}
    return {
        p.relative_to(DATA_DIR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in DATA_DIR.rglob("*") if p.is_file()
    }


def main() -> int:  # propio
    print(f"Carpeta de prueba: {TMP}")
    database.init_db()
    antes_filas = fill_every_table()
    antes_archivos = put_files()

    zip_path = backup.create_backup(TMP / "zips", "prueba")
    print(f"Respaldo: {zip_path.name} ({zip_path.stat().st_size / 1024:.0f} KB)")

    # "Celular nuevo": sin BD y sin data/
    database.engine.dispose()
    database.DB_PATH.unlink()
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    database.init_db()  # BD vacía, como al instalar
    backup.restore_backup(zip_path)

    despues_filas = count_rows()
    despues_archivos = file_hashes()

    fallas = 0
    print("\nTablas:")
    for tabla, n in sorted(antes_filas.items()):
        ok = despues_filas.get(tabla) == n
        fallas += not ok
        print(f"  {'✓' if ok else '✗'} {tabla:<28} {n} -> {despues_filas.get(tabla)}")
    print("\nArchivos de data/:")
    for ruta, h in sorted(antes_archivos.items()):
        ok = despues_archivos.get(ruta) == h
        fallas += not ok
        print(f"  {'✓' if ok else '✗'} {ruta}")

    shutil.rmtree(TMP, ignore_errors=True)
    if fallas:
        print(f"\n✗ {fallas} diferencia(s): el respaldo NO está completo.")
        return 1
    print(f"\n✓ Respaldo completo: {len(antes_filas)} tablas y {len(antes_archivos)} archivos "
          "regresaron iguales.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

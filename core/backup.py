"""
Respaldo y restauración de ControlKraken.

Un respaldo es UN zip:
  ControlKraken_2026-09-27_185012.zip
    ├─ movimientos.db   copia segura de la BD (API de respaldo de SQLite,
    │                   funciona aunque la app esté abierta)
    ├─ data/...         adjuntos de Proyectos (lo que no vive en la BD)
    └─ manifest.json    versión de la app, migración, fecha, equipo y motivo

Dónde se guardan:
  - Carpeta elegida en Configuración (p. ej. ~/Respaldos/ControlKraken, que
    rclone sube a Google Drive). Automático: 2 min después de tu último cambio.
  - respaldos/ junto a main.py: copias locales automáticas ANTES de migrar
    (al actualizar la app) y ANTES de restaurar. Está en .gitignore.

Se conservan los últimos 5 + el más reciente de cada mes (12 meses).
Restaurar: valida el zip, guarda tu BD actual en respaldos/, reemplaza la BD y
data/, y aplica las migraciones si el respaldo es de una versión anterior.
"""
import json
import shutil
import socket
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from alembic.script import ScriptDirectory

from core import APP_VERSION
from core.database import DB_PATH, ROOT_DIR, alembic_config, engine
from core.storage import DATA_DIR

PREFIJO = "ControlKraken_"
LOCAL_DIR = ROOT_DIR / "respaldos"     # copias de seguridad automáticas locales
MANIFEST = "manifest.json"
CONSERVAR_ULTIMOS = 5
CONSERVAR_MESES = 12


@dataclass
class BackupInfo:
    ruta: Path
    fecha: datetime
    tamaño: int


# ============================================================================
# Utilidades de versión
# ============================================================================
def db_revision(ruta: Path = DB_PATH) -> str | None:  # propio
    """Migración en la que está una BD (tabla alembic_version), o None."""
    if not ruta.exists():
        return None
    con = sqlite3.connect(ruta)
    try:
        fila = con.execute("select version_num from alembic_version").fetchone()
        return fila[0] if fila else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def head_revision() -> str:  # propio
    """La migración más nueva que conoce esta versión de la app."""
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def known_revision(revision: str) -> bool:  # propio
    try:
        return ScriptDirectory.from_config(alembic_config()).get_revision(revision) is not None
    except Exception:  # noqa: BLE001  (revisión desconocida)
        return False


def changed_since(timestamp: float) -> bool:  # propio
    """¿La BD se modificó después de ese momento? (cada guardado cambia el archivo)."""
    return DB_PATH.exists() and DB_PATH.stat().st_mtime > timestamp


def last_change() -> float:  # propio
    return DB_PATH.stat().st_mtime if DB_PATH.exists() else 0.0


# ============================================================================
# Crear
# ============================================================================
def create_backup(destino: Path, motivo: str = "manual") -> Path:  # propio
    """Crea el zip en `destino` y regresa su ruta."""
    destino = Path(destino).expanduser()
    destino.mkdir(parents=True, exist_ok=True)
    ahora = datetime.now()
    final = destino / f"{PREFIJO}{ahora:%Y-%m-%d_%H%M%S}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Copia consistente de la BD aunque esté en uso
        copia = Path(tmp) / DB_PATH.name
        origen, dst = sqlite3.connect(DB_PATH), sqlite3.connect(copia)
        try:
            origen.backup(dst)
        finally:
            dst.close()
            origen.close()

        manifest = {
            "app": "ControlKraken",
            "version_app": APP_VERSION,
            "migracion": db_revision(copia),
            "creado": ahora.isoformat(timespec="seconds"),
            "equipo": socket.gethostname(),
            "motivo": motivo,
        }

        # 2. Se escribe con otro nombre y al final se renombra: así rclone
        #    nunca sube un zip a medias
        parcial = destino / (final.name + ".part")
        with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia, DB_PATH.name)
            z.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            if DATA_DIR.exists():
                for archivo in DATA_DIR.rglob("*"):
                    if archivo.is_file():
                        z.write(archivo, Path("data") / archivo.relative_to(DATA_DIR))
        parcial.replace(final)
    return final


def list_backups(carpeta: Path) -> list[BackupInfo]:  # propio
    """Respaldos de la carpeta, del más nuevo al más viejo."""
    carpeta = Path(carpeta).expanduser()
    if not carpeta.is_dir():
        return []
    resultado = []
    for ruta in carpeta.glob(f"{PREFIJO}*.zip"):
        try:
            fecha = datetime.strptime(ruta.stem[len(PREFIJO):], "%Y-%m-%d_%H%M%S")
        except ValueError:
            continue  # zip con otro nombre: no es nuestro, no se toca
        resultado.append(BackupInfo(ruta, fecha, ruta.stat().st_size))
    return sorted(resultado, key=lambda b: b.fecha, reverse=True)


def prune(carpeta: Path, ultimos: int = CONSERVAR_ULTIMOS,  # propio
          meses: int = CONSERVAR_MESES) -> int:
    """Borra respaldos viejos: quedan los últimos N + el más nuevo de cada mes."""
    respaldos = list_backups(carpeta)
    conservar = {b.ruta for b in respaldos[:ultimos]}
    vistos = set()
    for b in respaldos:  # del más nuevo al más viejo: el primero de cada mes es el último
        mes = (b.fecha.year, b.fecha.month)
        if mes not in vistos and len(vistos) < meses:
            vistos.add(mes)
            conservar.add(b.ruta)
    borrados = 0
    for b in respaldos:
        if b.ruta not in conservar:
            b.ruta.unlink(missing_ok=True)
            borrados += 1
    return borrados


def backup_before_migrate() -> Path | None:  # propio
    """
    Lo llama init_db: si la BD existe y hay migraciones pendientes (acabas de
    actualizar la app), guarda una copia local antes de tocarla.
    """
    actual = db_revision()
    if actual is None or actual == head_revision():
        return None
    ruta = create_backup(LOCAL_DIR, f"antes de migrar {actual} -> {head_revision()}")
    prune(LOCAL_DIR, ultimos=5, meses=0)
    return ruta


# ============================================================================
# Restaurar
# ============================================================================
def read_manifest(zip_path: Path) -> dict:  # propio
    """Valida el zip y regresa su manifest. Lanza ValueError con el motivo."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            nombres = set(z.namelist())
            if DB_PATH.name not in nombres:
                raise ValueError("el archivo no contiene una base de datos de ControlKraken")
            manifest = json.loads(z.read(MANIFEST)) if MANIFEST in nombres else {}
    except zipfile.BadZipFile as ex:
        raise ValueError("no es un zip válido") from ex
    revision = manifest.get("migracion")
    if revision and not known_revision(revision):
        raise ValueError(
            f"el respaldo es de una versión más nueva de la app "
            f"(v{manifest.get('version_app', '?')}). Actualiza la app primero."
        )
    return manifest


def restore_backup(zip_path: Path) -> dict:  # propio
    """
    Reemplaza la BD y data/ con los del respaldo. Antes guarda lo actual en
    respaldos/ (por si te equivocas de archivo). Regresa el manifest.
    """
    from core import database

    manifest = read_manifest(zip_path)
    if DB_PATH.exists() and not database.BD_NUEVA:  # equipo nuevo: no hay nada que guardar
        create_backup(LOCAL_DIR, "antes de restaurar")
        prune(LOCAL_DIR, ultimos=5, meses=0)

    engine.dispose()  # suelta las conexiones abiertas a la BD actual
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp)
        # BD: se copia junto y se renombra encima (reemplazo en un solo paso)
        nueva = DB_PATH.with_suffix(".restaurando")
        shutil.copy2(Path(tmp) / DB_PATH.name, nueva)
        nueva.replace(DB_PATH)
        # Adjuntos
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        if (Path(tmp) / "data").exists():
            shutil.copytree(Path(tmp) / "data", DATA_DIR)

    database.init_db()  # si el respaldo es de una versión anterior, lo pone al día
    return manifest

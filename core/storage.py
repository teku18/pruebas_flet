"""
Archivos de la app que NO van dentro de la BD (adjuntos, y a futuro audios).
Se guardan en data/ y la BD solo guarda la ruta relativa, como el filestore
de Odoo. data/ está en .gitignore: respáldalo junto con la .db.
"""
import shutil
import uuid
from pathlib import Path

from core.database import ROOT_DIR

DATA_DIR = ROOT_DIR / "data"


def save_file(origen: Path | None, datos: bytes | None, destino_dir: Path, nombre: str) -> Path:  # propio
    """
    Copia un archivo elegido por el usuario a destino_dir y regresa la ruta
    RELATIVA a DATA_DIR (lo que se guarda en la BD).
    Se antepone un id corto para que dos archivos con el mismo nombre no choquen.
    """
    destino_dir.mkdir(parents=True, exist_ok=True)
    destino = destino_dir / f"{uuid.uuid4().hex[:8]}_{nombre}"
    if origen is not None:
        shutil.copy2(origen, destino)
    elif datos is not None:
        destino.write_bytes(datos)
    else:
        raise ValueError("El archivo no trae ruta ni contenido")
    return destino.relative_to(DATA_DIR)


def absolute_path(ruta_relativa: str) -> Path:  # propio
    return DATA_DIR / ruta_relativa


def delete_file(ruta_relativa: str) -> None:  # propio
    (DATA_DIR / ruta_relativa).unlink(missing_ok=True)


def delete_folder(carpeta: Path) -> None:  # propio
    shutil.rmtree(carpeta, ignore_errors=True)


def human_size(bytes_: int | None) -> str:  # propio
    """1536 -> '1.5 KB'"""
    tam = float(bytes_ or 0)
    for unidad in ("B", "KB", "MB", "GB"):
        if tam < 1024 or unidad == "GB":
            return f"{tam:.0f} {unidad}" if unidad == "B" else f"{tam:.1f} {unidad}"
        tam /= 1024
    return ""

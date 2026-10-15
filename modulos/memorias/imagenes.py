"""
Fotos de las memorias: se COPIAN a la carpeta de la app (no se guarda una
referencia a la galería del celular: si borras la foto allá, aquí sigue).

Al guardar cada foto (Pillow):
  1. Se gira según su EXIF (las fotos del celular vienen "acostadas" y la
     orientación viene aparte, en una etiqueta).
  2. Si su lado mayor pasa de LADO_MAXIMO, se reduce. 3072 px es más que la
     pantalla de cualquier celular (el tuyo: 1220 px de ancho), así que en la
     app y al hacer zoom se ve igual; el archivo pesa ~5-8 veces menos.
  3. Se guarda como JPEG calidad 92 (a simple vista no se distingue del
     original). PNG chicos (capturas) se quedan como PNG.
  4. Se hace una MINIATURA de 480 px para la galería y la línea de tiempo
     (cargar 50 fotos grandes en una cuadrícula sería lentísimo).

Si Pillow no puede abrir el archivo (p. ej. HEIC de iPhone), se guarda tal cual
y sin miniatura: la memoria lo muestra con un ícono.

Fecha de la foto: se lee del EXIF (DateTimeOriginal) para proponerla como
fecha de la memoria.
"""
import mimetypes
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from core.storage import DATA_DIR

LADO_MAXIMO = 3072
CALIDAD = 92
LADO_MINIATURA = 480
CALIDAD_MINIATURA = 80
EXIF_FECHA_ORIGINAL = 36867   # DateTimeOriginal
EXIF_FECHA = 306              # DateTime (por si no trae la original)
EXIF_IFD = 0x8769             # sub-bloque donde vive DateTimeOriginal


def photo_date(datos: bytes) -> date | None:  # propio
    """Fecha en que se tomó la foto (EXIF), o None."""
    try:
        with Image.open(BytesIO(datos)) as img:
            exif = img.getexif()
            texto = exif.get_ifd(EXIF_IFD).get(EXIF_FECHA_ORIGINAL) or exif.get(EXIF_FECHA)
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    try:
        return datetime.strptime(str(texto).strip()[:19], "%Y:%m:%d %H:%M:%S").date()
    except (TypeError, ValueError):
        return None


def thumbnail_path(ruta: str) -> Path:  # propio
    """data/memorias/7/ab12_foto.jpg -> data/memorias/7/mini/ab12_foto.jpg"""
    p = DATA_DIR / ruta
    return p.parent / "mini" / (p.stem + ".jpg")


def save_photo(datos: bytes, nombre: str, carpeta: Path) -> tuple[str, int, str]:  # propio
    """
    Guarda la foto (girada y reducida) y su miniatura en `carpeta`.
    Regresa (ruta relativa a data/, tamaño en bytes, mimetype).
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    base = f"{uuid.uuid4().hex[:8]}_{Path(nombre).stem}"[:120]
    try:
        img = Image.open(BytesIO(datos))
        img = ImageOps.exif_transpose(img)  # 1. girar según el EXIF
    except (UnidentifiedImageError, OSError, ValueError):
        # No es una imagen que Pillow entienda: se guarda tal cual
        destino = carpeta / f"{base}{Path(nombre).suffix.lower()}"
        destino.write_bytes(datos)
        mime = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
        return destino.relative_to(DATA_DIR).as_posix(), len(datos), mime

    es_png_chico = (nombre.lower().endswith(".png") and max(img.size) <= LADO_MAXIMO)
    if max(img.size) > LADO_MAXIMO:  # 2. reducir solo si es más grande
        img.thumbnail((LADO_MAXIMO, LADO_MAXIMO), Image.Resampling.LANCZOS)
    if es_png_chico:  # 3. capturas de pantalla: PNG (texto nítido)
        destino, mime = carpeta / f"{base}.png", "image/png"
        img.save(destino, "PNG", optimize=True)
    else:
        destino, mime = carpeta / f"{base}.jpg", "image/jpeg"
        img.convert("RGB").save(destino, "JPEG", quality=CALIDAD, optimize=True,
                                progressive=True)

    mini = carpeta / "mini" / f"{base}.jpg"  # 4. miniatura
    mini.parent.mkdir(exist_ok=True)
    chica = img.convert("RGB")
    chica.thumbnail((LADO_MINIATURA, LADO_MINIATURA), Image.Resampling.LANCZOS)
    chica.save(mini, "JPEG", quality=CALIDAD_MINIATURA, optimize=True)
    return destino.relative_to(DATA_DIR).as_posix(), destino.stat().st_size, mime


def read_thumbnail(ruta: str) -> bytes | None:  # propio
    """Bytes de la miniatura (o None si no tiene, p. ej. HEIC)."""
    p = thumbnail_path(ruta)
    return p.read_bytes() if p.exists() else None


def read_photo(ruta: str) -> bytes | None:  # propio
    p = DATA_DIR / ruta
    return p.read_bytes() if p.exists() else None


def delete_photo_files(ruta: str) -> None:  # propio
    """La foto y su miniatura (la fila de "adjuntos" la borra Adjunto.delete)."""
    thumbnail_path(ruta).unlink(missing_ok=True)

"""
Bandeja de capturas: lo que tomas con la herramienta flotante (📷 / 🎥) antes
de adjuntarlo a un pendiente.

  data/capturas/captura_agenda_2026-09-29_203512.png     <- captura (tomada en Agenda)
  data/capturas/grabacion_finanzas_2026-09-29_2036.gif   <- grabación (GIF animado)

El nombre guarda en qué módulo se tomó: al reportarla, el pendiente nuevo ya
trae ese módulo elegido.

Al adjuntar una captura a un pendiente se COPIA a la carpeta del pendiente y
se quita de la bandeja (así la bandeja solo tiene lo que falta reportar).

La grabación son varias capturas seguidas (page.take_screenshot) armadas como
GIF animado con Pillow: funciona igual en la compu y en el celular, pero solo
graba la app (no otras aplicaciones) y a ~2-3 cuadros por segundo.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from core.storage import DATA_DIR

CAPTURAS_DIR = DATA_DIR / "capturas"
EXT_CAPTURA = {".png", ".gif"}
_PATRON = re.compile(r"^(captura|grabacion)_(?:([a-z0-9-]+)_)?\d{4}-\d{2}-\d{2}_\d{6}")


def slug(texto: str) -> str:  # propio
    """'Configuración' -> 'configuracion' (sin acentos, minúsculas, sin espacios)."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sin_acentos.lower()).strip("-")


@dataclass
class Captura:
    ruta: Path

    @property
    def nombre(self) -> str:  # propio
        return self.ruta.name

    @property
    def origen(self) -> str | None:  # propio
        """Slug del módulo donde se tomó ('agenda'), o None."""
        m = _PATRON.match(self.ruta.stem)
        return m.group(2) if m else None

    @property
    def es_grabacion(self) -> bool:  # propio
        return self.ruta.suffix.lower() == ".gif"

    @property
    def tamano(self) -> int:  # propio
        return self.ruta.stat().st_size if self.ruta.exists() else 0

    @property
    def fecha(self) -> datetime:  # propio
        return datetime.fromtimestamp(self.ruta.stat().st_mtime)


def _new_path(prefijo: str, ext: str, origen: str | None) -> Path:  # propio
    CAPTURAS_DIR.mkdir(parents=True, exist_ok=True)
    medio = f"_{slug(origen)}" if origen else ""
    base = f"{prefijo}{medio}_{datetime.now():%Y-%m-%d_%H%M%S}"
    ruta = CAPTURAS_DIR / f"{base}{ext}"
    n = 2
    while ruta.exists():  # dos capturas en el mismo segundo
        ruta = CAPTURAS_DIR / f"{base}_{n}{ext}"
        n += 1
    return ruta


def save_screenshot(png: bytes, origen: str | None = None) -> Captura:  # propio
    ruta = _new_path("captura", ".png", origen)
    ruta.write_bytes(png)
    return Captura(ruta)


def save_recording(cuadros: list[bytes], tiempos_ms: list[int],  # propio
                   origen: str | None = None, ancho_max: int = 480) -> Captura:
    """
    Arma el GIF animado con los PNG de la grabación.
      tiempos_ms[i] = cuánto dura el cuadro i (lo que tardó en llegar el siguiente)
      ancho_max     = se reduce a este ancho para que el GIF no pese de más
    Pillow se importa aquí: solo se necesita al grabar.
    """
    from PIL import Image

    if not cuadros:
        raise ValueError("La grabación no tiene cuadros")
    imagenes = []
    for png in cuadros:
        img = Image.open(BytesIO(png)).convert("RGB")
        if img.width > ancho_max:
            alto = round(img.height * ancho_max / img.width)
            img = img.resize((ancho_max, alto), Image.Resampling.LANCZOS)
        # GIF solo admite 256 colores por cuadro
        imagenes.append(img.quantize(colors=256, method=Image.Quantize.MEDIANCUT))

    ruta = _new_path("grabacion", ".gif", origen)
    imagenes[0].save(
        ruta,
        save_all=True,
        append_images=imagenes[1:],
        duration=[max(t, 50) for t in tiempos_ms],
        loop=0,          # se repite siempre
        optimize=True,
    )
    return Captura(ruta)


def list_captures() -> list[Captura]:  # propio
    """Lo que hay en la bandeja, lo más reciente primero."""
    if not CAPTURAS_DIR.exists():
        return []
    archivos = [p for p in CAPTURAS_DIR.iterdir() if p.suffix.lower() in EXT_CAPTURA]
    return [Captura(p) for p in sorted(archivos, key=lambda p: p.stat().st_mtime, reverse=True)]


def delete_capture(ruta: Path | str) -> None:  # propio
    Path(ruta).unlink(missing_ok=True)

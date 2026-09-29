"""
Colores de los reportes de Finanzas, compartidos por la pantalla (reportes.py)
y el Excel exportado (exportador.py), para que "Nu" sea del mismo color en los dos.

  - Cada plataforma tiene SIEMPRE el mismo color (se asigna por su id, no por
    su tamaño), así no cambia de color al cambiar de filtro o de periodo.
  - Las plataformas que nunca se usaron no gastan colores; si hubiera más de
    8 usadas, las extra van en gris.
"""
from modulos.finanzas.models import Plataforma

# Paleta categórica validada (orden fijo; modo claro / modo oscuro)
PALETA_CLARO = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
PALETA_OSCURO = ["#3987e5", "#d95926", "#199e70", "#c98500",
                 "#d55181", "#008300", "#9085e9", "#e66767"]
GRIS_OTRAS = "#8c8b86"
AZUL = "#2a78d6"


def platform_colors(paleta: list[str] = PALETA_CLARO) -> dict[int, str]:  # propio
    """{plataforma_id: "#rrggbb"} en orden de alta entre las plataformas usadas."""
    usadas = Plataforma.usage_count()
    ids = sorted(p.id for p in Plataforma.search_all() if usadas.get(p.id))
    return {pid: paleta[i] if i < len(paleta) else GRIS_OTRAS for i, pid in enumerate(ids)}

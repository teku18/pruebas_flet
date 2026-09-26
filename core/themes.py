"""
Colores de la aplicación.

Flet genera toda la paleta (barras, botones, fondos, modo claro y oscuro)
a partir de un solo color "semilla" (color_scheme_seed). Por eso basta con
elegir uno de esta lista para cambiar el color de TODA la app.

Para agregar un color: una línea más en THEME_COLORS.
"""
import flet as ft

# {clave_guardada: (etiqueta visible, color semilla)}
THEME_COLORS = {
    "kraken": ("Kraken", ft.Colors.DEEP_ORANGE),
    "rojo": ("Rojo", ft.Colors.RED),
    "rosa": ("Rosa", ft.Colors.PINK),
    "morado": ("Morado", ft.Colors.PURPLE),
    "indigo": ("Índigo", ft.Colors.INDIGO),
    "azul": ("Azul", ft.Colors.BLUE),
    "cian": ("Cian", ft.Colors.CYAN),
    "turquesa": ("Turquesa", ft.Colors.TEAL),
    "verde": ("Verde", ft.Colors.GREEN),
    "ambar": ("Ámbar", ft.Colors.AMBER),
    "cafe": ("Café", ft.Colors.BROWN),
    "grafito": ("Grafito", ft.Colors.BLUE_GREY),
}
DEFAULT_COLOR = "kraken"

# Modo claro / oscuro / según el sistema
THEME_MODES = {
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
    "system": ft.ThemeMode.SYSTEM,
}
DEFAULT_MODE = "light"


def apply_color(page: ft.Page, clave: str) -> None:  # propio
    """Pinta toda la app con el color elegido (en claro y en oscuro)."""
    _, semilla = THEME_COLORS.get(clave, THEME_COLORS[DEFAULT_COLOR])
    page.theme = ft.Theme(color_scheme_seed=semilla)
    page.dark_theme = ft.Theme(color_scheme_seed=semilla)


def apply_mode(page: ft.Page, clave: str) -> None:  # propio
    page.theme_mode = THEME_MODES.get(clave, THEME_MODES[DEFAULT_MODE])

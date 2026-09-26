"""
Pantalla de Configuración (/ajustes):
  - Modo: claro / oscuro / sistema
  - Color de la app: 12 colores (core/themes.py)
Ambas preferencias se guardan en el dispositivo y se aplican al abrir la app.
"""
import flet as ft

from core import APP_VERSION
from core.themes import (
    DEFAULT_COLOR,
    DEFAULT_MODE,
    THEME_COLORS,
    THEME_MODES,
    apply_color,
    apply_mode,
)

CLAVE_MODO = "tema"    # se conserva la clave anterior para no perder tu elección
CLAVE_COLOR = "color"


class SettingsView:
    def __init__(self, page: ft.Page, route: str):
        self.page = page
        # Guarda la preferencia en el dispositivo (persiste al cerrar la app)
        self.prefs = ft.SharedPreferences()
        self.color_actual = DEFAULT_COLOR

        self.seg_modo = ft.SegmentedButton(
            selected=[DEFAULT_MODE],
            on_change=self.change_mode,
            segments=[
                ft.Segment(
                    value="light", icon=ft.Icon(ft.Icons.LIGHT_MODE), label=ft.Text("Claro")
                ),
                ft.Segment(
                    value="dark", icon=ft.Icon(ft.Icons.DARK_MODE), label=ft.Text("Oscuro")
                ),
                ft.Segment(
                    value="system",
                    icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO),
                    label=ft.Text("Sistema"),
                ),
            ],
        )

        # Cuadrícula de colores (se redibuja al elegir uno para mover la ✓)
        self.rejilla_colores = ft.Row(wrap=True, spacing=4, run_spacing=12)
        self._build_color_grid()

        self.vista = ft.View(
            route=route,
            appbar=ft.AppBar(title=ft.Text("Configuración")),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Text("Modo", size=18, weight=ft.FontWeight.BOLD),
                            self.seg_modo,
                            ft.Divider(),
                            ft.Text("Color de la app", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                "Cambia barras, botones y tarjetas de todos los módulos.",
                                size=12,
                                color=ft.Colors.OUTLINE,
                            ),
                            self.rejilla_colores,
                            ft.Divider(),
                            ft.Text(
                                f"ControlKraken v{APP_VERSION}",
                                size=12,
                                color=ft.Colors.OUTLINE,
                            ),
                        ],
                    )
                )
            ],
        )

    # ==================================================================
    # Color
    # ==================================================================
    def _build_color_grid(self):  # propio
        self.rejilla_colores.controls = [
            self._color_swatch(clave, etiqueta, semilla)
            for clave, (etiqueta, semilla) in THEME_COLORS.items()
        ]

    def _color_swatch(self, clave: str, etiqueta: str, semilla) -> ft.Control:  # propio
        """Un círculo de color con su nombre; el elegido lleva ✓."""
        elegido = clave == self.color_actual
        return ft.Column(
            width=84,
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=52 if elegido else 44,
                    height=52 if elegido else 44,
                    border_radius=26,
                    bgcolor=semilla,
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    on_click=lambda e, c=clave: self.page.run_task(self.change_color, c),
                    content=ft.Icon(ft.Icons.CHECK, color=ft.Colors.WHITE) if elegido else None,
                ),
                ft.Text(
                    etiqueta,
                    size=12,
                    weight=ft.FontWeight.BOLD if elegido else ft.FontWeight.NORMAL,
                ),
            ],
        )

    def _set_color(self, clave: str):  # propio
        self.color_actual = clave
        apply_color(self.page, clave)
        self._build_color_grid()

    async def change_color(self, clave: str):  # propio
        self._set_color(clave)
        self.page.update()
        await self.prefs.set(CLAVE_COLOR, clave)

    # ==================================================================
    # Modo claro / oscuro
    # ==================================================================
    def _set_mode(self, valor: str):  # propio
        apply_mode(self.page, valor)
        self.seg_modo.selected = [valor]

    async def change_mode(self, e):  # propio
        valor = self.seg_modo.selected[0]
        self._set_mode(valor)
        self.page.update()
        await self.prefs.set(CLAVE_MODO, valor)

    # ==================================================================
    async def load_saved(self):  # propio
        """Aplica el modo y el color que el usuario eligió la última vez."""
        modo = await self.prefs.get(CLAVE_MODO)
        color = await self.prefs.get(CLAVE_COLOR)
        self._set_mode(modo if modo in THEME_MODES else DEFAULT_MODE)
        self._set_color(color if color in THEME_COLORS else DEFAULT_COLOR)
        self.page.update()

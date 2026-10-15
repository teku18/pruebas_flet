"""
Pantalla de inicio de Kraken Tools (/kraken): una tarjeta por herramienta.

  [🌐 Cliente HTTP     ]  [🗄 Explorador SQLite]
  [🖧 Red  Próximamente]  [⌨ SSH  Próximamente]

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import icon_box
from modulos.kraken import routes
from modulos.kraken.herramientas import HERRAMIENTAS, Herramienta


class KrakenHome:
    def __init__(self, page: ft.Page):
        self.page = page
        self.vista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(title=ft.Text("Kraken Tools")),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.ResponsiveRow(
                spacing=10, run_spacing=10,
                controls=[self._card(h) for h in HERRAMIENTAS]))],
        )

    def _card(self, h: Herramienta) -> ft.Control:  # propio
        pie = (ft.Text(h.descripcion, size=12, color=ft.Colors.OUTLINE) if h.listo else
               ft.Row(spacing=4, controls=[
                   ft.Icon(ft.Icons.CONSTRUCTION, size=14, color=ft.Colors.OUTLINE),
                   ft.Text("Próximamente", size=12, italic=True, color=ft.Colors.OUTLINE)]))
        return ft.Card(
            col={"xs": 12, "sm": 6}, opacity=1 if h.listo else 0.6,
            content=ft.Container(
                padding=14, ink=h.listo, border_radius=12,
                on_click=(lambda e, r=h.route: self.page.navigate(r)) if h.listo else None,
                content=ft.Row(spacing=12, controls=[
                    icon_box(h.icono, h.color),
                    ft.Column(spacing=2, expand=True, controls=[
                        ft.Text(h.nombre, weight=ft.FontWeight.BOLD), pie]),
                ]),
            ),
        )

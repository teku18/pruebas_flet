"""
Pantalla "Mis capturas" (/desarrollo/capturas): la bandeja de lo que tomaste
con el botón flotante y todavía no adjuntas a ningún pendiente.

  ┌──────────┐ ┌──────────┐
  │  imagen  │ │  🎥 GIF   │   tocar = verla en grande
  │ Agenda   │ │ Finanzas │
  │ 29/09 …  │ │ 29/09 …  │
  │ [Reportar] [🗑]        │
  └──────────┘ └──────────┘

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.storage import human_size
from core.ui import confirm, notify
from modulos.desarrollo import routes
from modulos.desarrollo.capturas import Captura, delete_capture, list_captures
from modulos.desarrollo.views.adjuntos import show_preview


class CapturesView:
    def __init__(self, page: ft.Page, on_report):
        """on_report(capturas): pendiente nuevo con esas capturas adjuntas."""
        self.page = page
        self.on_report = on_report
        self.grid = ft.ResponsiveRow(spacing=10, run_spacing=10)
        self.lbl_vacio = ft.Text(
            "No hay capturas pendientes.\nUsa el botón 📷 flotante en cualquier pantalla.",
            italic=True, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER,
        )
        self.vista = ft.View(
            route=routes.CAPTURAS,
            appbar=ft.AppBar(title=ft.Text("Mis capturas")),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column([self.lbl_vacio, self.grid]))],
        )

    def load(self):  # propio
        capturas = list_captures()
        self.lbl_vacio.visible = not capturas
        self.grid.controls = [self._card(c) for c in capturas]

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _card(self, c: Captura) -> ft.Control:  # propio
        tipo = "🎥 Grabación" if c.es_grabacion else "📷 Captura"
        origen = (c.origen or "").capitalize() or "—"
        contenido = c.ruta.read_bytes()
        return ft.Container(
            col=6,
            padding=8,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Container(
                        height=170,
                        border_radius=8,
                        ink=True,
                        on_click=lambda e: show_preview(self.page, c.nombre, contenido),
                        content=ft.Image(src=contenido, fit=ft.BoxFit.COVER, height=170,
                                         border_radius=8),
                    ),
                    ft.Text(f"{tipo} · {origen}", size=12, weight=ft.FontWeight.W_500),
                    ft.Text(f"{c.fecha:%d/%m %H:%M} · {human_size(c.tamano)}", size=11,
                            color=ft.Colors.OUTLINE),
                    ft.Row(
                        spacing=0,
                        controls=[
                            ft.TextButton("Reportar", icon=ft.Icons.BUG_REPORT,
                                          on_click=lambda e: self.on_report([c])),
                            ft.IconButton(ft.Icons.DELETE, icon_color=ft.Colors.RED,
                                          tooltip="Eliminar",
                                          on_click=lambda e: self._delete(c)),
                        ],
                    ),
                ],
            ),
        )

    def _delete(self, c: Captura):  # propio
        def delete():  # propio
            delete_capture(c.ruta)
            notify(self.page, "Captura eliminada")
            self.refresh()

        confirm(self.page, "Eliminar captura", "¿Eliminar esta captura de la bandeja?", delete)

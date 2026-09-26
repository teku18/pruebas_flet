"""
Pantalla de inicio de Control Kraken: una tarjeta por módulo.

Las tarjetas se arman solas con la lista de módulos (nombre, ícono, ruta),
así que un módulo nuevo aparece aquí sin tocar este archivo.
Los colores salen del tema (PRIMARY, SURFACE...), por eso cambian junto
con el color elegido en Configuración.
"""
import flet as ft

from core.module import AppModule

APP_NAME = "Control Kraken"
LEMA = "Tu vida, bajo control"


class HomeView:
    def __init__(self, page: ft.Page, modulos: list[AppModule]):
        self.page = page
        self.vista = ft.View(
            route="/",
            scroll=ft.ScrollMode.AUTO,
            padding=ft.Padding.all(20),
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=24,
                        controls=[
                            self._header(),
                            ft.ResponsiveRow(
                                spacing=12,
                                run_spacing=12,
                                controls=[self._card(m) for m in modulos],
                            ),
                        ],
                    )
                )
            ],
        )

    def _header(self) -> ft.Control:  # propio
        """Logo provisional (emoji de pulpo) + nombre de la app."""
        return ft.Row(
            spacing=14,
            controls=[
                ft.Container(
                    width=64,
                    height=64,
                    border_radius=32,
                    bgcolor=ft.Colors.PRIMARY_CONTAINER,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("🐙", size=34),
                ),
                ft.Column(
                    spacing=0,
                    controls=[
                        ft.Text(APP_NAME, size=26, weight=ft.FontWeight.BOLD),
                        ft.Text(LEMA, size=13, color=ft.Colors.OUTLINE),
                    ],
                ),
            ],
        )

    def _card(self, modulo: AppModule) -> ft.Control:  # propio
        """Tarjeta de un módulo; al tocarla se abre su ruta."""
        textos = [
            ft.Text(modulo.nombre, size=16, weight=ft.FontWeight.BOLD),
            ft.Text(modulo.descripcion, size=12, color=ft.Colors.OUTLINE),
        ]
        if not modulo.listo:
            textos.append(
                ft.Text("Próximamente", size=11, italic=True, color=ft.Colors.PRIMARY)
            )

        return ft.Container(
            col=6,  # dos tarjetas por fila (12 columnas / 6)
            height=160,
            padding=16,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ink=True,
            on_click=lambda e, r=modulo.route: self.page.navigate(r),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Container(
                        width=48,
                        height=48,
                        border_radius=12,
                        bgcolor=ft.Colors.PRIMARY_CONTAINER,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(
                            modulo.icono, size=28, color=ft.Colors.ON_PRIMARY_CONTAINER
                        ),
                    ),
                    *textos,
                ],
            ),
        )

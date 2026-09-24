"""
Pantalla de Ajustes:
  /ajustes -> tema claro / oscuro / sistema
"""
import flet as ft

TEMAS = {
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
    "system": ft.ThemeMode.SYSTEM,
}
CLAVE_TEMA = "tema"


class AjustesVista:
    def __init__(self, page: ft.Page):
        self.page = page
        # Guarda la preferencia en el dispositivo (persiste al cerrar la app)
        self.prefs = ft.SharedPreferences()

        self.seg_tema = ft.SegmentedButton(
            selected=["light"],
            on_change=self.cambiar_tema,
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

        self.vista = ft.View(
            route="/ajustes",
            appbar=ft.AppBar(title=ft.Text("Ajustes")),
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Text("Tema", size=18, weight=ft.FontWeight.BOLD),
                            self.seg_tema,
                        ],
                    )
                )
            ],
        )

    def aplicar_tema(self, valor: str):
        self.page.theme_mode = TEMAS[valor]
        self.seg_tema.selected = [valor]

    async def cambiar_tema(self, e):
        valor = self.seg_tema.selected[0]
        self.aplicar_tema(valor)
        self.page.update()
        await self.prefs.set(CLAVE_TEMA, valor)

    async def cargar_tema_guardado(self):
        """Aplica el tema que el usuario eligió la última vez."""
        valor = await self.prefs.get(CLAVE_TEMA)
        if valor in TEMAS:
            self.aplicar_tema(valor)
            self.page.update()

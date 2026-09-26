"""
Módulo Memorias: dictar pensamientos y anécdotas, guardarlos como texto
con su fecha y poder reproducir el audio. (Por ahora, solo la pantalla.)
"""
import flet as ft

from core.module import AppModule
from core.ui import coming_soon_view


class MemoriasModule(AppModule):
    nombre = "Memorias"
    descripcion = "Tus pensamientos por voz"
    icono = ft.Icons.AUTO_STORIES
    route = "/memorias"
    listo = False

    def __init__(self, page: ft.Page):
        super().__init__(page)
        self.vista = coming_soon_view(
            self.route,
            self.nombre,
            self.icono,
            "Dicta una idea o anécdota y se guarda como texto con su fecha.",
        )

    def build_views(self, route: str) -> list[ft.View]:  # propio
        return [self.vista]

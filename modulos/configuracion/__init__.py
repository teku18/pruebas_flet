"""Módulo Configuración: modo claro/oscuro y color de la app."""
import flet as ft

from core.module import AppModule
from modulos.configuracion.views import SettingsView


class ConfiguracionModule(AppModule):
    nombre = "Configuración"
    descripcion = "Tema y colores"
    icono = ft.Icons.SETTINGS
    route = "/ajustes"

    def __init__(self, page: ft.Page):
        super().__init__(page)
        self.ajustes = SettingsView(page, self.route)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        return [self.ajustes.vista]

    async def on_start(self) -> None:  # propio
        await self.ajustes.load_saved()

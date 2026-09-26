"""
Módulo Agenda (el "chismoso"): recordatorios recurrentes, marcar como hecho
y ver los pendientes por colores de urgencia. (Por ahora, solo la pantalla.)
"""
import flet as ft

from core.module import AppModule
from core.ui import coming_soon_view


class AgendaModule(AppModule):
    nombre = "Agenda"
    descripcion = "Pendientes y recordatorios"
    icono = ft.Icons.EVENT_NOTE
    route = "/agenda"
    listo = False

    def __init__(self, page: ft.Page):
        super().__init__(page)
        self.vista = coming_soon_view(
            self.route,
            self.nombre,
            self.icono,
            "Tus pendientes del día, lo vencido en rojo y lo de mañana a la vista.",
        )

    def build_views(self, route: str) -> list[ft.View]:  # propio
        return [self.vista]

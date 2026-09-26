"""
Contrato que cumple cada módulo de Control Kraken
(parecido al __manifest__ + estructura de un addon de Odoo).

Para agregar un módulo nuevo:
  1. Crea modulos/<nombre>/__init__.py con una clase que herede de AppModule
  2. Regístrala en la lista MODULES de modulos/__init__.py
La pantalla de inicio y la navegación lo toman solos.
"""
import flet as ft


class AppModule:
    nombre = ""          # texto de la tarjeta en el inicio
    descripcion = ""     # subtítulo de la tarjeta
    icono = ft.Icons.APPS
    route = ""           # ruta base, p. ej. "/finanzas"
    listo = True         # False -> la tarjeta muestra "Próximamente"

    def __init__(self, page: ft.Page):
        self.page = page

    def build_views(self, route: str) -> list[ft.View]:  # propio
        """Pantallas que se apilan encima del inicio para esta ruta."""
        return []

    def go_back(self, route: str) -> None:  # propio
        """Flecha de regreso dentro del módulo. Por defecto: al inicio."""
        self.page.navigate("/")

    async def on_start(self) -> None:  # propio
        """Se llama una vez al abrir la app (p. ej. cargar preferencias)."""

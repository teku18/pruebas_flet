"""
Control Kraken — punto de entrada.

Estructura del proyecto:
  core/                 -> lo compartido: BD, CrudMixin, UI común, temas, inicio
  modulos/finanzas/     -> Periodo, Movimiento y sus pantallas
  modulos/memorias/     -> (próximamente) pensamientos por voz
  modulos/agenda/       -> (próximamente) pendientes / chismoso
  modulos/configuracion -> modo claro/oscuro y color de la app

Convención: los métodos y funciones marcados con  # propio  son nuestros;
lo que no lo tiene (page.update, page.navigate, ft.*) viene de Flet.
"""
import flet as ft

from core.database import init_db
from core.home import APP_NAME, HomeView
from core.themes import DEFAULT_COLOR, apply_color
from modulos import MODULES


def main(page: ft.Page):  # propio
    # Crea la BD / tablas si no existen (y migra si hace falta)
    init_db()

    # Configuración visual (el modo y color guardados se aplican al final)
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.LIGHT
    apply_color(page, DEFAULT_COLOR)

    # Tamaño de ventana (ahora se configura en page.window, no en ft.run)
    page.window.width = 412
    page.window.height = 915
    page.window.resizable = False
    page.window.maximizable = False

    # ------------------------------------------------------------------
    # Módulos + pantalla de inicio
    # ------------------------------------------------------------------
    modulos = [Modulo(page) for Modulo in MODULES]
    inicio = HomeView(page, modulos)

    def module_for(route: str):  # propio
        """El módulo dueño de la ruta ("/finanzas/..." -> Finanzas), o None."""
        for m in modulos:
            if route == m.route or route.startswith(m.route + "/"):
                return m
        return None

    # ------------------------------------------------------------------
    # Navegación: el inicio siempre abajo y encima las pantallas del módulo.
    #   /            -> Inicio
    #   /finanzas... -> Inicio > (pantallas de Finanzas)
    #   /memorias    -> Inicio > Memorias
    #   /agenda      -> Inicio > Agenda
    #   /ajustes     -> Inicio > Configuración
    # ------------------------------------------------------------------
    def on_route_change(e=None):  # propio
        page.views.clear()
        page.views.append(inicio.vista)
        modulo = module_for(page.route)
        if modulo is not None:
            page.views.extend(modulo.build_views(page.route))
        page.update()

    def on_back(e):  # propio
        """Flecha de regreso (o botón atrás del celular)."""
        modulo = module_for(page.route)
        if modulo is not None:
            modulo.go_back(page.route)
        else:
            page.navigate("/")

    page.on_route_change = on_route_change
    page.on_view_pop = on_back

    on_route_change()

    # Cada módulo carga lo que necesite al arrancar (p. ej. el tema guardado)
    for m in modulos:
        page.run_task(m.on_start)


# Ejecuta la aplicación
if __name__ == "__main__":
    ft.run(main)

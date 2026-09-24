"""
Punto de entrada: configura la página, crea las pantallas y maneja las rutas.

Estructura del proyecto:
  models/  -> datos (SQLAlchemy): Periodo, Movimiento
  views/   -> pantallas (Flet): una clase por pantalla con sus acciones
"""
import flet as ft

from database import init_db
from views import AjustesVista, MovimientosVista, PeriodosVista


def main(page: ft.Page):
    # Crea la BD / tablas si no existen (y migra si hace falta)
    init_db()

    # Configuración visual
    page.title = "Mi Primera App"
    page.theme_mode = ft.ThemeMode.LIGHT
    # Misma paleta (azul) para ambos temas; Flet genera los tonos claros/oscuros
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.Colors.BLUE)

    # Tamaño de ventana (ahora se configura en page.window, no en ft.run)
    page.window.width = 412
    page.window.height = 915
    page.window.resizable = False
    page.window.maximizable = False

    # ------------------------------------------------------------------
    # Pantallas
    # ------------------------------------------------------------------
    # Las pantallas se avisan entre sí con funciones (callbacks):
    #   Periodos    --tocar un periodo-->  Movimientos.abrir_periodo
    #   Movimientos --engrane----------->  Periodos.ver
    # (el lambda se evalúa al hacer clic, cuando "periodos" ya existe)
    movimientos = MovimientosVista(page, al_ver_periodo=lambda per: periodos.ver(per))
    periodos = PeriodosVista(page, al_abrir_periodo=movimientos.abrir_periodo)
    ajustes = AjustesVista(page)

    # ------------------------------------------------------------------
    # Navegación: según la ruta, se apilan las pantallas.
    #   /                    -> Periodos
    #   /periodo             -> Periodos > Nuevo periodo
    #   /movimientos         -> Periodos > Movimientos del periodo
    #   /movimientos/periodo -> Periodos > Movimientos > Datos del periodo (engrane)
    #   /movimiento          -> Periodos > Movimientos > Movimiento
    #   /ajustes             -> Periodos > Ajustes
    # ------------------------------------------------------------------
    def cambio_de_ruta(e=None):
        # Sin periodo abierto (o si se eliminó) no hay movimientos: volver al inicio
        if page.route.startswith("/movimiento"):
            if movimientos.periodo is not None:
                movimientos.cargar()  # relee el periodo y su lista
            if movimientos.periodo is None:
                page.route = "/"

        page.views.clear()
        page.views.append(periodos.vista_lista)
        if page.route == "/":
            periodos.cargar()  # refresca nombres y cantidad de movimientos
        elif page.route == "/periodo":
            periodos.vista_form.route = page.route
            page.views.append(periodos.vista_form)
        elif page.route == "/movimientos":
            page.views.append(movimientos.vista_lista)
        elif page.route == "/movimientos/periodo":
            periodos.vista_form.route = page.route
            page.views.append(movimientos.vista_lista)
            page.views.append(periodos.vista_form)
        elif page.route == "/movimiento":
            page.views.append(movimientos.vista_lista)
            page.views.append(movimientos.vista_form)
        elif page.route == "/ajustes":
            page.views.append(ajustes.vista)
        page.update()

    def regresar(e):
        """Flecha de regreso (o botón atrás del celular)."""
        # Al salir de un formulario se descarta lo que no se guardó
        if page.route == "/movimiento":
            movimientos.limpiar_formulario()
            page.navigate("/movimientos")
        elif page.route == "/movimientos/periodo":
            periodos.limpiar_formulario()
            page.navigate("/movimientos")
        else:
            if page.route == "/periodo":
                periodos.limpiar_formulario()
            page.navigate("/")

    page.on_route_change = cambio_de_ruta
    page.on_view_pop = regresar

    cambio_de_ruta()

    # Aplica el tema que el usuario eligió la última vez
    page.run_task(ajustes.cargar_tema_guardado)


# Ejecuta la aplicación
if __name__ == "__main__":
    ft.run(main)

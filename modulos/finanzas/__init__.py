"""
Módulo Finanzas: periodos y sus movimientos.

Navegación (se apila encima de la pantalla de inicio):
  /finanzas                      -> Periodos
  /finanzas/periodo              -> Periodos > Nuevo periodo
  /finanzas/movimientos          -> Periodos > Movimientos del periodo
  /finanzas/movimientos/periodo  -> Periodos > Movimientos > Datos del periodo (engrane)
  /finanzas/movimiento           -> Periodos > Movimientos > Movimiento
"""
import flet as ft

from core.module import AppModule
from modulos.finanzas import routes


class FinanzasModule(AppModule):
    nombre = "Finanzas"
    descripcion = "Periodos y movimientos"
    icono = ft.Icons.ACCOUNT_BALANCE_WALLET
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        # Import aquí para que los modelos se registren después de core.database
        from modulos.finanzas.views import MovementsView, PeriodsView

        # Las pantallas se avisan entre sí con funciones (callbacks):
        #   Periodos    --tocar un periodo-->  Movimientos.open_period
        #   Movimientos --engrane----------->  Periodos.show
        # (el lambda se evalúa al hacer clic, cuando "self.periodos" ya existe)
        self.movimientos = MovementsView(page, on_show_period=lambda per: self.periodos.show(per))
        self.periodos = PeriodsView(page, on_open_period=self.movimientos.open_period)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        movs, pers = self.movimientos, self.periodos

        # Sin periodo abierto (o si se eliminó) no hay movimientos: a la lista
        if route.startswith(routes.MOVIMIENTO):  # cubre /movimiento y /movimientos...
            if movs.periodo is not None:
                movs.load()  # relee el periodo y su lista
            if movs.periodo is None:
                route = routes.BASE
                self.page.route = route

        vistas = [pers.vista_lista]
        if route == routes.BASE:
            pers.load()  # refresca nombres y cantidad de movimientos
        elif route == routes.PERIODO:
            pers.vista_form.route = route
            vistas.append(pers.vista_form)
        elif route == routes.MOVIMIENTOS:
            vistas.append(movs.vista_lista)
        elif route == routes.MOVIMIENTOS_PERIODO:
            pers.vista_form.route = route
            vistas += [movs.vista_lista, pers.vista_form]
        elif route == routes.MOVIMIENTO:
            vistas += [movs.vista_lista, movs.vista_form]
        return vistas

    def go_back(self, route: str) -> None:  # propio
        """Flecha de regreso: al salir de un formulario se descarta lo no guardado."""
        if route == routes.MOVIMIENTO:
            self.movimientos.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)
        elif route == routes.MOVIMIENTOS_PERIODO:
            self.periodos.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)
        elif route == routes.PERIODO:
            self.periodos.clear_form()
            self.page.navigate(routes.BASE)
        elif route == routes.MOVIMIENTOS:
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")  # de la lista de periodos al inicio

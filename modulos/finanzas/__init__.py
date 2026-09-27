"""
Módulo Finanzas: periodos, movimientos, traspasos y sus catálogos.

Navegación (se apila encima de la pantalla de inicio):
  /finanzas                      -> Periodos
  /finanzas/periodo              -> Periodos > Nuevo periodo
  /finanzas/movimientos          -> Periodos > Movimientos del periodo
  /finanzas/movimientos/periodo  -> Periodos > Movimientos > Datos del periodo (engrane)
  /finanzas/movimiento           -> Periodos > Movimientos > Movimiento
  /finanzas/traspaso             -> Periodos > Movimientos > Traspaso (⇄)
  /finanzas/reportes             -> Periodos > Reportes (📊, cualquier periodo)
  /finanzas/movimientos/reportes -> Periodos > Movimientos > Reportes (📊, solo ese periodo)
  /finanzas/ajustes              -> Periodos > Ajustes de Finanzas (engrane)
  /finanzas/ajustes/plataformas  -> Periodos > Ajustes > Plataformas
  /finanzas/ajustes/inversiones  -> Periodos > Ajustes > Conceptos
"""
import flet as ft

from core.module import AppModule
from modulos.finanzas import routes

# Rutas que necesitan un periodo abierto
RUTAS_CON_PERIODO = (routes.MOVIMIENTOS, routes.MOVIMIENTOS_PERIODO,
                     routes.MOVIMIENTO, routes.TRASPASO, routes.MOVIMIENTOS_REPORTES)


class FinanzasModule(AppModule):
    nombre = "Finanzas"
    descripcion = "Periodos y movimientos"
    icono = ft.Icons.ACCOUNT_BALANCE_WALLET
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        # Import aquí para que los modelos se registren después de core.database
        from modulos.finanzas.models import Inversion, Plataforma
        from modulos.finanzas.views import (
            CatalogView,
            FinanceSettingsView,
            MovementsView,
            PeriodsView,
            ReportsView,
            TransferView,
        )

        # Las pantallas se avisan entre sí con funciones (callbacks):
        #   Periodos    --tocar un periodo-->  Movimientos.open_period
        #   Movimientos --engrane----------->  Periodos.show
        #   Movimientos --⇄----------------->  Traspaso.open
        #   Movimientos --📊----------------->  Reportes.open_for_period
        # (los lambda se evalúan al hacer clic, cuando todo ya existe)
        self.movimientos = MovementsView(
            page,
            on_show_period=lambda per: self.periodos.show(per),
            on_transfer=lambda: self.traspaso.open(),
            on_reports=lambda per, inv: self.reportes.open_for_period(per, inv),
        )
        self.periodos = PeriodsView(page, on_open_period=self.movimientos.open_period,
                                    on_reports=lambda: self.reportes.open_general())
        self.traspaso = TransferView(page, get_period=lambda: self.movimientos.periodo)
        self.reportes = ReportsView(page)
        self.ajustes = FinanceSettingsView(page, on_imported=self.periodos.load)
        self.plataformas = CatalogView(page, Plataforma, routes.PLATAFORMAS,
                                       ft.Icons.ACCOUNT_BALANCE)
        self.inversiones = CatalogView(page, Inversion, routes.INVERSIONES, ft.Icons.FLAG)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        movs, pers = self.movimientos, self.periodos

        # Sin periodo abierto (o si se eliminó) no hay movimientos: a la lista
        if route in RUTAS_CON_PERIODO:
            if movs.periodo is not None:
                movs.load()  # relee el periodo, su resumen y su lista
            if movs.periodo is None:
                route = routes.BASE
                self.page.route = route

        vistas = [pers.vista_lista]
        if route == routes.BASE:
            pers.load()  # refresca nombres, netos y acumulado global
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
        elif route == routes.TRASPASO:
            vistas += [movs.vista_lista, self.traspaso.vista]
        elif route == routes.REPORTES:
            self.reportes.fijo = False
            self.reportes.load()
            vistas.append(self.reportes.vista)
        elif route == routes.MOVIMIENTOS_REPORTES:
            self.reportes.load()
            vistas += [movs.vista_lista, self.reportes.vista]
        elif route == routes.AJUSTES:
            self.ajustes.load()
            vistas.append(self.ajustes.vista)
        elif route in (routes.PLATAFORMAS, routes.INVERSIONES):
            catalogo = self.plataformas if route == routes.PLATAFORMAS else self.inversiones
            catalogo.load()
            vistas += [self.ajustes.vista, catalogo.vista]
        return vistas

    def go_back(self, route: str) -> None:  # propio
        """Flecha de regreso: al salir de un formulario se descarta lo no guardado."""
        if route == routes.MOVIMIENTO:
            self.movimientos.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)
        elif route in (routes.MOVIMIENTOS_PERIODO, routes.TRASPASO,
                       routes.MOVIMIENTOS_REPORTES):
            if route == routes.MOVIMIENTOS_PERIODO:
                self.periodos.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)
        elif route == routes.PERIODO:
            self.periodos.clear_form()
            self.page.navigate(routes.BASE)
        elif route in (routes.PLATAFORMAS, routes.INVERSIONES):
            self.page.navigate(routes.AJUSTES)
        elif route in (routes.MOVIMIENTOS, routes.AJUSTES, routes.REPORTES):
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")  # de la lista de periodos al inicio

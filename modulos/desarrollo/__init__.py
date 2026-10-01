"""
Módulo Desarrollo: el roadmap de la propia app.
Cada módulo de ControlKraken con su descripción, prioridad y % de avance,
y sus pendientes (tareas, errores, comentarios) ordenados por prioridad.

Navegación (encima de la pantalla de inicio):
  /desarrollo                   -> [Módulos] [Pendientes]
  /desarrollo/nuevo             -> Desarrollo > Nuevo módulo
  /desarrollo/modulo            -> Desarrollo > Pendientes del módulo
  /desarrollo/modulo/datos      -> Desarrollo > Módulo > Datos (engrane)
  /desarrollo/modulo/pendiente  -> Desarrollo > Módulo > Pendiente
  /desarrollo/pendiente         -> Desarrollo > Pendiente (desde la pestaña Pendientes)
  /desarrollo/capturas          -> Desarrollo > Mis capturas (bandeja)

Además instala en TODAS las pantallas el botón flotante 📷 para capturar o
grabar la pantalla y reportarlo como pendiente (views/herramienta.py).

Capas:
  models/       ModuloApp, Pendiente, DevAdjunto          (la despensa)
  services.py   overview, pending_by_priority, toggle     (el cocinero)
  capturas.py   bandeja de capturas (PNG) y grabaciones (GIF)
  exportador.py Excel: Resumen + una hoja por módulo
  views/        RoadmapView, ModuleView, formularios,
                CapturesView, CaptureTool (botón flotante) (el mesero)
"""
import flet as ft

from core.module import AppModule
from modulos.desarrollo import routes


class DesarrolloModule(AppModule):
    nombre = "Desarrollo"
    descripcion = "Pendientes de la app"
    icono = ft.Icons.CONSTRUCTION
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.desarrollo.views import (
            CapturesView,
            CaptureTool,
            ModuleFormView,
            ModuleView,
            PendingFormView,
            RoadmapView,
        )

        nav = page.navigate

        # Formularios: al terminar regresan a la pantalla de la que vinieron
        self.form_pendiente = PendingFormView(
            page, on_done=lambda: nav(self._parent(self.page.route))
        )
        self.form_modulo = ModuleFormView(
            page,
            on_created=lambda m: self.detalle.open_module(m),
            on_updated=lambda: nav(routes.MODULO),
            on_deleted=lambda: nav(routes.BASE),
        )
        # Pendientes de un módulo
        self.detalle = ModuleView(
            page,
            on_settings=self.form_modulo.show,
            on_open_item=lambda p: self.form_pendiente.show(p, routes.MODULO_PENDIENTE),
            on_new_item=lambda mid: self.form_pendiente.new(routes.MODULO_PENDIENTE, mid),
        )
        # Pantalla principal
        self.lista = RoadmapView(
            page,
            on_open_module=self.detalle.open_module,
            on_new_module=self.form_modulo.new,
            on_open_item=lambda p: self.form_pendiente.show(p, routes.PENDIENTE),
            on_new_item=lambda: self.form_pendiente.new(routes.PENDIENTE),
            on_open_inbox=lambda: nav(routes.CAPTURAS),
        )
        # Bandeja de capturas + botón flotante (vive en todas las pantallas)
        self.capturas = CapturesView(page, on_report=self.report)
        self.herramienta = CaptureTool(page, on_report=self.report,
                                       on_open_inbox=lambda: nav(routes.CAPTURAS))

    def report(self, capturas):  # propio
        """
        [Reportar]: pendiente nuevo con las capturas adjuntas y, si todas se
        tomaron en el mismo módulo, ese módulo ya elegido ('agenda' -> Agenda).
        """
        from modulos.desarrollo.capturas import slug
        from modulos.desarrollo.models import ModuloApp

        origenes = {c.origen for c in capturas if c.origen}
        modulo_id = None
        if len(origenes) == 1:
            origen = origenes.pop()
            modulo_id = next((m.id for m in ModuloApp.search_all() if slug(m.nombre) == origen),
                             None)
        self.form_pendiente.new(routes.PENDIENTE, modulo_id, capturas=capturas)

    async def on_start(self) -> None:  # propio
        """Al abrir la app: el botón flotante de captura, encima de todo."""
        self.herramienta.install()

    @staticmethod
    def _parent(route: str) -> str:  # propio
        """A dónde regresa la flecha (o el guardar) desde cada ruta."""
        return {
            routes.MODULO_DATOS: routes.MODULO,
            routes.MODULO_PENDIENTE: routes.MODULO,
            routes.MODULO: routes.BASE,
            routes.MODULO_NUEVO: routes.BASE,
            routes.PENDIENTE: routes.BASE,
            routes.CAPTURAS: routes.BASE,
        }.get(route, "/")

    def build_views(self, route: str) -> list[ft.View]:  # propio
        det = self.detalle

        # Las rutas de un módulo necesitan uno abierto (que siga existiendo)
        if route.startswith(routes.MODULO):
            det.load()
            if det.modulo is None:
                route = routes.BASE
                self.page.route = route

        vistas = [self.lista.vista]
        if route == routes.BASE:
            self.lista.load()  # cada vez que regresas, los números están al día
        elif route == routes.MODULO_NUEVO:
            vistas.append(self.form_modulo.vista)
        elif route == routes.PENDIENTE:
            vistas.append(self.form_pendiente.vista)
        elif route == routes.CAPTURAS:
            self.capturas.load()
            vistas.append(self.capturas.vista)
        elif route == routes.MODULO:
            vistas.append(det.vista)
        elif route == routes.MODULO_DATOS:
            vistas += [det.vista, self.form_modulo.vista]
        elif route == routes.MODULO_PENDIENTE:
            vistas += [det.vista, self.form_pendiente.vista]
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route in (routes.MODULO_NUEVO, routes.MODULO_DATOS):
            self.form_modulo.clear_form()
        elif route in (routes.PENDIENTE, routes.MODULO_PENDIENTE):
            self.form_pendiente.clear_form()
        self.page.navigate(self._parent(route))

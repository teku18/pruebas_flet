"""
Módulo Proyectos: proyectos personales, familiares o de trabajo con su
bitácora de avances (fecha, notas y adjuntos como evidencia).

Navegación (encima de la pantalla de inicio):
  /proyectos                    -> Proyectos
  /proyectos/proyecto           -> Proyectos > Nuevo proyecto
  /proyectos/bitacora           -> Proyectos > Bitácora del proyecto
  /proyectos/bitacora/proyecto  -> Proyectos > Bitácora > Datos del proyecto (engrane)
  /proyectos/entrada            -> Proyectos > Bitácora > Entrada
"""
import flet as ft

from core.module import AppModule
from modulos.proyectos import routes


class ProyectosModule(AppModule):
    nombre = "Proyectos"
    descripcion = "Bitácora de avances"
    icono = ft.Icons.FOLDER_SPECIAL
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.proyectos.views import LogView, ProjectsView

        # Proyectos --tocar-->  Bitácora.open_project
        # Bitácora  --engrane-> Proyectos.show
        self.bitacora = LogView(page, on_show_project=lambda p: self.proyectos.show(p))
        self.proyectos = ProjectsView(page, on_open_project=self.bitacora.open_project)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        bit, pro = self.bitacora, self.proyectos

        # Bitácora y entrada necesitan un proyecto abierto (que siga existiendo)
        if route.startswith(routes.BITACORA) or route == routes.ENTRADA:
            if bit.proyecto is not None:
                bit.load()
            if bit.proyecto is None:
                route = routes.BASE
                self.page.route = route

        vistas = [pro.vista_lista]
        if route == routes.BASE:
            pro.load()
        elif route == routes.PROYECTO:
            pro.vista_form.route = route
            vistas.append(pro.vista_form)
        elif route == routes.BITACORA:
            vistas.append(bit.vista_lista)
        elif route == routes.BITACORA_PROYECTO:
            pro.vista_form.route = route
            vistas += [bit.vista_lista, pro.vista_form]
        elif route == routes.ENTRADA:
            vistas += [bit.vista_lista, bit.vista_form]
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route == routes.ENTRADA:
            self.bitacora.clear_form()
            self.page.navigate(routes.BITACORA)
        elif route == routes.BITACORA_PROYECTO:
            self.proyectos.clear_form()
            self.page.navigate(routes.BITACORA)
        elif route == routes.PROYECTO:
            self.proyectos.clear_form()
            self.page.navigate(routes.BASE)
        elif route == routes.BITACORA:
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")

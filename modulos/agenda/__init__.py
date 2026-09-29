"""
Módulo Agenda: tareas (con o sin proyecto) y el "chismoso" del día.

Navegación (encima de la pantalla de inicio):
  /agenda        -> Agenda: pestañas [Hoy] (chismoso) y [Todas]
  /agenda/tarea  -> Agenda > Tarea (nueva, ver o editar)

Capas:
  models/     Tarea, Cumplimiento           (la despensa)
  services.py gossip, complete, next_date   (el cocinero)
  views/      AgendaView, TaskFormView      (el mesero)
"""
import flet as ft

from core.module import AppModule
from modulos.agenda import routes


class AgendaModule(AppModule):
    nombre = "Agenda"
    descripcion = "Pendientes y tareas"
    icono = ft.Icons.EVENT_NOTE
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.agenda.views import AgendaView, TaskFormView

        # Agenda --tocar tarea--> Formulario.show
        # Formulario --guardar--> Agenda.load (se refresca al regresar)
        self.formulario = TaskFormView(page, on_saved=lambda: self.agenda.load())
        self.agenda = AgendaView(
            page, on_open_task=self.formulario.show, on_new_task=self.formulario.new
        )

    def build_views(self, route: str) -> list[ft.View]:  # propio
        vistas = [self.agenda.vista]
        if route == routes.BASE:
            self.agenda.load()  # cada vez que entras, el chisme está al día
        elif route == routes.TAREA:
            vistas.append(self.formulario.vista)
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route == routes.TAREA:
            self.formulario.clear_form()
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")

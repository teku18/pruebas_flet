"""
Módulo Notas: notas rápidas y listas con casillas (súper, ideas, pendientes sueltos).

Navegación (encima de la pantalla de inicio):
  /notas         -> tablero: buscar, captura rápida, fijadas, etiquetas, archivadas
  /notas/editor  -> una nota (texto o lista); se guarda sola

Capas:
  models/       EtiquetaNota, Nota, NotaItem          (la despensa)
  services.py   buscar, crear, guardar, convertir     (el cocinero)
  views/        NotesBoard, NoteEditor                (el mesero)
  exportador.py todas las notas a Excel
"""
import flet as ft

from core.module import AppModule
from modulos.notas import routes


class NotasModule(AppModule):
    nombre = "Notas"
    descripcion = "Notas rápidas y listas"
    icono = ft.Icons.STICKY_NOTE_2
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.notas.views import NoteEditor, NotesBoard

        # Tablero --tocar--> Editor.open  ·  Editor --salir--> Tablero.load
        self.editor = NoteEditor(page, on_closed=lambda: self.tablero.load())
        self.tablero = NotesBoard(page, on_open=self.editor.open)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        vistas = [self.tablero.vista]
        if route == routes.EDITOR and self.editor.nota is not None:
            vistas.append(self.editor.vista)
        else:
            if route == routes.EDITOR:  # p. ej. se recargó la app: no hay nota abierta
                self.page.route = routes.BASE
            self.tablero.load()
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route == routes.EDITOR:
            self.editor.close()  # guarda y descarta si quedó vacía
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")

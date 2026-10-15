"""
Módulo Memorias: bitácora de MOMENTOS importantes (no es agenda ni pendientes).
"Fui al cine en mi aniversario", "el viaje a Oaxaca", "cuando salí de X".

Navegación (encima de la pantalla de inicio):
  /memorias          -> línea de tiempo (por año y mes) o galería de fotos,
                        con "Un día como hoy", búsqueda y filtros
  /memorias/memoria  -> una memoria: nueva, ver o editar

Capas:
  models/      Memoria, EtiquetaMemoria (fotos: core/adjuntos.py)   (la despensa)
  services.py  buscar, línea de tiempo, un día como hoy, guardar    (el cocinero)
  imagenes.py  copiar fotos: girar, reducir sin perder calidad, miniatura
  views/       MemoriesView, MemoryView                             (el mesero)

Pensado para la voz (después): Memoria.origen = "voz", el audio como adjunto
(mimetype audio/…) y el relato con la transcripción. No hace falta cambiar tablas.
"""
import flet as ft

from core.module import AppModule
from modulos.memorias import routes


class MemoriasModule(AppModule):
    nombre = "Memorias"
    descripcion = "Momentos importantes"
    icono = ft.Icons.AUTO_STORIES
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.memorias.views import MemoriesView, MemoryView

        # Línea de tiempo --tocar--> Memoria.show  ·  Memoria --guardar--> recarga
        self.memoria = MemoryView(page, on_saved=lambda: self.inicio.load())
        self.inicio = MemoriesView(page, on_open=self.memoria.show, on_new=self.memoria.new)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        vistas = [self.inicio.vista]
        if route == routes.MEMORIA:
            vistas.append(self.memoria.vista)
        else:
            self.inicio.load()
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route == routes.MEMORIA:
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")

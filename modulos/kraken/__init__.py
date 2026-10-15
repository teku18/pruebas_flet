"""
Módulo Kraken Tools: herramientas de desarrollador en tu bolsillo.

Navegación (encima de la pantalla de inicio):
  /kraken                   -> tarjetas de las herramientas
  /kraken/http              -> cliente HTTP: colecciones e historial
  /kraken/http/peticion     -> una petición y su respuesta
  /kraken/http/entornos     -> variables {{así}}
  /kraken/sqlite            -> bases .db (la de ControlKraken + las que agregues)
  /kraken/sqlite/base       -> una base: tablas, datos y SQL
  /kraken/red               -> Red: Mis equipos + pruebas
  /kraken/red/prueba        -> una prueba (ping, puertos, DNS…) y su resultado
  /kraken/red/historial     -> todas las pruebas de Red

Capas (cada herramienta en su carpeta, para sumar Red, SSH y Webhooks):
  models/          tablas kt_* (todo en la BD y en el respaldo)
  http/            services.py (httpx, variables, historial, cURL) + views/
  sqlite/          services.py (sqlite3, solo lectura, CSV) + views/
  red/             un archivo por prueba (ping.py, puertos.py…) + views/
  herramientas.py  las tarjetas del inicio
  comun.py         piezas de pantalla compartidas
"""
import flet as ft

from core.module import AppModule
from modulos.kraken import routes


class KrakenModule(AppModule):
    nombre = "Kraken Tools"
    descripcion = "HTTP, SQLite, red y más"
    icono = ft.Icons.HANDYMAN
    route = routes.BASE

    def __init__(self, page: ft.Page):
        super().__init__(page)
        from modulos.kraken.http.views import EnvironmentsView, HttpHome, RequestEditor
        from modulos.kraken.red.views import NetworkHistoryView, NetworkHome, TestView
        from modulos.kraken.sqlite.views import DatabaseView, DatabasesView
        from modulos.kraken.views import KrakenHome

        self.inicio = KrakenHome(page)
        # HTTP:  lista --tocar--> editor  ·  editor --salir--> lista.load
        self.editor = RequestEditor(page, on_closed=lambda: self.http.load())
        self.http = HttpHome(page, on_new=self.editor.open_new, on_open=self.editor.open_request,
                             on_open_history=self.editor.open_history)
        self.entornos = EnvironmentsView(page)
        # SQLite: bases --tocar--> una base
        self.base = DatabaseView(page)
        self.bases = DatabasesView(page, on_open=self.base.open)
        # Red: inicio --tarjeta/equipo--> prueba · historial --tocar--> prueba
        self.prueba = TestView(page)
        self.red = NetworkHome(page, on_test=self.prueba.open)
        self.red_historial = NetworkHistoryView(page, on_open=self._open_history)

    def _open_history(self, h):  # propio
        self.prueba.open(h.herramienta, h.objetivo if h.objetivo != "Este equipo" else "",
                         detalle=h.detalle, cuando=h.creado_en, desde_historial=True)

    def build_views(self, route: str) -> list[ft.View]:  # propio
        vistas = [self.inicio.vista]
        if route.startswith(routes.HTTP):
            vistas.append(self.http.vista)
            if route in (routes.PETICION, routes.ENTORNOS) and self.editor.activo:
                vistas.append(self.editor.vista)
            if route == routes.ENTORNOS:
                self.entornos.load()
                vistas.append(self.entornos.vista)
            elif route == routes.PETICION and self.editor.activo:
                self.editor.reload_environments()  # por si volviste de Entornos
            else:
                if route == routes.PETICION:  # se recargó la app: no hay petición abierta
                    self.page.route = routes.HTTP
                self.http.load()
        elif route.startswith(routes.RED):
            vistas.append(self.red.vista)
            if route == routes.RED_HISTORIAL or (route == routes.RED_PRUEBA
                                                 and self.prueba.desde_historial):
                self.red_historial.load()
                vistas.append(self.red_historial.vista)
            if route == routes.RED_PRUEBA:
                vistas.append(self.prueba.vista)
            elif route == routes.RED:
                self.red.load()
        elif route.startswith(routes.SQLITE):
            vistas.append(self.bases.vista)
            if route == routes.SQLITE_BASE and self.base.activa:
                vistas.append(self.base.vista)
            else:
                if route == routes.SQLITE_BASE:
                    self.page.route = routes.SQLITE
                self.bases.load()
        return vistas

    def go_back(self, route: str) -> None:  # propio
        if route == routes.PETICION:
            self.editor.close()
            self.page.navigate(routes.HTTP)
        elif route == routes.ENTORNOS:
            self.entornos.save()
            self.page.navigate(routes.PETICION if self.editor.activo else routes.HTTP)
        elif route == routes.SQLITE_BASE:
            self.base.close()
            self.page.navigate(routes.SQLITE)
        elif route == routes.RED_PRUEBA:
            if self.prueba.corriendo:  # salir corta la prueba (en el hilo de asyncio)
                self.page.run_task(self.prueba.cancel)
            self.page.navigate(routes.RED_HISTORIAL if self.prueba.desde_historial
                               else routes.RED)
        elif route == routes.RED_HISTORIAL:
            self.page.navigate(routes.RED)
        elif route in (routes.HTTP, routes.SQLITE, routes.RED):
            self.page.navigate(routes.BASE)
        else:
            self.page.navigate("/")

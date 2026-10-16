"""
Cliente HTTP (/kraken/http):

  Cliente HTTP     [{} entornos] [⚙] [⋮ nueva colección · importar cURL · importar de Postman]
  (Colecciones) (Historial 37)
  ▾ Mi API (3)                                           [⋮]
      GET   Usuarios          {{base}}/users
      POST  Crear usuario     {{base}}/users
  Sin colección
      GET   Clima             https://api…
                                                    [+ Nueva petición]

  Historial: 200 OK · GET · https://…  · 14:32:05 · 120 ms   (tocar = ver de nuevo)

Postman: "Importar de Postman" acepta colecciones (v2.1/v2.0) y entornos
(.json); el ⋮ de cada colección la exporta para abrirla en Postman.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
from datetime import date

import flet as ft

from core.ui import add_button, confirm, notify, service
from modulos.kraken import routes
from modulos.kraken.comun import ask_text, empty_state, method_badge, status_chip, tabs_row
from modulos.kraken.http import postman, services
from modulos.kraken.http.views.ajustes import settings_dialog
from modulos.kraken.models import Coleccion, HistorialHttp, Peticion


class HttpHome:
    def __init__(self, page: ft.Page, on_new, on_open, on_open_history):
        """
        on_new(coleccion_id=None, borrador=None) · on_open(peticion) ·
        on_open_history(historial): abren el editor.
        """
        self.page = page
        self.on_new = on_new
        self.on_open = on_open
        self.on_open_history = on_open_history
        self.pestana = "colecciones"
        self.abiertas: set[int] = set()   # colecciones desplegadas (se recuerdan al recargar)

        self.fila_pestanas = ft.Container()
        self.cuerpo = ft.ListView(expand=True, spacing=4, padding=ft.Padding.only(bottom=90))
        self.vista = ft.View(
            route=routes.HTTP,
            appbar=ft.AppBar(title=ft.Text("Cliente HTTP"), actions=[
                ft.IconButton(ft.Icons.DATA_OBJECT, tooltip="Entornos y variables",
                              on_click=lambda e: page.navigate(routes.ENTORNOS)),
                ft.IconButton(ft.Icons.SETTINGS, tooltip="Ajustes",
                              on_click=lambda e: settings_dialog(page, self.refresh)),
                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                    ft.PopupMenuItem(content=ft.Text("Nueva colección"),
                                     icon=ft.Icons.CREATE_NEW_FOLDER,
                                     on_click=lambda e: self.new_collection()),
                    ft.PopupMenuItem(content=ft.Text("Importar cURL…"), icon=ft.Icons.INPUT,
                                     on_click=lambda e: self.import_curl()),
                    ft.PopupMenuItem(content=ft.Text("Importar de Postman…"),
                                     icon=ft.Icons.FILE_OPEN,
                                     on_click=lambda e: page.run_task(self.import_postman)),
                ]),
            ]),
            floating_action_button=add_button("Nueva petición", lambda e: on_new()),
            controls=[ft.SafeArea(expand=True, content=ft.Column(
                expand=True, spacing=8, controls=[self.fila_pestanas, self.cuerpo]))],
        )

    # ==================================================================
    def load(self):  # propio
        n = len(services.history())
        self.fila_pestanas.content = tabs_row(
            [("colecciones", "Colecciones"), ("historial", f"Historial ({n})" if n else "Historial")],
            self.pestana, self.set_tab)
        self.cuerpo.controls = (self._history() if self.pestana == "historial"
                                else self._collections())

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def set_tab(self, pestana: str):  # propio
        self.pestana = pestana
        self.refresh()

    # ==================================================================
    # Colecciones
    # ==================================================================
    def _collections(self) -> list[ft.Control]:  # propio
        colecciones, sueltas = services.tree()
        if not colecciones and not sueltas:
            return [empty_state(ft.Icons.HTTP, "Tu primera petición",
                                "Toca + para probar una API, o pega un comando curl "
                                "(menú de tres puntos, Importar cURL). Guárdalas en "
                                "colecciones para reusarlas.")]
        controles: list[ft.Control] = [self._collection(c) for c in colecciones]
        if sueltas:
            controles.append(ft.Container(
                padding=ft.Padding.only(top=10, left=4),
                content=ft.Text("Sin colección", size=13, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.OUTLINE)))
            controles += [self._request_row(p) for p in sueltas]
        return controles

    def _collection(self, c: Coleccion) -> ft.Control:  # propio
        def toggle(e):  # propio
            (self.abiertas.add if e.data in (True, "true") else self.abiertas.discard)(c.id)

        n = len(c.peticiones)
        return ft.ExpansionTile(
            title=ft.Text(c.nombre, weight=ft.FontWeight.BOLD),
            subtitle=ft.Text(f"{n} petición" if n == 1 else f"{n} peticiones", size=12),
            leading=ft.Icon(ft.Icons.FOLDER, color=ft.Colors.ORANGE),
            expanded=c.id in self.abiertas, maintain_state=True, on_change=toggle,
            trailing=ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                ft.PopupMenuItem(content=ft.Text("Nueva petición aquí"), icon=ft.Icons.ADD,
                                 on_click=lambda e: self.on_new(coleccion_id=c.id)),
                ft.PopupMenuItem(content=ft.Text("Renombrar"), icon=ft.Icons.EDIT,
                                 on_click=lambda e: self.rename_collection(c)),
                ft.PopupMenuItem(content=ft.Text("Exportar a Postman"), icon=ft.Icons.IOS_SHARE,
                                 on_click=lambda e: self.page.run_task(self.export_postman, c)),
                ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                                 on_click=lambda e: self.delete_collection(c)),
            ]),
            controls=[self._request_row(p) for p in c.peticiones] or [
                ft.Text("Vacía: guarda una petición aquí.", italic=True, size=12,
                        color=ft.Colors.OUTLINE)],
        )

    def _request_row(self, p: Peticion) -> ft.Control:  # propio
        return ft.Container(
            ink=True, border_radius=8, padding=ft.Padding.only(left=12, top=4, bottom=4),
            on_click=lambda e: self.on_open(p),
            content=ft.Row(spacing=8, controls=[
                method_badge(p.metodo),
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(p.nombre, weight=ft.FontWeight.W_500, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(p.url or "(sin URL)", size=11, color=ft.Colors.OUTLINE, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ]),
                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                    ft.PopupMenuItem(content=ft.Text("Duplicar"), icon=ft.Icons.COPY,
                                     on_click=lambda e: self.duplicate(p)),
                    ft.PopupMenuItem(content=ft.Text("Mover a…"), icon=ft.Icons.DRIVE_FILE_MOVE,
                                     on_click=lambda e: self.move(p)),
                    ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                                     on_click=lambda e: self.delete_request(p)),
                ]),
            ]),
        )

    def new_collection(self):  # propio
        def ok(nombre):  # propio
            c = services.create_collection(nombre)
            self.abiertas.add(c.id)
            self.pestana = "colecciones"
            self.refresh()
        ask_text(self.page, "Nueva colección", ok, boton="Crear")

    def rename_collection(self, c: Coleccion):  # propio
        def ok(nombre):  # propio
            services.rename_collection(c.id, nombre)
            self.refresh()
        ask_text(self.page, "Renombrar colección", ok, valor=c.nombre)

    def delete_collection(self, c: Coleccion):  # propio
        n = len(c.peticiones)
        texto = (f"¿Eliminar «{c.nombre}» y sus {n} peticiones? Su historial se queda."
                 if n else f"¿Eliminar «{c.nombre}»?")

        def ok():  # propio
            Coleccion.delete(c.id)
            notify(self.page, "Colección eliminada")
            self.refresh()
        confirm(self.page, "Eliminar colección", texto, ok)

    def duplicate(self, p: Peticion):  # propio
        services.duplicate(p.id)
        if p.coleccion_id:
            self.abiertas.add(p.coleccion_id)
        notify(self.page, "Petición duplicada")
        self.refresh()

    def move(self, p: Peticion):  # propio
        def pick(coleccion_id):  # propio
            self.page.pop_dialog()
            Peticion.update(p.id, coleccion_id=coleccion_id)
            if coleccion_id:
                self.abiertas.add(coleccion_id)
            self.refresh()

        opciones = [(None, "Sin colección"), *((c.id, c.nombre) for c in Coleccion.search_all())]
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Mover a"),
            content=ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, controls=[
                ft.ListTile(title=ft.Text(nombre), selected=cid == p.coleccion_id,
                            leading=ft.Icon(ft.Icons.FOLDER_OPEN if cid else ft.Icons.INBOX),
                            on_click=lambda e, c=cid: pick(c))
                for cid, nombre in opciones]),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog())],
        ))

    def delete_request(self, p: Peticion):  # propio
        def ok():  # propio
            Peticion.delete(p.id)
            notify(self.page, "Petición eliminada")
            self.refresh()
        confirm(self.page, "Eliminar petición", f"¿Eliminar «{p.nombre}»?", ok)

    def import_curl(self):  # propio
        def ok(texto):  # propio
            self.on_new(borrador=services.parse_curl(texto))  # ValueError -> se queda abierto
        ask_text(self.page, "Importar cURL", ok, etiqueta="Pega aquí el comando curl",
                 boton="Importar", multilinea=True,
                 ayuda="Sirve el «Copy as cURL» de Chrome, Postman o la documentación de una API")

    async def import_postman(self):  # propio
        archivos = await service(self.page, ft.FilePicker).pick_files(
            dialog_title="Colección o entorno de Postman (.json)", allow_multiple=True,
            file_type=ft.FilePickerFileType.ANY,   # en Android .json no siempre tiene tipo
            with_data=True)
        if not archivos:
            return
        textos, avisos = [], []
        for f in archivos:
            try:
                datos = f.bytes
                if datos is None and f.path:
                    datos = await asyncio.to_thread(lambda p=f.path: open(p, "rb").read())
                r = await asyncio.to_thread(postman.import_file, datos or b"", f.name)
            except (ValueError, OSError) as ex:
                textos.append(f"{f.name}: {ex}")
                continue
            textos.append(r.summary())
            avisos += r.avisos
            for nombre in r.colecciones:
                encontradas = Coleccion.search(Coleccion.nombre == nombre)
                if encontradas:
                    self.abiertas.add(encontradas[0].id)
        self.pestana = "colecciones"
        self.refresh()
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Importar de Postman"),
            content=ft.Container(width=440, content=ft.Column(
                tight=True, spacing=8,
                scroll=ft.ScrollMode.AUTO if len(textos) + len(avisos) > 8 else None, controls=[
                    *[ft.Text(t) for t in textos],
                    *([ft.Text("Ojo:", weight=ft.FontWeight.BOLD)] if avisos else []),
                    *[ft.Text(f"- {a}", size=13, color=ft.Colors.OUTLINE) for a in avisos]])),
            actions=[ft.TextButton("Listo", on_click=lambda e: self.page.pop_dialog())],
        ))

    async def export_postman(self, c: Coleccion):  # propio
        try:
            nombre, datos = postman.export_collection(c.id)
        except ValueError as ex:
            notify(self.page, str(ex))
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Exportar a Postman", file_name=nombre,
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["json"], src_bytes=datos)
        if ruta or self.page.web:
            notify(self.page, "Listo: en Postman usa Import y elige este archivo")

    # ==================================================================
    # Historial
    # ==================================================================
    def _history(self) -> list[ft.Control]:  # propio
        envios = services.history()
        if not envios:
            return [empty_state(ft.Icons.HISTORY, "Sin envíos todavía",
                                "Cada petición que mandes queda aquí: lo que enviaste, lo que "
                                "regresó y cuánto tardó. Cuántos se guardan: en Ajustes (el engrane).")]
        return [self._history_row(h) for h in envios]

    def _history_row(self, h: HistorialHttp) -> ft.Control:  # propio
        cuando = (f"{h.creado_en:%H:%M:%S}" if h.creado_en.date() == date.today()
                  else f"{h.creado_en:%d/%m/%y %H:%M}")
        pie = f"{cuando} · {h.tiempo_ms or 0} ms"
        return ft.Container(
            ink=True, border_radius=8, padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            on_click=lambda e: self.on_open_history(h),
            content=ft.Row(spacing=8, controls=[
                method_badge(h.metodo),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(h.url, size=13, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row(spacing=8, controls=[
                        status_chip(h.status) if h.status is not None else
                        ft.Text("Sin respuesta", size=12, color=ft.Colors.RED),
                        ft.Text(pie, size=11, color=ft.Colors.OUTLINE)]),
                ]),
            ]),
        )

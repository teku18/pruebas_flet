"""
Explorador de bases (/kraken/sqlite): archivos SQLite y servidores PostgreSQL/MySQL.

  🔒 ControlKraken (esta app)       2.1 MB · Siempre en solo lectura
  🗄 tienda                         340 KB · Solo lectura · En respaldo   [⋮]
  🗄 odoo_pruebas                   48 MB  · Editable · Fuera del respaldo [⋮]
                                                          [+ Agregar base]

  🐘 Cliente ACME · Odoo   PostgreSQL · odoo@localhost:5432/produccion · por SSH: ACME [⋮]

⋮ de cada base: renombrar, permitir cambios / solo lectura, incluir o quitar
del respaldo, descargar copia, eliminar.

"Agregar base" COPIA el archivo dentro de la app (data/kraken/bases/): el
original no se toca, y en el celular la copia no depende de que el archivo
siga en Descargas. Los servidores no se copian: se consulta en vivo
(directo o por túnel SSH) y nunca entran al respaldo como datos, solo su conexión.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.storage import human_size
from core.ui import add_button, confirm, icon_box, notify, service
from modulos.kraken import routes
from modulos.kraken.comun import ask_text
from modulos.kraken.models import ConexionSqlite, Equipo
from modulos.kraken.sqlite import services
from modulos.kraken.sqlite.services import BaseInfo
from modulos.kraken.sqlite.views.servidor import NOMBRES, server_dialog


class DatabasesView:
    def __init__(self, page: ft.Page, on_open):
        self.page = page
        self.on_open = on_open
        self.lista = ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90))
        self.vista = ft.View(
            route=routes.SQLITE,
            appbar=ft.AppBar(title=ft.Text("Explorador de bases")),
            floating_action_button=add_button("Agregar base",
                                              lambda e: self.add_menu()),
            controls=[ft.SafeArea(expand=True, content=ft.Column(expand=True, controls=[
                ft.Text("Archivos SQLite (se copian a la app) o servidores PostgreSQL/MySQL.",
                        size=12, color=ft.Colors.OUTLINE),
                self.lista,
            ]))],
        )

    def load(self):  # propio
        self.lista.controls = [self._row(b) for b in services.databases()]

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _row(self, b: BaseInfo) -> ft.Control:  # propio
        if b.es_servidor:
            return self._server_row(b)
        if b.es_app:
            detalle = f"{human_size(b.tamano)} · Siempre en solo lectura"
        elif not b.existe:
            detalle = "Archivo no disponible en este equipo (estaba fuera del respaldo)"
        else:
            detalle = " · ".join([human_size(b.tamano),
                                  "Solo lectura" if b.solo_lectura else "Editable",
                                  "En respaldo" if b.respaldar else "Fuera del respaldo"])
        menu = None if b.es_app else ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
            ft.PopupMenuItem(content=ft.Text("Renombrar"), icon=ft.Icons.EDIT,
                             on_click=lambda e: self.rename(b)),
            self._read_only_item(b),
            ft.PopupMenuItem(
                content=ft.Text("Quitar del respaldo" if b.respaldar else "Incluir en el respaldo"),
                icon=ft.Icons.CLOUD_OFF if b.respaldar else ft.Icons.CLOUD_UPLOAD,
                on_click=lambda e: self.toggle_backup(b)),
            ft.PopupMenuItem(content=ft.Text("Descargar copia"), icon=ft.Icons.DOWNLOAD,
                             on_click=lambda e: self.page.run_task(self.download, b)),
            self._delete_item(b),
        ])
        return self._card(b, ft.Icons.LOCK if b.es_app else ft.Icons.STORAGE,
                          ft.Colors.BLUE if b.existe else ft.Colors.GREY, detalle, menu)

    def _server_row(self, b: BaseInfo) -> ft.Control:  # propio
        via = ""
        if b.ssh_equipo_id:
            equipo = Equipo.get(b.ssh_equipo_id)
            via = f" · por SSH: {equipo.nombre if equipo else '(servidor borrado)'}"
        detalle = (f"{NOMBRES[b.tipo]} · {b.destino}{via} · "
                   + ("Solo lectura" if b.solo_lectura else "Editable"))
        menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
            ft.PopupMenuItem(content=ft.Text("Editar conexión"), icon=ft.Icons.EDIT,
                             on_click=lambda e: server_dialog(self.page, b.tipo, self.refresh, b)),
            self._read_only_item(b),
            self._delete_item(b),
        ])
        return self._card(b, ft.Icons.DNS,
                          ft.Colors.INDIGO if b.tipo == "postgres" else ft.Colors.ORANGE,
                          detalle, menu)

    def _read_only_item(self, b: BaseInfo) -> ft.PopupMenuItem:  # propio
        return ft.PopupMenuItem(
            content=ft.Text("Volver a solo lectura" if not b.solo_lectura else "Permitir cambios"),
            icon=ft.Icons.LOCK if not b.solo_lectura else ft.Icons.LOCK_OPEN,
            on_click=lambda e: self.toggle_read_only(b))

    def _delete_item(self, b: BaseInfo) -> ft.PopupMenuItem:  # propio
        return ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                                on_click=lambda e: self.confirm_delete(b))

    def _card(self, b: BaseInfo, icono, color, detalle: str, menu) -> ft.Control:  # propio
        return ft.Card(content=ft.Container(
            padding=12, ink=b.existe, border_radius=12,
            on_click=(lambda e: self.on_open(b)) if b.existe else None,
            content=ft.Row(spacing=12, controls=[
                icon_box(icono, color),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(b.nombre, weight=ft.FontWeight.BOLD),
                    ft.Text(detalle, size=12, color=ft.Colors.OUTLINE)]),
                *([menu] if menu else []),
            ]),
        ))

    def add_menu(self):  # propio
        def opcion(icono, titulo, sub, accion):  # propio
            def click(e):  # propio
                self.page.pop_dialog()
                accion()
            return ft.ListTile(leading=ft.Icon(icono), title=ft.Text(titulo),
                               subtitle=ft.Text(sub, size=12), on_click=click)

        self.page.show_dialog(ft.BottomSheet(content=ft.Container(
            padding=ft.Padding.only(top=10, bottom=20), content=ft.Column(tight=True, controls=[
                opcion(ft.Icons.STORAGE, "Archivo SQLite", "Se copia a la app (.db, .sqlite)",
                       lambda: self.page.run_task(self.add)),
                opcion(ft.Icons.DNS, "Servidor PostgreSQL", "Directo o por túnel SSH",
                       lambda: server_dialog(self.page, "postgres", self.refresh)),
                opcion(ft.Icons.DNS, "Servidor MySQL / MariaDB", "Directo o por túnel SSH",
                       lambda: server_dialog(self.page, "mysql", self.refresh)),
            ]))))

    # ==================================================================
    async def add(self):  # propio
        archivos = await service(self.page, ft.FilePicker).pick_files(
            dialog_title="Elige una base SQLite (.db, .sqlite, .sqlite3)",
            file_type=ft.FilePickerFileType.ANY,  # en Android .db no tiene tipo propio
            with_data=True,  # en el celular llega el contenido, no una ruta útil
        )
        for f in archivos or []:
            try:
                if f.bytes is None and f.path:
                    c = await asyncio.to_thread(services.add_database, f.name, None, f.path)
                else:
                    c = await asyncio.to_thread(services.add_database, f.name, f.bytes)
            except (ValueError, OSError) as ex:
                notify(self.page, f"{f.name}: {ex}")
                continue
            notify(self.page, f"«{c.nombre}» agregada (solo lectura)")
        self.refresh()

    def rename(self, b: BaseInfo):  # propio
        def ok(nombre):  # propio
            ConexionSqlite.update(b.id, nombre=nombre[:80])
            self.refresh()
        ask_text(self.page, "Renombrar base", ok, valor=b.nombre)

    def toggle_read_only(self, b: BaseInfo):  # propio
        if not b.solo_lectura:
            ConexionSqlite.update(b.id, solo_lectura=True)
            notify(self.page, "Solo lectura")
            self.refresh()
            return

        def ok(e):  # propio
            self.page.pop_dialog()
            ConexionSqlite.update(b.id, solo_lectura=False)
            notify(self.page, "Ahora se puede editar")
            self.refresh()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Permitir cambios"),
            content=ft.Text(
                ("Podrás ejecutar INSERT, UPDATE, DELETE… DIRECTO en el servidor de «"
                 + b.nombre + "». Ojo: es la base real, no una copia. Antes de cada cambio "
                 "se te pedirá confirmar.") if b.es_servidor else
                ("Podrás ejecutar INSERT, UPDATE, DELETE… en la COPIA de "
                 "«" + b.nombre + "» que está en la app (el archivo original no se "
                 "toca). Antes de cada cambio se te pedirá confirmar.")),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Permitir", on_click=ok)],
        ))

    def toggle_backup(self, b: BaseInfo):  # propio
        ConexionSqlite.update(b.id, respaldar=not b.respaldar)
        notify(self.page, "Fuera del respaldo: no viaja en el zip, pero restaurar no la borra"
               if b.respaldar else "Entrará en el próximo respaldo")
        self.refresh()

    async def download(self, b: BaseInfo):  # propio
        try:
            datos = await asyncio.to_thread(services.file_bytes, b)
        except (ValueError, OSError) as ex:
            notify(self.page, str(ex))
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Guardar copia de la base", file_name=f"{b.nombre}.db",
            src_bytes=datos)
        if ruta or self.page.web:
            notify(self.page, "Copia guardada")

    def confirm_delete(self, b: BaseInfo):  # propio
        def ok():  # propio
            ConexionSqlite.delete(b.id)
            notify(self.page, "Base eliminada de la app")
            self.refresh()
        confirm(self.page, "Eliminar base",
                f"¿Quitar «{b.nombre}» de la app? Se borran sus consultas guardadas"
                + ("; el servidor no se toca." if b.es_servidor
                   else " y la copia; el archivo original no se toca."), ok)

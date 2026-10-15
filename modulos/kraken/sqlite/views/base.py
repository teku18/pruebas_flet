"""
Una base (/kraken/sqlite/base):

  ← tienda                                  🔒 Solo lectura
  (Tablas 3) (Datos) (SQL)

  Tablas:  ▦ clientes        120 filas   (tocar: columnas, llaves, índices)
           ▦ pedidos del mes  30 filas
           👁 grandes (vista)
  Datos:   [clientes ▾] [🔍 buscar…]
           id │ nombre    │ ciudad          <- desliza a los lados; toca una celda
           1  │ Cliente 1 │ CDMX               para verla completa
           ‹  51–100 de 120  ›
  SQL:     [ SELECT * FROM clientes …   ]
           [▶ Ejecutar] [★] [🕘 Guardadas]
           3 filas · 4 ms                 [⬇ CSV]

El SQL corre en otro hilo (asyncio.to_thread): una consulta pesada no congela
la pantalla. En una base editable, lo que no sea SELECT/PRAGMA pide confirmar.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import confirm, notify, service
from modulos.kraken import routes
from modulos.kraken.comun import MONO, ask_text, copy_text, tabs_row
from modulos.kraken.models import ConsultaSqlite
from modulos.kraken.sqlite import services
from modulos.kraken.sqlite.services import BaseInfo


class DatabaseView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.base: BaseInfo | None = None
        self.activa = False
        self.pestana = "tablas"
        self.tablas: list[services.Tabla] = []
        self.expandida: str | None = None    # tabla con el esquema abierto (pestaña Tablas)
        self.tabla: str | None = None        # tabla de la pestaña Datos
        self.pagina = 0
        self.buscar = ""
        self.resultado: services.ResultadoSql | None = None
        self.ejecutando = False

        self.titulo = ft.Text()
        self.lbl_modo = ft.Container()
        self.fila_pestanas = ft.Container()
        self.cuerpo = ft.Column(spacing=6)
        # Datos
        self.dd_tabla = ft.Dropdown(label="Tabla", dense=True, expand=True,
                                    on_select=self._on_table)
        self.txt_buscar = ft.TextField(hint_text="Buscar en todas las columnas", dense=True,
                                       prefix_icon=ft.Icons.SEARCH, expand=True,
                                       on_submit=self._on_search)
        # SQL
        self.txt_sql = ft.TextField(
            hint_text="SELECT * FROM tabla LIMIT 10", multiline=True, min_lines=4, expand=True,
            max_lines=14, text_style=ft.TextStyle(font_family=MONO, size=13))
        self.vista = ft.View(
            route=routes.SQLITE_BASE,
            appbar=ft.AppBar(title=self.titulo, actions=[self.lbl_modo]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=8, controls=[
                self.fila_pestanas, self.cuerpo, ft.Container(height=40)]))],
        )

    # ==================================================================
    def open(self, base: BaseInfo):  # propio
        if self.base is None or self.base.id != base.id or self.base.nombre != base.nombre:
            self.pestana, self.expandida, self.tabla = "tablas", None, None
            self.pagina, self.buscar, self.resultado = 0, "", None
            self.txt_sql.value = ""
            self.txt_buscar.value = ""
        self.base = base
        self.activa = True
        self.titulo.value = base.nombre
        modo = "Solo lectura" if (base.solo_lectura or base.es_app) else "Editable"
        color = ft.Colors.BLUE if modo == "Solo lectura" else ft.Colors.ORANGE
        self.lbl_modo.content = ft.Container(
            margin=ft.Margin.only(right=12),
            padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.15, color),
            content=ft.Row(tight=True, spacing=4, controls=[
                ft.Icon(ft.Icons.LOCK if modo == "Solo lectura" else ft.Icons.EDIT,
                        size=14, color=color),
                ft.Text(modo, size=12, color=color)]))
        try:
            self.tablas = services.tables(base)
        except Exception as ex:  # noqa: BLE001  (archivo dañado, etc.)
            self.tablas = []
            notify(self.page, f"No se pudo abrir: {ex}")
        self._render()
        self.page.navigate(routes.SQLITE_BASE)

    def close(self):  # propio
        self.activa = False

    def refresh(self):  # propio
        self._render()
        self.page.update()

    def set_tab(self, pestana: str):  # propio
        self.pestana = pestana
        self.refresh()

    def _render(self):  # propio
        self.fila_pestanas.content = tabs_row(
            [("tablas", f"Tablas ({len(self.tablas)})"), ("datos", "Datos"), ("sql", "SQL")],
            self.pestana, self.set_tab)
        if self.pestana == "datos":
            self.cuerpo.controls = self._data_tab()
        elif self.pestana == "sql":
            self.cuerpo.controls = self._sql_tab()
        else:
            self.cuerpo.controls = self._tables_tab()

    # ==================================================================
    # Tablas
    # ==================================================================
    def _tables_tab(self) -> list[ft.Control]:  # propio
        if not self.tablas:
            return [ft.Text("Esta base no tiene tablas.", italic=True, color=ft.Colors.OUTLINE)]
        controles = []
        for t in self.tablas:
            abierta = t.nombre == self.expandida
            filas = "?" if t.filas is None else f"{t.filas:,} fila{'s' if t.filas != 1 else ''}"
            controles.append(ft.Container(
                ink=True, border_radius=8, padding=ft.Padding.symmetric(horizontal=6, vertical=8),
                on_click=lambda e, n=t.nombre: self.toggle_schema(n),
                content=ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.VISIBILITY if t.tipo == "view" else ft.Icons.TABLE_CHART,
                            color=ft.Colors.BLUE, size=20),
                    ft.Text(t.nombre + (" (vista)" if t.tipo == "view" else ""),
                            expand=True, font_family=MONO, weight=ft.FontWeight.W_500),
                    ft.Text(filas, size=12, color=ft.Colors.OUTLINE),
                    ft.Icon(ft.Icons.EXPAND_LESS if abierta else ft.Icons.EXPAND_MORE, size=18),
                ])))
            if abierta:
                controles.append(self._schema(t))
        return controles

    def _schema(self, t: services.Tabla) -> ft.Control:  # propio
        try:
            e = services.schema(self.base, t.nombre)
        except Exception as ex:  # noqa: BLE001
            return ft.Text(str(ex), color=ft.Colors.RED)
        filas = []
        for c in e.columnas:
            marcas = []
            if c.llave:
                marcas.append("PK")
            if c.obligatoria:
                marcas.append("NOT NULL")
            if c.defecto is not None:
                marcas.append(f"= {c.defecto}")
            if c.apunta_a:
                marcas.append(f"FK {c.apunta_a}")
            filas.append(ft.Row(spacing=8, controls=[
                ft.Text(c.nombre, font_family=MONO, size=12, weight=ft.FontWeight.BOLD,
                        width=150, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(c.tipo or "—", font_family=MONO, size=12, color=ft.Colors.BLUE, width=90),
                ft.Text(" ".join(marcas), size=12, color=ft.Colors.OUTLINE, expand=True),
            ]))
        for nombre, unico, cols in e.indices:
            filas.append(ft.Text(f"{'Índice único' if unico else 'Índice'} {nombre} ({', '.join(cols)})",
                                 size=11, color=ft.Colors.OUTLINE))
        filas.append(ft.Row(wrap=True, spacing=0, controls=[
            ft.TextButton("Ver datos", icon=ft.Icons.GRID_ON,
                          on_click=lambda ev: self.show_data(t.nombre)),
            ft.TextButton("Consultar", icon=ft.Icons.CODE,
                          on_click=lambda ev: self.query_table(t.nombre)),
            ft.TextButton("Copiar CREATE", icon=ft.Icons.COPY,
                          on_click=lambda ev: self.page.run_task(copy_text, self.page, e.sql,
                                                                 "CREATE copiado")),
        ]))
        return ft.Container(
            margin=ft.Margin.only(left=30, bottom=6), padding=10, border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Column(spacing=4, controls=filas))

    def toggle_schema(self, nombre: str):  # propio
        self.expandida = None if self.expandida == nombre else nombre
        self.refresh()

    def show_data(self, tabla: str):  # propio
        self.tabla, self.pagina, self.buscar = tabla, 0, ""
        self.txt_buscar.value = ""
        self.set_tab("datos")

    def query_table(self, tabla: str):  # propio
        self.txt_sql.value = f'SELECT * FROM "{tabla}" LIMIT 100;'
        self.set_tab("sql")

    # ==================================================================
    # Datos
    # ==================================================================
    def _data_tab(self) -> list[ft.Control]:  # propio
        if not self.tablas:
            return [ft.Text("Esta base no tiene tablas.", italic=True, color=ft.Colors.OUTLINE)]
        if self.tabla not in {t.nombre for t in self.tablas}:
            self.tabla = self.tablas[0].nombre
        self.dd_tabla.options = [ft.DropdownOption(key=t.nombre, text=t.nombre)
                                 for t in self.tablas]
        self.dd_tabla.value = self.tabla
        try:
            columnas, filas, total = services.page_rows(self.base, self.tabla, self.pagina,
                                                        self.buscar)
        except Exception as ex:  # noqa: BLE001
            return [ft.Row([self.dd_tabla]), ft.Text(str(ex), color=ft.Colors.RED)]
        desde = self.pagina * services.POR_PAGINA
        hasta = desde + len(filas)
        def paginas() -> ft.Control:  # propio
            return ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=[
                ft.IconButton(ft.Icons.CHEVRON_LEFT, disabled=self.pagina == 0,
                              on_click=lambda e: self.go_page(-1)),
                ft.Text(f"{desde + 1 if filas else 0:,}–{hasta:,} de {total:,}"),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT, disabled=hasta >= total,
                              on_click=lambda e: self.go_page(1)),
            ])

        return [
            ft.Row([self.dd_tabla]),
            ft.Row([self.txt_buscar,
                    ft.IconButton(ft.Icons.CLEAR, tooltip="Quitar búsqueda",
                                  visible=bool(self.buscar), on_click=self._clear_search)]),
            paginas(),
            data_table(self.page, columnas, filas) if filas else
            ft.Text("Sin filas." if not self.buscar else "Nada coincide.", italic=True,
                    color=ft.Colors.OUTLINE),
            *([paginas()] if len(filas) > 15 else []),
        ]

    def _on_table(self, e):  # propio
        self.tabla, self.pagina, self.buscar = e.control.value, 0, ""
        self.txt_buscar.value = ""
        self.refresh()

    def _on_search(self, e):  # propio
        self.buscar, self.pagina = self.txt_buscar.value or "", 0
        self.refresh()

    def _clear_search(self, e):  # propio
        self.txt_buscar.value = ""
        self._on_search(e)

    def go_page(self, delta: int):  # propio
        self.pagina = max(0, self.pagina + delta)
        self.refresh()

    # ==================================================================
    # SQL
    # ==================================================================
    def _sql_tab(self) -> list[ft.Control]:  # propio
        botones = ft.Row(wrap=True, spacing=6, controls=[
            ft.FilledButton("Ejecutar", icon=ft.Icons.PLAY_ARROW, disabled=self.ejecutando,
                            on_click=lambda e: self.page.run_task(self.execute)),
            ft.IconButton(ft.Icons.STAR_BORDER, tooltip="Guardar como favorita",
                          on_click=lambda e: self.save_favorite()),
            ft.TextButton("Guardadas", icon=ft.Icons.HISTORY,
                          on_click=lambda e: self.show_saved()),
        ])
        controles: list[ft.Control] = [ft.Row([self.txt_sql]), botones]
        if self.ejecutando:
            controles.append(ft.ProgressBar())
        elif self.resultado is not None:
            controles += self._result(self.resultado)
        return controles

    def _result(self, r: services.ResultadoSql) -> list[ft.Control]:  # propio
        if r.error:
            return [ft.Container(
                padding=10, border_radius=8, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
                content=ft.Text(r.error, color=ft.Colors.RED, selectable=True))]
        if r.columnas:
            n = len(r.filas)
            resumen = f"{n:,} fila{'s' if n != 1 else ''}"
            if r.hay_mas:
                resumen = f"Primeras {n:,} filas (hay más: usa LIMIT/OFFSET)"
        else:
            resumen = f"Listo · {r.cambios:,} fila{'s' if r.cambios != 1 else ''} afectada" + \
                      ("s" if r.cambios != 1 else "")
        if r.sentencias > 1:
            resumen += f" · {r.sentencias} sentencias"
        cabecera = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Text(f"{resumen} · {r.tiempo_ms} ms", size=12, expand=True),
            ft.TextButton("CSV", icon=ft.Icons.DOWNLOAD, visible=bool(r.columnas),
                          on_click=lambda e: self.page.run_task(self.export_csv)),
        ])
        controles: list[ft.Control] = [cabecera]
        if r.columnas:
            controles.append(data_table(self.page, r.columnas, r.filas))
        return controles

    async def execute(self):  # propio
        sql = self.txt_sql.value or ""
        if not sql.strip():
            notify(self.page, "Escribe una consulta")
            return
        editable = not (self.base.solo_lectura or self.base.es_app)
        if editable and not services.is_read_only(sql):
            def ok():  # propio
                self.page.run_task(self._execute, sql)
            confirm(self.page, "¿Ejecutar cambios?",
                    f"Esto modifica la copia de «{self.base.nombre}» en la app. Si falla una "
                    "sentencia, no se aplica ninguna.", ok, boton="Ejecutar")
            return
        await self._execute(sql)

    async def _execute(self, sql: str):  # propio
        self.ejecutando = True
        self.refresh()
        try:
            self.resultado = await asyncio.to_thread(services.run, self.base, sql)
        finally:
            self.ejecutando = False
        if not self.resultado.error and not self.resultado.columnas:
            self.tablas = services.tables(self.base)  # pudo cambiar (CREATE/DROP/INSERT)
        self.refresh()

    async def export_csv(self):  # propio
        r = self.resultado
        if r is None or not r.columnas:
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Exportar resultado", file_name=f"{self.base.nombre}_consulta.csv",
            file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["csv"],
            src_bytes=services.to_csv(r.columnas, r.filas))
        if ruta or self.page.web:
            notify(self.page, "CSV exportado")

    def save_favorite(self):  # propio
        sql = self.txt_sql.value or ""

        def ok(nombre):  # propio
            services.save_favorite(self.base, nombre, sql)
            notify(self.page, "Consulta guardada")
        ask_text(self.page, "Guardar consulta", ok, etiqueta="Nombre (p. ej. Ventas por mes)")

    def show_saved(self):  # propio
        favoritas = services.favorites(self.base)
        recientes = services.history(self.base)[:30]

        def use(c: ConsultaSqlite):  # propio
            self.page.pop_dialog()
            self.txt_sql.value = c.sql
            self.txt_sql.update()

        def remove(c: ConsultaSqlite):  # propio
            ConsultaSqlite.delete(c.id)
            self.page.pop_dialog()
            self.show_saved()

        def row(c: ConsultaSqlite, favorita: bool) -> ft.Control:  # propio
            return ft.ListTile(
                dense=True, on_click=lambda e: use(c),
                leading=ft.Icon(ft.Icons.STAR if favorita else
                                (ft.Icons.ERROR_OUTLINE if c.error else ft.Icons.HISTORY),
                                color=ft.Colors.AMBER if favorita else
                                (ft.Colors.RED if c.error else None)),
                title=ft.Text(c.nombre if favorita else c.sql, max_lines=2,
                              overflow=ft.TextOverflow.ELLIPSIS,
                              font_family=None if favorita else MONO, size=13),
                subtitle=ft.Text(c.sql if favorita else f"{c.creado_en:%d/%m %H:%M}",
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, size=11),
                trailing=ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, tooltip="Quitar",
                                       on_click=lambda e: remove(c)),
            )

        controles: list[ft.Control] = []
        if favoritas:
            controles.append(ft.Text("Favoritas", weight=ft.FontWeight.BOLD))
            controles += [row(c, True) for c in favoritas]
        controles.append(ft.Text("Recientes", weight=ft.FontWeight.BOLD))
        controles += [row(c, False) for c in recientes] or [
            ft.Text("Aún no ejecutas nada en esta base.", italic=True, color=ft.Colors.OUTLINE)]
        self.page.show_dialog(ft.BottomSheet(
            show_drag_handle=True, scrollable=True,
            content=ft.Container(padding=ft.Padding.only(left=16, right=16, bottom=24),
                                 content=ft.Column(tight=True, spacing=2,
                                                   scroll=ft.ScrollMode.AUTO, controls=controles)),
        ))


def data_table(page: ft.Page, columnas: list[str], filas: list[tuple]) -> ft.Control:  # propio
    """Tabla que se desliza a los lados; tocar una celda la muestra completa."""
    def cell(valor) -> ft.DataCell:  # propio
        nulo = valor is None
        return ft.DataCell(
            ft.Text(services.cell_text(valor), size=12, font_family=MONO, italic=nulo,
                    color=ft.Colors.OUTLINE if nulo or isinstance(valor, bytes) else None),
            on_tap=lambda e, v=valor: show_value(page, v))

    tabla = ft.DataTable(
        column_spacing=18, heading_row_height=36, data_row_min_height=32,
        data_row_max_height=40, horizontal_margin=8,
        heading_text_style=ft.TextStyle(weight=ft.FontWeight.BOLD, size=12, font_family=MONO),
        columns=[ft.DataColumn(ft.Text(c)) for c in columnas],
        rows=[ft.DataRow(cells=[cell(v) for v in fila]) for fila in filas],
    )
    return ft.Row(scroll=ft.ScrollMode.AUTO, controls=[tabla])


def show_value(page: ft.Page, valor):  # propio
    if valor is None:
        texto = "NULL"
    elif isinstance(valor, bytes):
        texto = f"BLOB de {len(valor):,} bytes\n\n{valor[:256].hex(' ')}" + (
            " …" if len(valor) > 256 else "")
    else:
        texto = str(valor)
    page.show_dialog(ft.AlertDialog(
        content=ft.Container(width=520, content=ft.Column(tight=True, scroll=ft.ScrollMode.AUTO,
                                                          controls=[ft.Text(texto, selectable=True,
                                                                            font_family=MONO)])),
        actions=[ft.TextButton("Copiar", on_click=lambda e: page.run_task(copy_text, page, texto)),
                 ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))

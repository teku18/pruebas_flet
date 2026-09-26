"""
Pantallas de la Bitácora de un proyecto:
  /proyectos/bitacora -> entradas del proyecto abierto (la más reciente arriba)
  /proyectos/entrada  -> una entrada: nuevo, ver o editar, con sus adjuntos

Adjuntos: se eligen con FilePicker, se copian a data/adjuntos/<proyecto>/<entrada>/
y la BD guarda solo la ruta. Mientras editas, los cambios de adjuntos quedan
"pendientes" y se aplican al guardar (Cancelar los descarta).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date, datetime
from pathlib import Path

import flet as ft

from core.storage import absolute_path, human_size, save_file
from core.ui import (
    DateField,
    add_button,
    confirm,
    delete_button,
    edit_button,
    notify,
    short_date,
    swipe_to_delete,
)
from modulos.proyectos import routes
from modulos.proyectos.models import ADJUNTOS_DIR, Adjunto, Entrada, Proyecto

EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp"}


def attachment_icon(nombre: str):  # propio
    """Ícono según la extensión del archivo."""
    ext = Path(nombre).suffix.lower()
    if ext in EXT_IMAGEN:
        return ft.Icons.IMAGE
    if ext == ".pdf":
        return ft.Icons.PICTURE_AS_PDF
    return ft.Icons.INSERT_DRIVE_FILE


class LogView:
    def __init__(self, page: ft.Page, on_show_project):
        """on_show_project: función del engrane (muestra los datos del proyecto)."""
        self.page = page
        self.on_show_project = on_show_project
        self.proyecto: Proyecto | None = None  # proyecto abierto
        self.registro: Entrada | None = None   # entrada mostrada en el formulario
        self.modo = "nuevo"

        # Adjuntos del formulario: lista de dicts
        #   {"id": int|None, "nombre", "tamano", "ruta": str|None,
        #    "origen": str|None, "datos": bytes|None}
        # id=None -> todavía no se guarda (pendiente)
        self.adjuntos: list[dict] = []
        self.adjuntos_borrar: list[int] = []  # ids a borrar al guardar

        # Servicios de Flet (no se ven en pantalla)
        self.picker = ft.FilePicker()
        self.launcher = ft.UrlLauncher()

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista de entradas
    # ==================================================================
    def _build_list(self):  # propio
        self.lista = ft.ListView(expand=True, spacing=8, padding=ft.Padding.only(bottom=90))
        self.lbl_vacio = ft.Text(
            "Sin entradas. Registra el primer avance con el botón +.", italic=True
        )
        self.lbl_titulo_lista = ft.Text("Bitácora")

        self.vista_lista = ft.View(
            route=routes.BITACORA,
            appbar=ft.AppBar(
                title=self.lbl_titulo_lista,
                actions=[
                    ft.IconButton(
                        ft.Icons.SETTINGS,
                        tooltip="Datos del proyecto",
                        on_click=lambda e: self.on_show_project(self.proyecto),
                    )
                ],
            ),
            floating_action_button=add_button("Nueva entrada", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_vacio, self.lista]),
                )
            ],
        )

    def open_project(self, proyecto: Proyecto):  # propio
        """Lo llama la lista de proyectos al tocar uno."""
        self.proyecto = proyecto
        self.page.navigate(routes.BITACORA)

    def load(self):  # propio
        self.proyecto = Proyecto.get(self.proyecto.id)  # por si se editó o eliminó
        if self.proyecto is None:
            return
        self.lbl_titulo_lista.value = self.proyecto.nombre
        entradas = Entrada.search_by_project(self.proyecto.id)
        self.lista.controls = [self._row(en) for en in entradas]
        self.lbl_vacio.visible = not entradas

    def _row(self, en: Entrada) -> ft.Control:  # propio
        """Tarjeta de una entrada: fecha y hora, notas (3 líneas) y adjuntos."""
        pie = []
        if en.adjuntos:
            n = len(en.adjuntos)
            pie = [
                ft.Row(
                    spacing=4,
                    controls=[
                        ft.Icon(ft.Icons.ATTACH_FILE, size=16, color=ft.Colors.PRIMARY),
                        ft.Text(
                            "1 adjunto" if n == 1 else f"{n} adjuntos",
                            size=12,
                            color=ft.Colors.PRIMARY,
                        ),
                    ],
                )
            ]

        tarjeta = ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ink=True,
            on_click=lambda e, x=en: self.show(x),
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        spacing=4,
                        controls=[
                            ft.Icon(ft.Icons.SCHEDULE, size=14, color=ft.Colors.OUTLINE),
                            ft.Text(
                                f"{short_date(en.fecha_hora.date())} · "
                                f"{en.fecha_hora:%H:%M}",
                                size=12,
                                color=ft.Colors.OUTLINE,
                            ),
                        ],
                    ),
                    ft.Text(en.notas, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    *pie,
                ],
            ),
        )
        return swipe_to_delete(
            self.page,
            key=f"entrada-{en.id}",
            contenido=tarjeta,
            titulo="Eliminar entrada",
            mensaje=self._delete_message(en),
            on_delete=lambda x=en: self._delete(x),
        )

    # ==================================================================
    # Formulario de entrada
    # ==================================================================
    def _build_form(self):  # propio
        self.campo_fecha = DateField(self.page, "Fecha")
        self.txt_notas = ft.TextField(
            label="Notas del avance", multiline=True, min_lines=4, max_lines=12, expand=True
        )

        self.btn_adjuntar = ft.OutlinedButton(
            "Adjuntar", icon=ft.Icons.ATTACH_FILE, on_click=self.pick_files
        )
        self.col_adjuntos = ft.Column(spacing=4)
        self.lbl_sin_adjuntos = ft.Text("Sin adjuntos", italic=True, size=12)

        self.lbl_titulo_form = ft.Text("Nueva entrada")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.ENTRADA,
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.campo_fecha.fila,
                            # Dentro de un Row con expand=True ocupa todo el ancho
                            ft.Row([self.txt_notas]),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Adjuntos", size=16, weight=ft.FontWeight.BOLD),
                                    self.btn_adjuntar,
                                ],
                            ),
                            self.lbl_sin_adjuntos,
                            self.col_adjuntos,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _apply_mode(self):  # propio
        lectura = self.modo == "ver"
        self.txt_notas.read_only = lectura
        self.campo_fecha.set_enabled(not lectura)
        self.btn_adjuntar.visible = not lectura

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nueva entrada"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Entrada"
        else:
            self.lbl_titulo_form.value = "Editar entrada"
            self.btn_guardar.content = "Actualizar"
        self._render_attachments()

    # --- Adjuntos en pantalla -------------------------------------------
    def _render_attachments(self):  # propio
        editable = self.modo != "ver"
        self.col_adjuntos.controls = [
            self._attachment_row(i, adj, editable) for i, adj in enumerate(self.adjuntos)
        ]
        self.lbl_sin_adjuntos.visible = not self.adjuntos

    def _attachment_row(self, indice: int, adj: dict, editable: bool) -> ft.Control:  # propio
        detalle = human_size(adj["tamano"])
        if adj["id"] is None:
            detalle += " · se guarda al dar Guardar"
        acciones = []
        if editable:
            acciones.append(
                ft.IconButton(
                    ft.Icons.CLOSE,
                    tooltip="Quitar",
                    on_click=lambda e, i=indice: self.remove_attachment(i),
                )
            )
        elif adj["ruta"]:
            acciones.append(
                ft.IconButton(
                    ft.Icons.OPEN_IN_NEW,
                    tooltip="Abrir",
                    on_click=lambda e, r=adj["ruta"]: self.page.run_task(
                        self.open_attachment, r
                    ),
                )
            )
        return ft.Container(
            padding=ft.Padding.only(left=8),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            content=ft.Row(
                controls=[
                    ft.Icon(attachment_icon(adj["nombre"]), color=ft.Colors.PRIMARY),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(
                                adj["nombre"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS
                            ),
                            ft.Text(detalle, size=11, color=ft.Colors.OUTLINE),
                        ],
                    ),
                    *acciones,
                ],
            ),
        )

    async def pick_files(self, e=None):  # propio
        """Botón Adjuntar: abre el selector de archivos del sistema."""
        archivos = await self.picker.pick_files(
            dialog_title="Elige la evidencia", allow_multiple=True
        )
        for f in archivos or []:
            self.adjuntos.append(
                {"id": None, "nombre": f.name, "tamano": f.size, "ruta": None,
                 "origen": f.path, "datos": f.bytes}
            )
        self._render_attachments()
        self.page.update()

    def remove_attachment(self, indice: int):  # propio
        adj = self.adjuntos.pop(indice)
        if adj["id"] is not None:
            self.adjuntos_borrar.append(adj["id"])  # se borra de verdad al guardar
        self._render_attachments()
        self.page.update()

    async def open_attachment(self, ruta: str):  # propio
        """Abre el archivo con la aplicación predeterminada del sistema."""
        archivo = absolute_path(ruta)
        if not archivo.exists():
            notify(self.page, "No se encontró el archivo")
            return
        await self.launcher.launch_url(archivo.as_uri())

    # --- Llenar / limpiar -------------------------------------------------
    def _fill(self, en: Entrada):  # propio
        self.campo_fecha.set_value(en.fecha_hora.date())
        self.txt_notas.value = en.notas
        self.adjuntos = [
            {"id": a.id, "nombre": a.nombre, "tamano": a.tamano, "ruta": a.ruta,
             "origen": None, "datos": None}
            for a in en.adjuntos
        ]
        self.adjuntos_borrar = []

    def clear_errors(self):  # propio
        self.txt_notas.error_text = None

    def clear_form(self):  # propio
        self.clear_errors()
        self.campo_fecha.set_value(date.today())
        self.txt_notas.value = ""
        self.adjuntos = []
        self.adjuntos_borrar = []
        self.registro = None
        self.modo = "nuevo"
        self._apply_mode()

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        self.clear_form()
        self.page.navigate(routes.ENTRADA)

    def show(self, en: Entrada):  # propio
        self.clear_errors()
        self.registro = Entrada.get_with_attachments(en.id)
        self._fill(self.registro)
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.ENTRADA)

    def edit(self, e=None):  # propio
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            # Descarta cambios, incluidos los adjuntos pendientes
            self.registro = Entrada.get_with_attachments(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(routes.BITACORA)

    def _entry_datetime(self) -> datetime:  # propio
        """Fecha elegida + hora: la actual si es nueva, la original si se edita."""
        hora = self.registro.fecha_hora.time() if self.registro else datetime.now().time()
        return datetime.combine(self.campo_fecha.valor, hora.replace(microsecond=0))

    def save(self, e=None):  # propio
        self.clear_errors()
        notas = (self.txt_notas.value or "").strip()
        if not notas:
            self.txt_notas.error_text = "Escribe qué avanzaste"
            self.page.update()
            return

        valores = dict(
            proyecto_id=self.proyecto.id, fecha_hora=self._entry_datetime(), notas=notas
        )
        try:
            if self.modo == "nuevo":
                entrada = Entrada.create(**valores)
            else:
                entrada = Entrada.update(self.registro.id, **valores)
            self._apply_attachment_changes(entrada.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Entrada guardada")
            self.page.navigate(routes.BITACORA)
        else:
            self.registro = Entrada.get_with_attachments(entrada.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Entrada actualizada")
            self.page.update()

    def _apply_attachment_changes(self, entrada_id: int):  # propio
        """Guarda los adjuntos pendientes y borra los que se quitaron."""
        for adjunto_id in self.adjuntos_borrar:
            Adjunto.delete(adjunto_id)
        self.adjuntos_borrar = []

        carpeta = ADJUNTOS_DIR / str(self.proyecto.id) / str(entrada_id)
        for adj in self.adjuntos:
            if adj["id"] is not None:
                continue
            ruta = save_file(
                Path(adj["origen"]) if adj["origen"] else None,
                adj["datos"],
                carpeta,
                adj["nombre"],
            )
            Adjunto.create(
                entrada_id=entrada_id,
                nombre=adj["nombre"],
                ruta=ruta.as_posix(),
                tamano=adj["tamano"],
            )

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, en: Entrada) -> str:  # propio
        mensaje = f"¿Eliminar la entrada del {short_date(en.fecha_hora.date())}?"
        if en.adjuntos:
            mensaje += f"\n\nTambién se borrarán sus {len(en.adjuntos)} adjunto(s)."
        return mensaje

    def confirm_delete(self, e=None):  # propio
        en = self.registro

        def delete():  # propio
            if self._delete(en):
                self.clear_form()
                self.page.navigate(routes.BITACORA)

        confirm(self.page, "Eliminar entrada", self._delete_message(en), delete)

    def _delete(self, en: Entrada) -> bool:  # propio
        try:
            Entrada.delete(en.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Entrada eliminada")
        self.page.update()
        return True

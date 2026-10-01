"""
Pantalla principal de Desarrollo (/desarrollo), con dos pestañas:

  [Módulos]     cada módulo de la app: prioridad, % de avance y cuántos
                pendientes tiene (y cuántos son de prioridad alta)
  [Pendientes]  TODOS los pendientes abiertos de la app, agrupados
                Alta → Media → Baja  (lo que sigue por hacer, de un vistazo)

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, icon_box, notify, service, swipe_to_delete
from modulos.desarrollo import services
from modulos.desarrollo.models import ModuloApp
from modulos.desarrollo.routes import BASE
from modulos.desarrollo.views.comun import COLOR_PRIORIDAD, grouped_rows


class RoadmapView:
    def __init__(self, page: ft.Page, on_open_module, on_new_module, on_open_item, on_new_item,
                 on_open_inbox):
        """
        on_open_module(modulo): abre los pendientes de un módulo
        on_new_module():        alta de módulo
        on_open_item(p):        formulario de un pendiente
        on_new_item():          pendiente nuevo (eliges el módulo en el form)
        on_open_inbox():        pantalla "Mis capturas"
        """
        self.page = page
        self.on_open_module = on_open_module
        self.on_open_item = on_open_item
        self.pestana = "modulos"  # "modulos" | "pendientes"

        self.fab_modulo = add_button("Nuevo módulo", lambda e: on_new_module())
        self.fab_pendiente = add_button("Nuevo pendiente", lambda e: on_new_item())

        self.fila_pestanas = ft.Row(spacing=6)
        self.lista = ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90))
        self.vista = ft.View(
            route=BASE,
            appbar=ft.AppBar(
                title=ft.Text("Desarrollo"),
                actions=[
                    ft.IconButton(ft.Icons.PHOTO_LIBRARY, tooltip="Mis capturas",
                                  on_click=lambda e: on_open_inbox()),
                    ft.IconButton(ft.Icons.TABLE_VIEW, tooltip="Exportar a Excel",
                                  on_click=lambda e: self.page.run_task(self.export_excel)),
                ],
            ),
            floating_action_button=self.fab_modulo,
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.fila_pestanas, self.lista]),
                )
            ],
        )
        self._build_tabs()

    # ==================================================================
    # Pestañas
    # ==================================================================
    def _build_tabs(self):  # propio
        self.fila_pestanas.controls = [
            ft.Chip(
                label=ft.Text(texto),
                selected=self.pestana == clave,
                on_select=lambda e, c=clave: self.set_tab(c),
            )
            for clave, texto in (("modulos", "Módulos"), ("pendientes", "Pendientes"))
        ]
        self.vista.floating_action_button = (
            self.fab_modulo if self.pestana == "modulos" else self.fab_pendiente
        )

    def set_tab(self, pestana: str):  # propio
        self.pestana = pestana
        self._build_tabs()
        self.refresh()

    def load(self):  # propio
        if self.pestana == "modulos":
            self.lista.controls = self._module_controls()
        else:
            self.lista.controls = self._pending_controls()

    def refresh(self):  # propio
        self.load()
        self.page.update()

    async def export_excel(self):  # propio
        """Excel con una hoja Resumen + una hoja por módulo con sus pendientes."""
        from modulos.desarrollo.exportador import export_all, export_file_name

        try:
            contenido = export_all()
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo generar el Excel: {ex}")
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Guardar reporte de Desarrollo",
            file_name=export_file_name(),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
            src_bytes=contenido,  # Flet escribe el archivo (escritorio, web y celular)
        )
        if ruta or self.page.web:
            notify(self.page, "Excel exportado")

    # ==================================================================
    # [Módulos]
    # ==================================================================
    def _module_controls(self) -> list[ft.Control]:  # propio
        datos = services.overview()
        if not datos:
            return [ft.Text("Aún no hay módulos. Crea uno con el botón +.", italic=True)]
        return [self._module_row(m, r) for m, r in datos]

    def _module_row(self, m: ModuloApp, r: services.ModuleSummary) -> ft.Control:  # propio
        color = COLOR_PRIORIDAD.get(m.prioridad, ft.Colors.GREY)
        if r.pendientes:
            pie = "1 pendiente" if r.pendientes == 1 else f"{r.pendientes} pendientes"
            if r.altas:
                pie += f" · {r.altas} alta{'s' if r.altas > 1 else ''}"
        else:
            pie = "Sin pendientes"

        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,
            on_click=lambda e, x=m: self.on_open_module(x),
            content=ft.Row(
                spacing=10,
                controls=[
                    icon_box(ft.Icons.WIDGETS, color),
                    ft.Column(
                        expand=True,
                        spacing=2,
                        controls=[
                            ft.Row([
                                ft.Text(m.nombre, size=16, weight=ft.FontWeight.W_500,
                                        expand=True),
                                ft.Text(f"{m.avance}%", weight=ft.FontWeight.BOLD),
                            ]),
                            ft.ProgressBar(value=m.avance / 100, bar_height=6,
                                           border_radius=3),
                            ft.Text(
                                f"Prioridad {m.prioridad_label.lower()} · {pie}",
                                size=12,
                                color=ft.Colors.RED if r.altas else ft.Colors.OUTLINE,
                            ),
                        ],
                    ),
                ],
            ),
        )
        mensaje = f"¿Eliminar el módulo «{m.nombre}»?"
        total = r.pendientes + r.hechos
        if total:
            mensaje += f"\n\nTambién se eliminan sus {total} pendiente(s)."
        return swipe_to_delete(
            self.page,
            key=f"dev-modulo-{m.id}",
            contenido=linea,
            titulo="Eliminar módulo",
            mensaje=mensaje,
            on_delete=lambda x=m: self._delete(x),
        )

    def _delete(self, m: ModuloApp):  # propio
        try:
            ModuloApp.delete(m.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return
        notify(self.page, "Módulo eliminado")
        self.refresh()

    # ==================================================================
    # [Pendientes]  todo lo abierto, alta primero
    # ==================================================================
    def _pending_controls(self) -> list[ft.Control]:  # propio
        pendientes = services.pending_by_priority()
        if not pendientes:
            return [
                ft.Container(
                    padding=ft.Padding.only(top=60),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=64, color=ft.Colors.GREEN),
                            ft.Text("Nada pendiente", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text("Agrega tareas, errores o comentarios con el +.",
                                    color=ft.Colors.OUTLINE),
                        ],
                    ),
                )
            ]
        return grouped_rows(self.page, pendientes, self.on_open_item, self.refresh,
                            mostrar_modulo=True)

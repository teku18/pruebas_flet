"""
Pantallas de un módulo de la app:
  /desarrollo/modulo        -> ModuleView: sus pendientes [Pendientes] [Hechos]
  /desarrollo/nuevo         -> ModuleFormView (alta)
  /desarrollo/modulo/datos  -> ModuleFormView (engrane: editar / eliminar)

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, confirm, delete_button, dropdown_options, notify
from modulos.desarrollo import routes, services
from modulos.desarrollo.models import PRIORIDAD_SELECTION, ModuloApp
from modulos.desarrollo.views.comun import COLOR_PRIORIDAD, grouped_rows, item_row


# ============================================================================
# Pendientes de un módulo
# ============================================================================
class ModuleView:
    def __init__(self, page: ft.Page, on_settings, on_open_item, on_new_item):
        """
        on_settings(modulo):   engrane -> datos del módulo
        on_open_item(p):       formulario de un pendiente
        on_new_item(modulo_id) pendiente nuevo ya con este módulo
        """
        self.page = page
        self.on_open_item = on_open_item
        self.modulo: ModuloApp | None = None
        self.ver_hechos = False

        self.lbl_titulo = ft.Text("Módulo")
        self.lbl_descripcion = ft.Text(size=13, color=ft.Colors.OUTLINE)
        self.lbl_avance = ft.Text(weight=ft.FontWeight.BOLD)
        self.barra = ft.ProgressBar(value=0, bar_height=8, border_radius=4)
        self.lbl_prioridad = ft.Text(size=12)
        self.fila_pestanas = ft.Row(spacing=6)
        self.lista = ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90))

        self.vista = ft.View(
            route=routes.MODULO,
            appbar=ft.AppBar(
                title=self.lbl_titulo,
                actions=[
                    ft.IconButton(ft.Icons.SETTINGS, tooltip="Datos del módulo",
                                  on_click=lambda e: on_settings(self.modulo)),
                ],
            ),
            floating_action_button=add_button(
                "Nuevo pendiente", lambda e: on_new_item(self.modulo.id)
            ),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        controls=[
                            self.lbl_descripcion,
                            ft.Row([ft.Container(self.barra, expand=True), self.lbl_avance]),
                            self.lbl_prioridad,
                            self.fila_pestanas,
                            self.lista,
                        ],
                    ),
                )
            ],
        )

    def open_module(self, m: ModuloApp):  # propio
        self.modulo = m
        self.ver_hechos = False
        self.page.navigate(routes.MODULO)

    def set_tab(self, hechos: bool):  # propio
        self.ver_hechos = hechos
        self.refresh()

    def load(self):  # propio
        """Relee el módulo (pudo cambiar en el engrane o ya no existir)."""
        if self.modulo is None:
            return
        self.modulo = ModuloApp.get(self.modulo.id)
        if self.modulo is None:
            return
        m = self.modulo
        resumen = services.module_summary(m.id)

        self.lbl_titulo.value = m.nombre
        self.lbl_descripcion.value = m.descripcion or ""
        self.lbl_descripcion.visible = bool(m.descripcion)
        self.barra.value = m.avance / 100
        self.lbl_avance.value = f"{m.avance}%"
        self.lbl_prioridad.value = f"Prioridad {m.prioridad_label.lower()}"
        self.lbl_prioridad.color = COLOR_PRIORIDAD.get(m.prioridad)

        self.fila_pestanas.controls = [
            ft.Chip(
                label=ft.Text(texto),
                selected=self.ver_hechos == hechos,
                on_select=lambda e, h=hechos: self.set_tab(h),
            )
            for hechos, texto in (
                (False, f"Pendientes ({resumen.pendientes})"),
                (True, f"Hechos ({resumen.hechos})"),
            )
        ]

        items = services.module_items(m.id, hechos=self.ver_hechos)
        if not items:
            vacio = "Nada hecho todavía." if self.ver_hechos else "Sin pendientes. Agrega uno con el +."
            self.lista.controls = [ft.Text(vacio, italic=True)]
        elif self.ver_hechos:
            self.lista.controls = [
                item_row(self.page, p, self.on_open_item, self.refresh, mostrar_modulo=False)
                for p in items
            ]
        else:
            self.lista.controls = grouped_rows(self.page, items, self.on_open_item,
                                               self.refresh, mostrar_modulo=False)

    def refresh(self):  # propio
        self.load()
        self.page.update()


# ============================================================================
# Alta / edición de un módulo
# ============================================================================
class ModuleFormView:
    def __init__(self, page: ft.Page, on_created, on_updated, on_deleted):
        """
        on_created(modulo): tras crear (el módulo lo abre)
        on_updated():       tras actualizar (regresa a sus pendientes)
        on_deleted():       tras eliminar (regresa a la lista)
        """
        self.page = page
        self.on_created = on_created
        self.on_updated = on_updated
        self.on_deleted = on_deleted
        self.registro: ModuloApp | None = None
        self.modo = "nuevo"  # "nuevo" | "editar"

        self.txt_nombre = ft.TextField(label="Nombre del módulo", max_length=60)
        self.txt_descripcion = ft.TextField(label="Descripción", multiline=True,
                                            min_lines=2, max_lines=5)
        self.fila_prioridad = ft.Row()
        self._new_dropdown()
        self.lbl_avance = ft.Text()
        self.sld_avance = ft.Slider(min=0, max=100, divisions=20, value=0,
                                    label="{value}%", round=0, on_change=self._on_avance)

        self.lbl_titulo = ft.Text("Nuevo módulo")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        self.btn_eliminar = delete_button(self.confirm_delete)

        self.vista = ft.View(
            route=routes.MODULO_NUEVO,  # el módulo la ajusta: NUEVO o DATOS
            appbar=ft.AppBar(title=self.lbl_titulo, actions=[self.btn_eliminar]),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.txt_nombre,
                            self.txt_descripcion,
                            self.fila_prioridad,
                            self.lbl_avance,
                            self.sld_avance,
                            ft.Row([self.btn_guardar]),
                        ],
                    )
                )
            ],
        )
        self.clear_form()

    def _new_dropdown(self):  # propio
        """Dropdown nuevo (mismo truco que en Proyectos para que se vea limpio)."""
        self.dd_prioridad = ft.Dropdown(
            label="Prioridad", options=dropdown_options(PRIORIDAD_SELECTION),
            value="media", expand=True,
        )
        self.fila_prioridad.controls = [self.dd_prioridad]

    def _set_avance(self, valor: int):  # propio
        self.sld_avance.value = valor
        self.lbl_avance.value = f"Avance: {valor}%"

    def _on_avance(self, e):  # propio
        self._set_avance(int(e.control.value))
        self.page.update()

    def clear_form(self):  # propio
        self.registro = None
        self.modo = "nuevo"
        self.txt_nombre.value = ""
        self.txt_nombre.error_text = None
        self.txt_descripcion.value = ""
        self._new_dropdown()
        self._set_avance(0)
        self.lbl_titulo.value = "Nuevo módulo"
        self.btn_guardar.content = "Guardar"
        self.btn_eliminar.visible = False

    def new(self):  # propio
        self.clear_form()
        self.vista.route = routes.MODULO_NUEVO
        self.page.navigate(routes.MODULO_NUEVO)

    def show(self, m: ModuloApp):  # propio
        """Engrane: el módulo abierto, listo para editar."""
        self.clear_form()
        self.registro = ModuloApp.get(m.id)
        self.modo = "editar"
        self.txt_nombre.value = self.registro.nombre
        self.txt_descripcion.value = self.registro.descripcion or ""
        self.dd_prioridad.value = self.registro.prioridad
        self._set_avance(self.registro.avance)
        self.lbl_titulo.value = "Datos del módulo"
        self.btn_guardar.content = "Actualizar"
        self.btn_eliminar.visible = True
        self.vista.route = routes.MODULO_DATOS
        self.page.navigate(routes.MODULO_DATOS)

    def save(self, e=None):  # propio
        nombre = (self.txt_nombre.value or "").strip()
        self.txt_nombre.error_text = None if nombre else "Requerido"
        if not nombre:
            self.page.update()
            return
        valores = dict(
            nombre=nombre,
            descripcion=(self.txt_descripcion.value or "").strip() or None,
            prioridad=self.dd_prioridad.value or "media",
            avance=int(self.sld_avance.value or 0),
        )
        try:
            if self.modo == "nuevo":
                nuevo = ModuloApp.create(**valores)
            else:
                ModuloApp.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Módulo creado")
            self.on_created(nuevo)
        else:
            notify(self.page, "Módulo actualizado")
            self.clear_form()
            self.on_updated()

    def confirm_delete(self, e=None):  # propio
        m = self.registro
        resumen = services.module_summary(m.id)
        total = resumen.pendientes + resumen.hechos
        mensaje = f"¿Eliminar el módulo «{m.nombre}»?"
        if total:
            mensaje += f"\n\nTambién se eliminan sus {total} pendiente(s)."

        def delete():  # propio
            try:
                ModuloApp.delete(m.id)
            except Exception as ex:  # noqa: BLE001
                notify(self.page, f"Error al eliminar: {ex}")
                return
            self.clear_form()
            notify(self.page, "Módulo eliminado")
            self.on_deleted()

        confirm(self.page, "Eliminar módulo", mensaje, delete)

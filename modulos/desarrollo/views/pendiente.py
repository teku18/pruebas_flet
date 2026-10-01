"""
Formulario de un pendiente (tarea, error o comentario de un módulo):
  /desarrollo/pendiente         -> desde la pestaña Pendientes
  /desarrollo/modulo/pendiente  -> desde los pendientes de un módulo

Siempre editable: [Guardar] y, si ya existe, el bote para eliminar.
Adjuntos (archivos, imágenes, capturas y grabaciones): views/adjuntos.py.
Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import confirm, delete_button, dropdown_options, notify
from modulos.desarrollo import services
from modulos.desarrollo.capturas import Captura
from modulos.desarrollo.models import (
    PRIORIDAD_SELECTION,
    TIPO_PENDIENTE_SELECTION,
    ModuloApp,
    Pendiente,
)
from modulos.desarrollo.views.adjuntos import AttachmentsBox


class PendingFormView:
    def __init__(self, page: ft.Page, on_done):
        """on_done(): después de guardar o eliminar (el módulo decide a dónde regresar)."""
        self.page = page
        self.on_done = on_done
        self.registro: Pendiente | None = None

        self.fila_modulo = ft.Row()
        self.fila_tipo_prioridad = ft.Row()
        self.txt_texto = ft.TextField(label="¿Qué hay que hacer / comentar?",
                                      multiline=True, min_lines=3, max_lines=10)
        self.sw_hecho = ft.Switch(label="Hecho")
        self.lbl_fechas = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.adjuntos = AttachmentsBox(page)

        self.lbl_titulo = ft.Text("Nuevo pendiente")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        self.btn_eliminar = delete_button(self.confirm_delete)

        self.vista = ft.View(
            route="",  # el módulo la ajusta según de dónde vienes
            appbar=ft.AppBar(title=self.lbl_titulo, actions=[self.btn_eliminar]),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.fila_modulo,
                            self.fila_tipo_prioridad,
                            self.txt_texto,
                            self.sw_hecho,
                            self.adjuntos.control,
                            self.lbl_fechas,
                            ft.Row([self.btn_guardar]),
                        ],
                    )
                )
            ],
        )
        self.clear_form()

    def _new_dropdowns(self):  # propio
        """Dropdowns nuevos cada vez (el de módulos se llena con los que existan hoy)."""
        modulos = {str(m.id): m.nombre for m in ModuloApp.search_all()}
        self.dd_modulo = ft.Dropdown(label="Módulo", options=dropdown_options(modulos),
                                     expand=True)
        self.dd_tipo = ft.Dropdown(label="Tipo", options=dropdown_options(TIPO_PENDIENTE_SELECTION),
                                   value="tarea", expand=True)
        self.dd_prioridad = ft.Dropdown(label="Prioridad",
                                        options=dropdown_options(PRIORIDAD_SELECTION),
                                        value="media", expand=True)
        self.fila_modulo.controls = [self.dd_modulo]
        self.fila_tipo_prioridad.controls = [self.dd_tipo, self.dd_prioridad]

    def clear_form(self):  # propio
        self.registro = None
        self._new_dropdowns()
        self.txt_texto.value = ""
        self.txt_texto.error_text = None
        self.sw_hecho.value = False
        self.lbl_fechas.value = ""
        self.lbl_titulo.value = "Nuevo pendiente"
        self.btn_eliminar.visible = False
        self.adjuntos.clear()

    # --- Abrir -----------------------------------------------------------
    def new(self, route: str, modulo_id: int | None = None,  # propio
            capturas: list[Captura] | None = None):
        """Pendiente nuevo; capturas = las que ya vienen adjuntas (botón Reportar)."""
        self.clear_form()
        if modulo_id is not None:
            self.dd_modulo.value = str(modulo_id)
        for c in capturas or []:
            self.adjuntos.add_capture(c)
        self.adjuntos.render()
        self.vista.route = route
        self.page.navigate(route)

    def show(self, p: Pendiente, route: str):  # propio
        self.clear_form()
        self.registro = services.get_item(p.id)
        r = self.registro
        self.adjuntos.load(r.adjuntos)
        self.dd_modulo.value = str(r.modulo_id)
        self.dd_tipo.value = r.tipo
        self.dd_prioridad.value = r.prioridad
        self.txt_texto.value = r.texto
        self.sw_hecho.value = r.hecho
        fechas = f"Creado: {r.creado_en:%d/%m/%Y %H:%M}" if r.creado_en else ""
        if r.hecho_en:
            fechas += f"  ·  Hecho: {r.hecho_en:%d/%m/%Y %H:%M}"
        self.lbl_fechas.value = fechas
        self.lbl_titulo.value = r.tipo_label
        self.btn_eliminar.visible = True
        self.vista.route = route
        self.page.navigate(route)

    # --- Guardar / eliminar ------------------------------------------------
    def save(self, e=None):  # propio
        texto = (self.txt_texto.value or "").strip()
        self.txt_texto.error_text = None if texto else "Requerido"
        self.dd_modulo.error_text = None if self.dd_modulo.value else "Requerido"
        if not texto or not self.dd_modulo.value:
            self.page.update()
            return
        valores = dict(
            modulo_id=int(self.dd_modulo.value),
            tipo=self.dd_tipo.value or "tarea",
            prioridad=self.dd_prioridad.value or "media",
            texto=texto,
            hecho=bool(self.sw_hecho.value),
        )
        try:
            if self.registro is None:
                guardado = Pendiente.create(**valores)
            else:
                guardado = Pendiente.update(self.registro.id, **valores)
            self.adjuntos.apply(guardado.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return
        notify(self.page, "Guardado")
        self.clear_form()
        self.on_done()

    def confirm_delete(self, e=None):  # propio
        p = self.registro

        def delete():  # propio
            try:
                Pendiente.delete(p.id)
            except Exception as ex:  # noqa: BLE001
                notify(self.page, f"Error al eliminar: {ex}")
                return
            notify(self.page, "Eliminado")
            self.clear_form()
            self.on_done()

        confirm(self.page, "Eliminar", f"¿Eliminar «{p.texto[:60]}»?", delete)

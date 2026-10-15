"""
Entornos y variables (/kraken/http/entornos):

  (Globales) (Local ✓) (Producción) (+ Nuevo)
  Local                     [Usar este] [✏] [🗑]
  [✓] base_url   http://192.168.1.10:8069   ✕
  [✓] token      abc123                     ✕
  + Variable

  Globales aplica siempre; el entorno elegido se pone encima (si los dos tienen
  `token`, gana el del entorno). Úsalas como {{token}} en URL, params, headers,
  body o auth.

Se guarda solo (0.8 s después de que dejas de escribir), como Notas.
Los valores se guardan tal cual (texto normal) y viajan en el respaldo.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import confirm, notify
from modulos.kraken import routes
from modulos.kraken.comun import KeyValueEditor, ask_text
from modulos.kraken.models import Ajustes, Entorno

PAUSA_GUARDADO = 0.8


class EnvironmentsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.entorno: Entorno | None = None
        self.variables: list[dict] = []
        self._turno = 0

        self.fila_entornos = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.lbl_nombre = ft.Text(size=18, weight=ft.FontWeight.BOLD, expand=True)
        self.acciones = ft.Row(spacing=0)
        self.kv = KeyValueEditor(page, self._changed, "Variable", "Valor", "Variable")
        self.lbl_estado = ft.Text(size=11, color=ft.Colors.OUTLINE)
        self.vista = ft.View(
            route=routes.ENTORNOS,
            appbar=ft.AppBar(title=ft.Text("Entornos y variables")),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                self.fila_entornos,
                ft.Row([self.lbl_nombre, self.acciones],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self.kv.control,
                self.lbl_estado,
                ft.Text("Globales aplica siempre; el entorno elegido se pone encima (si los "
                        "dos tienen la misma variable, gana el del entorno). Úsalas como "
                        "{{nombre}} en la URL, params, headers, body o auth.",
                        size=12, color=ft.Colors.OUTLINE),
            ]))],
        )

    # ==================================================================
    def load(self, entorno_id: int | None = None):  # propio
        """Abre el entorno elegido (o el que digas)."""
        if entorno_id is None:
            entorno_id = (self.entorno.id if self.entorno else
                          Ajustes.current().entorno_id or Entorno.globals_().id)
        self.entorno = Entorno.get(entorno_id) or Entorno.globals_()
        self.variables = list(self.entorno.variables or [])
        self.kv.load(self.variables)
        self.lbl_estado.value = ""
        self._render()

    def refresh(self):  # propio
        self._render()
        self.page.update()

    def _render(self):  # propio
        activo = Ajustes.current().entorno_id
        chips = []
        for e in Entorno.search_all():
            icono = (ft.Icons.PUBLIC if e.es_global else
                     ft.Icons.CHECK_CIRCLE if e.id == activo else ft.Icons.DNS)
            chips.append(ft.Chip(
                label=ft.Text(e.nombre), show_checkmark=False, selected=e.id == self.entorno.id,
                leading=ft.Icon(icono, size=16),
                tooltip="En uso" if e.id == activo else None,
                on_select=lambda ev, i=e.id: self.select(i)))
        chips.append(ft.Chip(label=ft.Text("Nuevo"), leading=ft.Icon(ft.Icons.ADD, size=16),
                             on_click=lambda e: self.new()))
        self.fila_entornos.controls = chips

        e = self.entorno
        self.lbl_nombre.value = e.nombre
        if e.es_global:
            self.acciones.controls = [ft.Text("Siempre activas", size=12,
                                              color=ft.Colors.OUTLINE)]
        else:
            usando = activo == e.id
            self.acciones.controls = [
                ft.TextButton("Dejar de usar" if usando else "Usar este",
                              icon=ft.Icons.CHECK_CIRCLE if usando else ft.Icons.RADIO_BUTTON_OFF,
                              on_click=lambda ev: self.toggle_active()),
                ft.IconButton(ft.Icons.EDIT, tooltip="Renombrar", on_click=lambda ev: self.rename()),
                ft.IconButton(ft.Icons.DELETE, tooltip="Eliminar", icon_color=ft.Colors.RED,
                              on_click=lambda ev: self.confirm_delete()),
            ]

    # ==================================================================
    def select(self, entorno_id: int):  # propio
        self.save()
        self.load(entorno_id)
        self.page.update()

    def toggle_active(self):  # propio
        usando = Ajustes.current().entorno_id == self.entorno.id
        Ajustes.change(entorno_id=None if usando else self.entorno.id)
        notify(self.page, "Sin entorno" if usando else f"Usando «{self.entorno.nombre}»")
        self.refresh()

    def new(self):  # propio
        def ok(nombre):  # propio
            if not nombre:
                raise ValueError("Ponle un nombre")
            Entorno.check_unique(nombre)
            e = Entorno.create(nombre=nombre, variables=[])
            Ajustes.change(entorno_id=e.id)  # uno nuevo casi siempre es para usarlo
            self.save()
            self.load(e.id)
            self.page.update()
        ask_text(self.page, "Nuevo entorno", ok, etiqueta="Nombre (p. ej. Local, Producción)",
                 boton="Crear")

    def rename(self):  # propio
        def ok(nombre):  # propio
            if not nombre:
                raise ValueError("Ponle un nombre")
            Entorno.check_unique(nombre, excluir_id=self.entorno.id)
            self.entorno = Entorno.update(self.entorno.id, nombre=nombre)
            self.refresh()
        ask_text(self.page, "Renombrar entorno", ok, valor=self.entorno.nombre)

    def confirm_delete(self):  # propio
        def ok():  # propio
            Entorno.delete(self.entorno.id)
            self.entorno = None
            notify(self.page, "Entorno eliminado")
            self.load(Entorno.globals_().id)
            self.page.update()
        confirm(self.page, "Eliminar entorno",
                f"¿Eliminar «{self.entorno.nombre}» y sus variables?", ok)

    # ==================================================================
    # Guardado automático
    # ==================================================================
    def _changed(self):  # propio
        self._turno += 1
        self.page.run_task(self._save_later, self._turno)

    async def _save_later(self, turno: int):  # propio
        await asyncio.sleep(PAUSA_GUARDADO)
        if turno == self._turno:
            self.save()
            self.lbl_estado.update()

    def save(self):  # propio
        """Lo que hay en pantalla -> BD (al instante; también al salir)."""
        if self.entorno is None:
            return
        self._turno += 1  # cancela un guardado pendiente
        self.entorno = Entorno.update(self.entorno.id, variables=[dict(v) for v in self.variables])
        self.lbl_estado.value = "Guardado"

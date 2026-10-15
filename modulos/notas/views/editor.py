"""
Editor de una nota (/notas/editor). NO tiene botón Guardar: se guarda solo.

  ←  [📌] [⋮ color · etiqueta · convertir · archivar · eliminar]
  Título
  ─────────────────────────────
  texto libre…                       (nota de texto)
     o
  ☐ Leche                     ✕      (lista: Enter crea la siguiente casilla)
  ☐ Huevos                    ✕
  + Elemento
  Hechos (1)
  ☑ ~~Pan~~                   ✕      (al palomear, baja aquí)

Guardado automático:
  - cada cambio pide guardar "en un momento" (0.8 s después de que dejas de
    escribir: no se guarda en cada tecla)
  - al salir (← o el botón atrás del celular) se guarda al instante y, si la
    nota quedó vacía, se borra (así un "+" por error no deja basura)

Las casillas viven en self.items (lista de dicts) mientras editas. Al escribir
solo se actualiza el dict; la pantalla se redibuja solo al agregar, quitar o
palomear (si se redibujara en cada tecla, el cursor saltaría).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import confirm, notify
from modulos.notas import routes, services
from modulos.notas.models import Nota
from modulos.notas.views.comun import color_row, label_dialog, note_bg

PAUSA_GUARDADO = 0.8  # segundos sin escribir antes de guardar


class NoteEditor:
    def __init__(self, page: ft.Page, on_closed):
        """on_closed(): al salir (el tablero se recarga)."""
        self.page = page
        self.on_closed = on_closed
        self.nota: Nota | None = None
        self.items: list[dict] = []   # [{"texto": str, "hecho": bool}]
        self._turno = 0               # para la pausa del guardado
        self._enfocar: int | None = None  # índice de la casilla que recibe el cursor

        self.txt_titulo = ft.TextField(
            hint_text="Título", border=ft.NoInputBorder(), text_size=20,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD), max_length=150,
            counter=ft.Text(""), on_change=self._changed,
        )
        self.txt_cuerpo = ft.TextField(
            hint_text="Nota", border=ft.NoInputBorder(), multiline=True, min_lines=6,
            on_change=self._changed,
        )
        self.col_items = ft.Column(spacing=0)
        self.lbl_estado = ft.Text(size=11, color=ft.Colors.OUTLINE)

        self.btn_fijar = ft.IconButton(ft.Icons.PUSH_PIN_OUTLINED, tooltip="Fijar",
                                       on_click=self.toggle_pin)
        self.menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT)
        self.vista = ft.View(
            route=routes.EDITOR,
            appbar=ft.AppBar(actions=[self.btn_fijar, self.menu]),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(content=ft.Column(spacing=4, controls=[
                    self.txt_titulo, self.txt_cuerpo, self.col_items, self.lbl_estado,
                ]))
            ],
        )

    # ==================================================================
    # Abrir / cerrar
    # ==================================================================
    def open(self, nota: Nota):  # propio
        self.nota = services.get(nota.id)
        self.txt_titulo.value = self.nota.titulo or ""
        self.txt_cuerpo.value = self.nota.cuerpo or ""
        self.items = [{"texto": i.texto, "hecho": i.hecho} for i in self.nota.items]
        nueva = self.nota.vacia
        # Nota nueva: el cursor va al cuerpo o a la primera casilla
        self.txt_cuerpo.autofocus = nueva and not self.nota.es_lista
        self._enfocar = 0 if (nueva and self.nota.es_lista) else None
        self._render()
        self.page.navigate(routes.EDITOR)

    def close(self):  # propio
        """Al salir: guarda ya, borra si quedó vacía y avisa al tablero."""
        if self.nota is None:
            return
        self._turno += 1  # cancela un guardado pendiente (ya se guarda aquí)
        self.save()
        if services.delete_if_empty(self.nota.id):
            notify(self.page, "Nota vacía descartada")
        self.nota = None
        self.on_closed()

    # ==================================================================
    # Pintar
    # ==================================================================
    def _render(self):  # propio
        n = self.nota
        self.vista.bgcolor = note_bg(n.color) if n.color else None
        self.vista.appbar.bgcolor = self.vista.bgcolor
        self.btn_fijar.icon = ft.Icons.PUSH_PIN if n.fijada else ft.Icons.PUSH_PIN_OUTLINED
        self.btn_fijar.tooltip = "Desfijar" if n.fijada else "Fijar"
        self.btn_fijar.visible = not n.archivada
        self.txt_cuerpo.visible = not n.es_lista
        self.col_items.visible = n.es_lista
        if n.es_lista:
            self._render_items()
        self._build_menu()
        etiqueta = f" · 🏷 {n.etiqueta.nombre}" if n.etiqueta else ""
        archivada = " · archivada" if n.archivada else ""
        self.lbl_estado.value = f"Editada {n.actualizado_en:%d/%m/%Y %H:%M}{etiqueta}{archivada}"

    def _render_items(self):  # propio
        pendientes = [(k, i) for k, i in enumerate(self.items) if not i["hecho"]]
        hechos = [(k, i) for k, i in enumerate(self.items) if i["hecho"]]
        filas = [self._item_row(k, i) for k, i in pendientes]
        filas.append(ft.TextButton("Elemento", icon=ft.Icons.ADD,
                                   on_click=lambda e: self.add_item()))
        if hechos:
            filas.append(ft.Container(
                padding=ft.Padding.only(top=8, left=4),
                content=ft.Text(f"Hechos ({len(hechos)})", size=12,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE)))
            filas += [self._item_row(k, i) for k, i in hechos]
        self.col_items.controls = filas

    def _item_row(self, k: int, item: dict) -> ft.Control:  # propio
        txt = ft.TextField(
            value=item["texto"], border=ft.NoInputBorder(), dense=True, expand=True,
            content_padding=ft.Padding.symmetric(vertical=10),
            autofocus=k == self._enfocar,
            color=ft.Colors.OUTLINE if item["hecho"] else None,
            text_style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
            if item["hecho"] else None,
            on_change=lambda e, i=item: self._item_text(i, e.control.value),
            on_submit=lambda e, kk=k: self.add_item(after=kk),
        )
        return ft.Row(spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Checkbox(value=item["hecho"], on_change=lambda e, kk=k: self.check(kk)),
            txt,
            ft.IconButton(ft.Icons.CLOSE, icon_size=18, tooltip="Quitar",
                          on_click=lambda e, kk=k: self.remove_item(kk)),
        ])

    def _build_menu(self):  # propio
        n = self.nota
        self.menu.items = [
            ft.PopupMenuItem(content=ft.Text("Color…"), icon=ft.Icons.PALETTE,
                             on_click=lambda e: self.pick_color()),
            ft.PopupMenuItem(content=ft.Text("Etiqueta…"), icon=ft.Icons.LABEL,
                             on_click=lambda e: self.pick_label()),
            ft.PopupMenuItem(
                content=ft.Text("Convertir en nota de texto" if n.es_lista
                                else "Convertir en lista"),
                icon=ft.Icons.NOTES if n.es_lista else ft.Icons.CHECKLIST,
                on_click=lambda e: self.convert()),
            ft.PopupMenuItem(content=ft.Text("Desarchivar" if n.archivada else "Archivar"),
                             icon=ft.Icons.UNARCHIVE if n.archivada else ft.Icons.ARCHIVE,
                             on_click=lambda e: self.toggle_archive()),
            ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                             on_click=lambda e: self.confirm_delete()),
        ]

    def refresh(self):  # propio
        self._render()
        self.page.update()

    # ==================================================================
    # Guardar
    # ==================================================================
    def _changed(self, e=None):  # propio
        """Algo cambió: guarda cuando dejes de escribir un momento."""
        self._turno += 1
        self.page.run_task(self._save_later, self._turno)

    async def _save_later(self, turno: int):  # propio
        await asyncio.sleep(PAUSA_GUARDADO)
        if turno == self._turno and self.nota is not None:
            self.save()
            self.lbl_estado.update()

    def save(self):  # propio
        """La foto completa de la nota -> BD."""
        if self.nota is None:
            return
        items = ([services.ItemData(i["texto"], i["hecho"]) for i in self.items]
                 if self.nota.es_lista else None)
        guardada = services.save_note(self.nota.id, self.txt_titulo.value,
                                      self.txt_cuerpo.value, items)
        if guardada is not None:
            self.nota = guardada
            self.lbl_estado.value = f"Guardada {guardada.actualizado_en:%H:%M:%S}"

    # ==================================================================
    # Casillas
    # ==================================================================
    def _item_text(self, item: dict, texto: str):  # propio
        item["texto"] = texto
        self._changed()

    def add_item(self, after: int | None = None):  # propio
        """Nueva casilla (después de `after`, o al final de las pendientes) con el cursor."""
        if after is None:
            pendientes = [k for k, i in enumerate(self.items) if not i["hecho"]]
            after = pendientes[-1] if pendientes else -1
        self.items.insert(after + 1, {"texto": "", "hecho": False})
        self._enfocar = after + 1
        self._render_items()
        self._enfocar = None
        self._changed()
        self.page.update()

    def check(self, k: int):  # propio
        self.items[k]["hecho"] = not self.items[k]["hecho"]
        self._render_items()
        self._changed()
        self.page.update()

    def remove_item(self, k: int):  # propio
        self.items.pop(k)
        self._render_items()
        self._changed()
        self.page.update()

    # ==================================================================
    # Menú
    # ==================================================================
    def toggle_pin(self, e=None):  # propio
        self.save()
        self.nota = services.set_pinned(self.nota.id, not self.nota.fijada)
        self.refresh()

    def toggle_archive(self):  # propio
        self.save()
        archivar = not self.nota.archivada
        services.set_archived(self.nota.id, archivar)
        notify(self.page, "Archivada" if archivar else "De vuelta en el tablero")
        self.close()
        self.page.navigate(routes.BASE)

    def pick_color(self):  # propio
        def pick(color):  # propio
            self.page.pop_dialog()
            self.nota = services.set_color(self.nota.id, color)
            self.refresh()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Color"), content=color_row(self.nota.color, pick),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())],
        ))

    def pick_label(self):  # propio
        def pick(etiqueta_id):  # propio
            self.nota = services.set_label(self.nota.id, etiqueta_id)
            self.refresh()

        label_dialog(self.page, self.nota.etiqueta_id, pick)

    def convert(self):  # propio
        self.save()
        self.nota = services.convert(self.nota.id)
        self.txt_cuerpo.value = self.nota.cuerpo or ""
        self.items = [{"texto": i.texto, "hecho": i.hecho} for i in self.nota.items]
        self.refresh()

    def confirm_delete(self):  # propio
        def delete():  # propio
            Nota.delete(self.nota.id)
            self.nota = None
            notify(self.page, "Nota eliminada")
            self.on_closed()
            self.page.navigate(routes.BASE)

        confirm(self.page, "Eliminar nota", "¿Eliminar esta nota? No se puede deshacer.",
                delete)

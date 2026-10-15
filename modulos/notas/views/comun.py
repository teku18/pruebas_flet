"""
Piezas que comparten el tablero y el editor de Notas:

  note_bg(color)        fondo de la tarjeta / del editor según el color de la nota
  color_row(...)        fila de circulitos para elegir color (o "sin color")
  label_dialog(...)     elegir etiqueta (o crear una nueva ahí mismo)
  actions_sheet(...)    menú de abajo al dejar presionada una tarjeta

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import confirm, notify
from modulos.notas import services
from modulos.notas.models import COLORES_NOTA, EtiquetaNota, Nota

COLORES_ETIQUETA = ["green", "amber", "blue", "red", "purple", "teal", "orange", "bluegrey"]


def note_bg(color: str | None) -> str:  # propio
    """Un tinte suave del color (se lee bien en modo claro y oscuro)."""
    if not color:
        return ft.Colors.SURFACE_CONTAINER_HIGHEST
    return ft.Colors.with_opacity(0.28, color)


def color_row(actual: str | None, on_pick) -> ft.Row:  # propio
    """Circulitos de color; el primero (tachado) = sin color."""
    def dot(color):  # propio
        elegido = color == actual
        return ft.Container(
            width=34, height=34, border_radius=17,
            bgcolor=color or ft.Colors.SURFACE,
            border=ft.Border.all(3 if elegido else 1,
                                 ft.Colors.ON_SURFACE if elegido else ft.Colors.OUTLINE),
            alignment=ft.Alignment.CENTER,
            content=None if color else ft.Icon(ft.Icons.FORMAT_COLOR_RESET, size=18),
            on_click=lambda e, c=color: on_pick(c),
        )

    return ft.Row(wrap=True, spacing=8, run_spacing=8,
                  controls=[dot(None)] + [dot(c) for c in COLORES_NOTA])


def label_dialog(page: ft.Page, actual_id: int | None, on_pick):  # propio
    """
    Elegir etiqueta para una nota. Abajo, "Nueva etiqueta" la crea y la elige.
    on_pick(etiqueta_id | None).
    """
    txt_nueva = ft.TextField(label="Nueva etiqueta", max_length=40, dense=True,
                             expand=True)

    def pick(etiqueta_id):  # propio
        page.pop_dialog()
        on_pick(etiqueta_id)

    def create(e=None):  # propio
        nombre = (txt_nueva.value or "").strip()
        if not nombre:
            txt_nueva.error_text = "Escribe un nombre"
            page.update()
            return
        try:
            EtiquetaNota.check_unique(nombre)
            usadas = len(EtiquetaNota.search_all())
            nueva = EtiquetaNota.create(nombre=nombre,
                                        color=COLORES_ETIQUETA[usadas % len(COLORES_ETIQUETA)])
        except ValueError as ex:
            txt_nueva.error_text = str(ex)
            page.update()
            return
        pick(nueva.id)

    txt_nueva.on_submit = create
    opciones = [(None, "Sin etiqueta", ft.Colors.OUTLINE)] + [
        (e.id, e.nombre, e.color) for e in EtiquetaNota.search_all()]
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Etiqueta"),
        content=ft.Column(tight=True, spacing=0, scroll=ft.ScrollMode.AUTO, controls=[
            *[ft.ListTile(
                leading=ft.Icon(ft.Icons.LABEL if eid else ft.Icons.LABEL_OFF, color=color),
                title=ft.Text(nombre),
                trailing=ft.Icon(ft.Icons.CHECK) if eid == actual_id else None,
                on_click=lambda e, i=eid: pick(i),
            ) for eid, nombre, color in opciones],
            ft.Row([txt_nueva, ft.IconButton(ft.Icons.ADD, on_click=create)]),
        ]),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))


def actions_sheet(page: ft.Page, nota: Nota, on_changed):  # propio
    """
    Menú al dejar presionada una tarjeta del tablero:
    fijar · archivar · color · etiqueta · eliminar. on_changed() repinta.
    """
    def done(texto: str | None = None):  # propio
        page.pop_dialog()
        if texto:
            notify(page, texto)
        on_changed()

    def pin(e):  # propio
        services.set_pinned(nota.id, not nota.fijada)
        done("Fijada arriba" if not nota.fijada else "Ya no está fijada")

    def archive(e):  # propio
        services.set_archived(nota.id, not nota.archivada)
        done("Archivada" if not nota.archivada else "De vuelta en el tablero")

    def color(c):  # propio
        services.set_color(nota.id, c)
        done()

    def label(e):  # propio
        page.pop_dialog()
        label_dialog(page, nota.etiqueta_id,
                     lambda eid: (services.set_label(nota.id, eid), on_changed()))

    def delete(e):  # propio
        page.pop_dialog()

        def really():  # propio
            Nota.delete(nota.id)
            notify(page, "Nota eliminada")
            on_changed()

        confirm(page, "Eliminar nota", "¿Eliminar esta nota? No se puede deshacer.", really)

    page.show_dialog(ft.BottomSheet(
        show_drag_handle=True,
        content=ft.Container(
            padding=ft.Padding.only(left=16, right=16, bottom=24),
            content=ft.Column(tight=True, spacing=4, controls=[
                ft.ListTile(leading=ft.Icon(ft.Icons.PUSH_PIN),
                            title=ft.Text("Desfijar" if nota.fijada else "Fijar arriba"),
                            on_click=pin, visible=not nota.archivada),
                ft.ListTile(leading=ft.Icon(ft.Icons.UNARCHIVE if nota.archivada
                                            else ft.Icons.ARCHIVE),
                            title=ft.Text("Desarchivar" if nota.archivada else "Archivar"),
                            on_click=archive),
                ft.ListTile(leading=ft.Icon(ft.Icons.LABEL), title=ft.Text("Etiqueta…"),
                            on_click=label),
                ft.ListTile(leading=ft.Icon(ft.Icons.DELETE, color=ft.Colors.RED),
                            title=ft.Text("Eliminar", color=ft.Colors.RED), on_click=delete),
                ft.Text("Color", size=12, color=ft.Colors.OUTLINE),
                color_row(nota.color, color),
            ]),
        ),
    ))

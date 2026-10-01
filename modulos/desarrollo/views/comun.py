"""
Piezas que comparten las pantallas de Desarrollo:
  - color de cada prioridad (el color ES el mensaje: rojo = urge)
  - la línea de un pendiente (○ para marcar hecho, tocar para abrir)
"""
import flet as ft

from core.ui import notify, swipe_to_delete
from modulos.desarrollo import services
from modulos.desarrollo.models import Pendiente

COLOR_PRIORIDAD = {
    "alta": ft.Colors.RED,
    "media": ft.Colors.AMBER,
    "baja": ft.Colors.BLUE_GREY,
}

ICONO_TIPO = {
    "tarea": ft.Icons.TASK_ALT,
    "error": ft.Icons.BUG_REPORT,
    "comentario": ft.Icons.CHAT_BUBBLE_OUTLINE,
}

COLOR_HECHO = ft.Colors.GREEN


def priority_header(prioridad_label: str, color, cantidad: int) -> ft.Control:  # propio
    """Encabezado de grupo: ● Alta (3)"""
    return ft.Container(
        padding=ft.Padding.only(top=10, left=4),
        content=ft.Row(
            spacing=6,
            controls=[
                ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                ft.Text(f"{prioridad_label} ({cantidad})", weight=ft.FontWeight.BOLD),
            ],
        ),
    )


def item_row(  # propio
    page: ft.Page, p: Pendiente, on_open, on_changed, mostrar_modulo: bool
) -> ft.Control:
    """
    Una línea de pendiente:
      ║ ○  Texto del pendiente
      ║    🐞 Error · Finanzas
    ○ / ✓ lo marca o desmarca hecho · tocar abre el formulario · deslizar borra.
    """
    color = COLOR_HECHO if p.hecho else COLOR_PRIORIDAD.get(p.prioridad, ft.Colors.GREY)

    detalle = p.tipo_label
    if mostrar_modulo and p.modulo:
        detalle += f" · {p.modulo.nombre}"
    if p.hecho and p.hecho_en:
        detalle += f" · hecho {p.hecho_en:%d/%m/%Y}"
    if p.adjuntos:
        detalle += f" · 📎 {len(p.adjuntos)}"

    def toggle(e):  # propio
        try:
            actualizado = services.toggle_done(p.id)
        except Exception as ex:  # noqa: BLE001
            notify(page, f"No se pudo marcar: {ex}")
            return
        notify(page, "✓ Hecho" if actualizado.hecho else "Regresó a pendientes")
        on_changed()

    def delete():  # propio
        try:
            Pendiente.delete(p.id)
        except Exception as ex:  # noqa: BLE001
            notify(page, f"Error al eliminar: {ex}")
            return
        notify(page, "Eliminado")
        on_changed()

    linea = ft.Container(
        border_radius=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border=ft.Border.only(left=ft.BorderSide(4, color)),
        ink=True,
        on_click=lambda e: on_open(p),
        content=ft.Row(
            spacing=0,
            controls=[
                ft.IconButton(
                    ft.Icons.CHECK_CIRCLE if p.hecho else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    icon_color=color,
                    tooltip="Deshacer" if p.hecho else "Marcar como hecho",
                    on_click=toggle,
                ),
                ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        ft.Text(
                            p.texto,
                            weight=ft.FontWeight.W_500,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.OUTLINE if p.hecho else None,
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
                            if p.hecho else None,
                        ),
                        ft.Row(
                            spacing=4,
                            controls=[
                                ft.Icon(ICONO_TIPO.get(p.tipo), size=14, color=ft.Colors.OUTLINE),
                                ft.Text(detalle, size=12, color=ft.Colors.OUTLINE),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )
    return swipe_to_delete(
        page,
        key=f"pendiente-{p.id}",
        contenido=linea,
        titulo="Eliminar",
        mensaje=f"¿Eliminar «{p.texto[:60]}»?",
        on_delete=delete,
    )


def grouped_rows(page, pendientes: list[Pendiente], on_open, on_changed,  # propio
                 mostrar_modulo: bool) -> list[ft.Control]:
    """Pendientes (ya ordenados alta→baja) con un encabezado por prioridad."""
    controles: list[ft.Control] = []
    actual = None
    for p in pendientes:
        if p.prioridad != actual:
            actual = p.prioridad
            cantidad = sum(1 for x in pendientes if x.prioridad == actual)
            controles.append(priority_header(p.prioridad_label, COLOR_PRIORIDAD[actual], cantidad))
        controles.append(item_row(page, p, on_open, on_changed, mostrar_modulo))
    return controles

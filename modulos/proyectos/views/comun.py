"""
Piezas que comparten las pantallas de Proyectos:

  icon_of(texto)       "STAR" -> ft.Icons.STAR  (los catálogos guardan el nombre)
  stage_chip(...)      etiqueta de color con el nombre de la etapa
  view_toggle(...)     botón ☰ / ▥ para cambiar entre Lista y Kanban
  kanban_board(...)    tablero: una columna por etapa, tarjetas que se arrastran
  move_menu(...)       menú "Mover a ▸" (para el celular, donde arrastrar dentro
                       de algo que también se desliza es incómodo)
  catalog_dialog(...)  alta/edición de una etapa o tipo de entrada (Ajustes y el
                       "+" del formulario de entradas usan el mismo)

Kanban con Flet (Draggable + DragTarget):

  DragTarget(group="tareas")  <- cada columna
     └ Draggable(group="tareas", data=id)  <- la manijita ⋮⋮ de cada tarjeta

  Al soltar una tarjeta en una columna del mismo "group", Flet llama
  on_accept(e) de la columna; e.src es el Draggable y e.src.data su id.
  La manija es lo único arrastrable: así deslizar el tablero o la lista
  sigue funcionando normal con el dedo.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import notify
from modulos.proyectos.models import (
    CLASE_ETAPA_SELECTION,
    COLORES_CATALOGO,
    ICONOS_ENTRADA,
    EtapaProyecto,
    EtapaTarea,
    TipoEntrada,
)

ANCHO_COLUMNA = 270


def icon_of(nombre: str | None):  # propio
    """Nombre guardado en la BD -> ícono de Flet (LABEL si no existe)."""
    return getattr(ft.Icons, nombre or "LABEL", ft.Icons.LABEL)


def stage_chip(nombre: str, color: str) -> ft.Control:  # propio
    """Etiqueta redondita de color (la etapa de un proyecto o tarea)."""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.18, color),
        content=ft.Text(nombre, size=11, color=color, weight=ft.FontWeight.W_500),
    )


def view_toggle(modo: str, on_change) -> ft.IconButton:  # propio
    """Muestra el ícono de la vista A LA QUE CAMBIAS (como Odoo)."""
    es_lista = modo == "lista"
    return ft.IconButton(
        ft.Icons.VIEW_KANBAN if es_lista else ft.Icons.VIEW_LIST,
        tooltip="Ver como Kanban" if es_lista else "Ver como lista",
        on_click=lambda e: on_change("kanban" if es_lista else "lista"),
    )


def move_menu(etapas, actual_id: int | None, on_move, item_id: int) -> ft.PopupMenuButton:  # propio
    """Menú ⋮ con "Mover a: <etapa>" (todas menos la actual)."""
    return ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        tooltip="Mover a…",
        items=[
            ft.PopupMenuItem(
                content=ft.Row(spacing=8, controls=[
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=e.color),
                    ft.Text(f"Mover a {e.nombre}"),
                ]),
                on_click=lambda ev, eid=e.id: on_move(item_id, eid),
            )
            for e in etapas if e.id != actual_id
        ],
    )


def drag_handle(grupo: str, item_id: int, titulo: str) -> ft.Draggable:  # propio
    """Manija ⋮⋮ para arrastrar la tarjeta a otra columna."""
    return ft.Draggable(
        group=grupo,
        data=item_id,
        content=ft.Container(
            padding=ft.Padding.symmetric(horizontal=2, vertical=8),
            content=ft.Icon(ft.Icons.DRAG_INDICATOR, size=20, color=ft.Colors.OUTLINE),
        ),
        # Lo que va pegado al dedo mientras arrastras
        content_feedback=ft.Container(
            width=ANCHO_COLUMNA - 30,
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            content=ft.Text(titulo, max_lines=2, size=13,
                            color=ft.Colors.ON_PRIMARY_CONTAINER),
        ),
    )


def kanban_board(grupo: str, columnas, tarjeta, on_move, vacio: str = "Vacío") -> ft.Control:  # propio
    """
    columnas: [(etapa, registros)]   tarjeta(registro, etapa) -> Control
    on_move(registro_id, etapa_id) se llama al soltar una tarjeta en otra columna.
    """
    def column(etapa, registros) -> ft.Control:  # propio
        caja = ft.Container(
            width=ANCHO_COLUMNA,
            padding=8,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.only(top=ft.BorderSide(4, etapa.color)),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row([
                        ft.Text(etapa.nombre, weight=ft.FontWeight.BOLD, expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=1),
                            border_radius=10,
                            bgcolor=ft.Colors.with_opacity(0.18, etapa.color),
                            content=ft.Text(str(len(registros)), size=12),
                        ),
                    ]),
                    ft.ListView(
                        expand=True, spacing=6, padding=ft.Padding.only(bottom=80),
                        controls=[tarjeta(r, etapa) for r in registros] or [
                            ft.Text(vacio, size=12, italic=True, color=ft.Colors.OUTLINE)
                        ],
                    ),
                ],
            ),
        )

        def accept(e):  # propio
            caja.bgcolor = ft.Colors.SURFACE_CONTAINER_HIGHEST
            if e.src is not None and e.src.data is not None:
                on_move(e.src.data, etapa.id)

        def hover(e, encima: bool):  # propio
            caja.bgcolor = (ft.Colors.with_opacity(0.15, etapa.color) if encima
                            else ft.Colors.SURFACE_CONTAINER_HIGHEST)
            caja.update()

        return ft.DragTarget(
            group=grupo,
            content=caja,
            on_accept=accept,
            on_will_accept=lambda e: hover(e, True),
            on_leave=lambda e: hover(e, False),
        )

    return ft.Row(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,  # columnas de alto completo
        controls=[column(e, regs) for e, regs in columnas],
    )


# ============================================================================
# Alta / edición de catálogos (etapas y tipos de entrada)
# ============================================================================
TITULOS = {
    EtapaProyecto: ("etapa de proyecto", "Nueva"),
    EtapaTarea: ("etapa de tarea", "Nueva"),
    TipoEntrada: ("tipo de entrada", "Nuevo"),
}


def _picker(opciones, actual, dibujar) -> tuple[ft.Row, dict]:  # propio
    """Fila de opciones tocables (colores o íconos); estado["valor"] = la elegida."""
    estado = {"valor": actual}
    fila = ft.Row(wrap=True, spacing=6, run_spacing=6)

    def pick(valor):  # propio
        estado["valor"] = valor
        render()
        fila.update()

    def render():  # propio
        fila.controls = [
            ft.Container(
                content=dibujar(op),
                border_radius=16,
                padding=2,
                border=ft.Border.all(3, ft.Colors.ON_SURFACE) if op == estado["valor"] else None,
                on_click=lambda e, o=op: pick(o),
            )
            for op in opciones
        ]

    render()
    return fila, estado


def catalog_dialog(page: ft.Page, modelo, on_saved, registro=None):  # propio
    """
    Diálogo para crear (registro=None) o editar una etapa / tipo de entrada.
    on_saved(registro_guardado) se llama al guardar.
    """
    singular, nuevo = TITULOS[modelo]
    txt_nombre = ft.TextField(label="Nombre", value=registro.nombre if registro else "",
                              autofocus=True, max_length=60)

    color_actual = registro.color if registro else COLORES_CATALOGO[0]
    fila_color, color = _picker(
        COLORES_CATALOGO, color_actual,
        lambda c: ft.Container(width=26, height=26, border_radius=13, bgcolor=c),
    )
    extras: list[ft.Control] = [ft.Text("Color", size=12, color=ft.Colors.OUTLINE), fila_color]

    dd_clase = sw_cerrada = sw_hito = icono = None
    if modelo is EtapaProyecto:
        dd_clase = ft.Dropdown(
            label="¿Qué significa?",
            value=registro.clase if registro else "en_curso",
            options=[ft.DropdownOption(key=k, text=v) for k, v in CLASE_ETAPA_SELECTION.items()],
        )
        extras += [dd_clase, ft.Text(
            "En curso: avisa si se estanca · En pausa: no avisa · "
            "Terminada / Cancelada: el proyecto se cierra y lleva fecha fin.",
            size=11, color=ft.Colors.OUTLINE)]
    elif modelo is EtapaTarea:
        sw_cerrada = ft.Switch(label="Cuenta como hecha",
                               value=registro.cerrada if registro else False)
        extras += [sw_cerrada, ft.Text(
            "Llevar una tarea a esta etapa la marca como hecha.",
            size=11, color=ft.Colors.OUTLINE)]
    else:
        sw_hito = ft.Switch(label="Es hito (línea de tiempo y resumen del año)",
                            value=registro.es_hito if registro else False)
        fila_icono, icono = _picker(
            ICONOS_ENTRADA, registro.icono if registro else "LABEL",
            lambda n: ft.Container(width=28, height=28, alignment=ft.Alignment.CENTER,
                                   content=ft.Icon(icon_of(n), size=20)),
        )
        extras += [sw_hito, ft.Text("Ícono", size=12, color=ft.Colors.OUTLINE), fila_icono]

    def save(e=None):  # propio
        nombre = (txt_nombre.value or "").strip()
        if not nombre:
            txt_nombre.error_text = "Requerido"
            page.update()
            return
        valores = {"nombre": nombre, "color": color["valor"]}
        if dd_clase:
            valores["clase"] = dd_clase.value or "en_curso"
        if sw_cerrada:
            valores["cerrada"] = bool(sw_cerrada.value)
        if sw_hito:
            valores["es_hito"] = bool(sw_hito.value)
            valores["icono"] = icono["valor"]
        try:
            modelo.check_unique(nombre, excluir_id=registro.id if registro else None)
            guardado = (modelo.create_last(**valores) if registro is None
                        else modelo.update(registro.id, **valores))
        except ValueError as ex:
            txt_nombre.error_text = str(ex)
            page.update()
            return
        except Exception as ex:  # noqa: BLE001
            notify(page, f"Error al guardar: {ex}")
            return
        page.pop_dialog()
        on_saved(guardado)

    txt_nombre.on_submit = save
    titulo = f"Editar {singular}" if registro else f"{nuevo} {singular}"
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Column(tight=True, spacing=8,
                              controls=[txt_nombre, *extras]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton("Guardar", on_click=save),
            ],
        )
    )

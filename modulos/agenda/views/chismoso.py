"""
Pantalla principal de la Agenda (/agenda), con tres pestañas:

  [Hoy]         el chismoso: lo vencido, lo de hoy, lo de mañana y lo que ya hiciste
  [Todas]       todas las tareas pendientes, de la más próxima a la más lejana
  [Calendario]  cuántas tareas hay por día, semana, mes o año (views/calendario.py)

Esta pantalla NO calcula nada: le pide a services.gossip() la lista ya
clasificada y solo la pinta (la vista pregunta y pinta, la lógica decide).

Tocar el círculo ○ marca la tarea como hecha; tocar ✓ en "Hechas hoy" lo deshace.
Si la tarea es de un proyecto, ofrece registrar el avance en su bitácora.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date, datetime

import flet as ft

from core.ui import add_button, notify, short_date, swipe_to_delete
from modulos.agenda import services
from modulos.agenda.models import Cumplimiento, Tarea
from modulos.agenda.routes import BASE
from modulos.agenda.views.calendario import CalendarPanel

# Color de cada grupo (el color ES el mensaje: rojo = ya se te quemó)
COLOR_VENCIDA = ft.Colors.RED
COLOR_HOY = ft.Colors.AMBER
COLOR_MANANA = ft.Colors.OUTLINE
COLOR_HECHA = ft.Colors.GREEN


class AgendaView:
    def __init__(self, page: ft.Page, on_open_task, on_new_task):
        """
        on_open_task(tarea): abre el formulario de una tarea (lo pone el módulo)
        on_new_task():       formulario vacío
        """
        self.page = page
        self.on_open_task = on_open_task
        self.pestana = "hoy"  # "hoy" | "todas" | "calendario"
        self.calendario = CalendarPanel(page, on_open_task=on_open_task, on_change=self.refresh)

        self.fila_pestanas = ft.Row(spacing=6)
        self.lista = ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90))
        self.vista = ft.View(
            route=BASE,
            appbar=ft.AppBar(title=ft.Text("Agenda")),
            floating_action_button=add_button("Nueva tarea", lambda e: on_new_task()),
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
            for clave, texto in (("hoy", "Hoy"), ("todas", "Todas"), ("calendario", "Calendario"))
        ]

    def set_tab(self, pestana: str):  # propio
        self.pestana = pestana
        self._build_tabs()
        self.load()
        self.page.update()

    def load(self):  # propio
        if self.pestana == "hoy":
            self.lista.controls = self._today_controls()
        elif self.pestana == "todas":
            self.lista.controls = self._all_controls()
        else:
            self.lista.controls = self.calendario.controls()

    # ==================================================================
    # [Hoy] el chismoso
    # ==================================================================
    def _today_controls(self) -> list[ft.Control]:  # propio
        hoy = date.today()
        chisme = services.gossip(hoy)
        controles: list[ft.Control] = []

        grupos = [
            ("Vencidas", COLOR_VENCIDA, chisme.vencidas),
            ("Hoy", COLOR_HOY, chisme.hoy),
            ("Mañana", COLOR_MANANA, chisme.manana),
        ]
        for titulo, color, tareas in grupos:
            if not tareas:
                continue
            controles.append(self._header(titulo, color, len(tareas)))
            controles += [self._task_row(t, color, hoy) for t in tareas]

        if chisme.hechas:
            controles.append(self._header("Hechas hoy", COLOR_HECHA, len(chisme.hechas)))
            controles += [self._done_row(c) for c in chisme.hechas]

        # Proyectos olvidados (la otra mitad del chisme)
        estancados = self._stalled_projects()
        if estancados:
            controles.append(self._header("Proyectos sin avance", ft.Colors.ORANGE,
                                          len(estancados)))
            controles += [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=4),
                    content=ft.Row([
                        ft.Icon(ft.Icons.FOLDER_OUTLINED, size=18, color=ft.Colors.ORANGE),
                        ft.Text(pro.nombre, expand=True),
                        ft.Text(f"{st.dias_sin_avance} días", size=12, color=ft.Colors.ORANGE),
                    ]),
                )
                for pro, st in estancados
            ]

        if chisme.vacio and not estancados:
            controles.append(
                ft.Container(
                    padding=ft.Padding.only(top=60),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=64, color=COLOR_HECHA),
                            ft.Text("Nada pendiente", size=18, weight=ft.FontWeight.BOLD),
                            ft.Text("Ni para hoy ni para mañana.", color=ft.Colors.OUTLINE),
                        ],
                    ),
                )
            )
        return controles

    @staticmethod
    def _stalled_projects():  # propio
        from modulos.proyectos.services import stalled_projects
        return stalled_projects()

    @staticmethod
    def _header(titulo: str, color, cantidad: int) -> ft.Control:  # propio
        return ft.Container(
            padding=ft.Padding.only(top=10, left=4),
            content=ft.Row(
                spacing=6,
                controls=[
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=color),
                    ft.Text(f"{titulo} ({cantidad})", weight=ft.FontWeight.BOLD),
                ],
            ),
        )

    def _details(self, t: Tarea, hoy: date, mostrar_fecha: bool) -> str:  # propio
        """Segunda línea: 'venció 1 oct · 10:00 · 📁 App mamá · ↻ Cada mes'."""
        partes = []
        if t.fecha < hoy:
            dias = (hoy - t.fecha).days
            partes.append("venció ayer" if dias == 1 else f"venció hace {dias} días")
        elif mostrar_fecha:
            partes.append(short_date(t.fecha))
        if t.horario:
            partes.append(t.horario)
        if t.proyecto:
            partes.append(f"📁 {t.proyecto.nombre}")
        if t.recurrente:
            partes.append(f"↻ {t.frecuencia_label}")
        return " · ".join(partes)

    def _task_row(self, t: Tarea, color, hoy: date, mostrar_fecha: bool = False) -> ft.Control:  # propio
        detalle = self._details(t, hoy, mostrar_fecha)
        return ft.Container(
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.only(left=ft.BorderSide(4, color)),
            ink=True,
            on_click=lambda e, x=t: self.on_open_task(x),
            content=ft.Row(
                spacing=0,
                controls=[
                    ft.IconButton(
                        ft.Icons.RADIO_BUTTON_UNCHECKED,
                        icon_color=color,
                        tooltip="Marcar como hecha",
                        on_click=lambda e, x=t: self.complete(x),
                    ),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(t.titulo, weight=ft.FontWeight.W_500, max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                            *([ft.Text(detalle, size=12, color=ft.Colors.OUTLINE)]
                              if detalle else []),
                        ],
                    ),
                ],
            ),
        )

    def _done_row(self, c: Cumplimiento) -> ft.Control:  # propio
        t = c.tarea
        return ft.Container(
            border_radius=10,
            content=ft.Row(
                spacing=0,
                controls=[
                    ft.IconButton(
                        ft.Icons.CHECK_CIRCLE,
                        icon_color=COLOR_HECHA,
                        tooltip="Deshacer",
                        on_click=lambda e, x=c: self.undo(x),
                    ),
                    ft.Text(
                        t.titulo,
                        expand=True,
                        color=ft.Colors.OUTLINE,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                    ),
                    ft.Text(f"{c.hecho_en:%H:%M}", size=12, color=ft.Colors.OUTLINE),
                    ft.Container(width=12),
                ],
            ),
        )

    # ==================================================================
    # [Todas]
    # ==================================================================
    def _all_controls(self) -> list[ft.Control]:  # propio
        hoy = date.today()
        tareas = services.all_pending()
        if not tareas:
            return [ft.Text("No hay tareas. Crea una con el botón +.", italic=True)]

        def color(t: Tarea):  # propio
            if t.fecha < hoy:
                return COLOR_VENCIDA
            return COLOR_HOY if t.fecha == hoy else COLOR_MANANA

        return [
            swipe_to_delete(
                self.page,
                key=f"tarea-{t.id}",
                contenido=self._task_row(t, color(t), hoy, mostrar_fecha=True),
                titulo="Eliminar tarea",
                mensaje=f"¿Eliminar «{t.titulo}»?"
                        + ("\n\nTambién se borra su historial." if t.recurrente else ""),
                on_delete=lambda x=t: self._delete(x),
            )
            for t in tareas
        ]

    def _delete(self, t: Tarea):  # propio
        try:
            Tarea.delete(t.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return
        self.load()
        notify(self.page, "Tarea eliminada")
        self.page.update()

    # ==================================================================
    # Acciones
    # ==================================================================
    def complete(self, t: Tarea):  # propio
        """Círculo ○: la marca como hecha (lo mismo desde el formulario)."""
        complete_task(self.page, t, on_done=self.refresh)

    def undo(self, c: Cumplimiento):  # propio
        services.undo(c.id)
        notify(self.page, f"«{c.tarea.titulo}» regresó a pendientes")
        self.refresh()

    def refresh(self):  # propio
        self.load()
        self.page.update()


# ============================================================================
# Marcar hecha (se usa desde el chismoso y desde el formulario)
# ============================================================================
def complete_task(page: ft.Page, t: Tarea, on_done) -> None:  # propio
    """
    Marca la tarea como hecha. Si es de un proyecto, pregunta si quieres
    dejar el avance en su bitácora (así la historia se llena sola).
    """
    try:
        services.complete(t.id)
    except Exception as ex:  # noqa: BLE001
        notify(page, f"No se pudo marcar: {ex}")
        return

    # Si es recurrente, avisa cuándo vuelve a salir
    proxima = services.get_task(t.id).fecha if t.recurrente else None
    on_done()

    if t.proyecto_id is None:
        notify(page, f"✓ Hecho · vuelve el {short_date(proxima)}" if proxima else "✓ Hecho")
        return

    def close(e=None):  # propio
        page.pop_dialog()

    def register(e=None):  # propio
        from modulos.proyectos.models import Entrada

        page.pop_dialog()
        try:
            Entrada.create(proyecto_id=t.proyecto_id, fecha_hora=datetime.now().replace(microsecond=0),
                           tipo="avance", notas=f"✓ {t.titulo}")
        except Exception as ex:  # noqa: BLE001
            notify(page, f"No se pudo registrar: {ex}")
            return
        notify(page, "Avance registrado en la bitácora")

    nombre = t.proyecto.nombre if t.proyecto else "su proyecto"
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("✓ Hecho"),
            content=ft.Text(
                f"¿Registrar «{t.titulo}» como avance en la bitácora de «{nombre}»?"
                + (f"\n\nLa tarea vuelve el {short_date(proxima)}." if proxima else "")
            ),
            actions=[
                ft.TextButton("Ahora no", on_click=close),
                ft.TextButton("Registrar", on_click=register),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )

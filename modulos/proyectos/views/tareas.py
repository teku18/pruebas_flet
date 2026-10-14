"""
Tareas DENTRO de un proyecto (pestaña "Tareas" de la bitácora):

  Lista ☰   agrupada por etapa:  ● Por hacer (3)  ● En proceso (1)  ● Hecho (5)
  Kanban ▥  una columna por etapa; la manija ⋮⋮ arrastra, el menú ⋮ "Mover a…"

  /proyectos/bitacora/tarea  -> formulario de una tarea del proyecto

Son las MISMAS tareas de la Agenda (tabla "tareas"):
  - con fecha  -> también salen en la Agenda (chismoso y calendario)
  - sin fecha  -> solo viven aquí (ideas, pendientes sin día)
  - frecuencia y horario se editan en la Agenda; aquí solo se muestran

Llevar una tarea a una etapa "hecha" la marca como hecha (con historial,
como en la Agenda) y ofrece dejar el avance en la bitácora.

Adjuntos: la misma caja que Desarrollo y la bitácora (core/adjuntos_ui.py),
con "Adjuntar archivo" y "De mis capturas". Archivos en data/tareas/<id>/.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft
from sqlalchemy.orm import selectinload

from core.adjuntos import Adjunto
from core.adjuntos_ui import AttachmentsBox
from core.database import SessionLocal
from core.ui import DateField, confirm, delete_button, notify, short_date, swipe_to_delete
from modulos.agenda.models import Tarea
from modulos.agenda.models.tarea import MODELO_ADJUNTOS, TAREAS_ADJUNTOS_DIR
from modulos.proyectos import routes
from modulos.proyectos import services as ps
from modulos.proyectos.models import EtapaTarea, Proyecto
from modulos.proyectos.views.comun import drag_handle, kanban_board, move_menu


class ProjectTasks:
    def __init__(self, page: ft.Page, on_changed):
        """on_changed(): algo cambió (la bitácora recarga y repinta)."""
        self.page = page
        self.on_changed = on_changed
        self.proyecto: Proyecto | None = None
        self.vista_modo = "lista"  # "lista" | "kanban"
        self.registro: Tarea | None = None
        self.n_adjuntos: dict[int, int] = {}  # {tarea_id: cuántos} para el 📎 de la lista
        self._build_form()

    # ==================================================================
    # Cuerpo de la pestaña
    # ==================================================================
    def body(self, pro: Proyecto) -> ft.Control:  # propio
        self.proyecto = pro
        self.n_adjuntos = Adjunto.count_by_record(MODELO_ADJUNTOS)
        columnas = ps.tasks_by_stage(pro)
        if not any(tareas for _, tareas in columnas):
            return ft.Container(
                padding=ft.Padding.only(top=40),
                alignment=ft.Alignment.TOP_CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECKLIST, size=56, color=ft.Colors.OUTLINE),
                        ft.Text("Sin tareas todavía", size=16, weight=ft.FontWeight.BOLD),
                        ft.Text("Crea la primera con el botón +.\n"
                                "Con fecha también sale en la Agenda.",
                                text_align=ft.TextAlign.CENTER, color=ft.Colors.OUTLINE),
                    ],
                ),
            )
        if self.vista_modo == "kanban":
            return kanban_board("tareas", columnas, self._card, self.move,
                                vacio="Suelta aquí una tarea")
        return self._list(columnas)

    def pending_count(self, pro: Proyecto) -> int:  # propio
        return sum(1 for t in ps.project_tasks(pro.id) if not t.completada)

    # --- Lista agrupada por etapa ---------------------------------------
    def _list(self, columnas) -> ft.Control:  # propio
        controles: list[ft.Control] = []
        for etapa, tareas in columnas:
            controles.append(ft.Container(
                padding=ft.Padding.only(top=10, left=4),
                content=ft.Row(spacing=6, controls=[
                    ft.Container(width=10, height=10, border_radius=5, bgcolor=etapa.color),
                    ft.Text(f"{etapa.nombre} ({len(tareas)})", weight=ft.FontWeight.BOLD),
                ]),
            ))
            controles += [self._row(t, etapa) for t in tareas]
        return ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90),
                           controls=controles)

    def _detail(self, t: Tarea) -> str:  # propio
        """'vence 3 oct · 10:00 · ↻ Cada mes'  o  'Sin fecha'."""
        partes = []
        hoy = date.today()
        if t.fecha is None:
            partes.append("Sin fecha")
        elif not t.completada and t.fecha < hoy:
            partes.append(f"venció {short_date(t.fecha)}")
        elif t.fecha == hoy:
            partes.append("hoy")
        elif (t.fecha - hoy).days == 1:
            partes.append("mañana")
        else:
            partes.append(short_date(t.fecha))
        if t.horario:
            partes.append(t.horario)
        if t.recurrente:
            partes.append(f"↻ {t.frecuencia_label}")
        if self.n_adjuntos.get(t.id):
            partes.append(f"📎 {self.n_adjuntos[t.id]}")
        return " · ".join(partes)

    def _check(self, t: Tarea) -> ft.IconButton:  # propio
        hecha = t.completada
        return ft.IconButton(
            ft.Icons.CHECK_CIRCLE if hecha else ft.Icons.RADIO_BUTTON_UNCHECKED,
            icon_color=ft.Colors.GREEN if hecha else ft.Colors.OUTLINE,
            tooltip="Reabrir" if hecha else "Marcar como hecha",
            on_click=lambda e, x=t: self.toggle(x),
        )

    def _title(self, t: Tarea, size: int = 14) -> ft.Text:  # propio
        return ft.Text(
            t.titulo, size=size, weight=ft.FontWeight.W_500, max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
            color=ft.Colors.OUTLINE if t.completada else None,
            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH) if t.completada else None,
        )

    def _detail_text(self, t: Tarea) -> ft.Text:  # propio
        vencida = t.fecha and not t.completada and t.fecha < date.today()
        return ft.Text(self._detail(t), size=11,
                       color=ft.Colors.RED if vencida else ft.Colors.OUTLINE)

    def _row(self, t: Tarea, etapa: EtapaTarea) -> ft.Control:  # propio
        linea = ft.Container(
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.only(left=ft.BorderSide(4, etapa.color)),
            ink=True,
            on_click=lambda e, x=t: self.open(x),
            content=ft.Row(spacing=0, controls=[
                self._check(t),
                ft.Column(expand=True, spacing=0, controls=[
                    self._title(t), self._detail_text(t),
                ]),
                move_menu(ps.task_stages(self.proyecto), etapa.id, self.move, t.id),
            ]),
        )
        return swipe_to_delete(
            self.page, key=f"ptarea-{t.id}", contenido=linea,
            titulo="Eliminar tarea", mensaje=f"¿Eliminar «{t.titulo}»?",
            on_delete=lambda x=t: self._delete(x),
        )

    def _card(self, t: Tarea, etapa: EtapaTarea) -> ft.Control:  # propio
        return ft.Container(
            border_radius=10,
            bgcolor=ft.Colors.SURFACE,
            ink=True,
            on_click=lambda e, x=t: self.open(x),
            padding=ft.Padding.only(left=4, top=2, bottom=6),
            content=ft.Row(
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    drag_handle("tareas", t.id, t.titulo),
                    ft.Column(expand=True, spacing=2, controls=[
                        ft.Container(height=6), self._title(t, 13), self._detail_text(t),
                    ]),
                    move_menu(ps.task_stages(self.proyecto), etapa.id, self.move, t.id),
                ],
            ),
        )

    # ==================================================================
    # Mover / marcar
    # ==================================================================
    def move(self, tarea_id: int, etapa_id: int):  # propio
        try:
            resultado = ps.move_task(tarea_id, etapa_id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo mover: {ex}")
            return
        self.on_changed()
        if resultado == "hecha":
            from modulos.agenda.views.chismoso import ask_log_entry

            ask_log_entry(self.page, Tarea.get(tarea_id), on_registered=self.on_changed)
        elif resultado == "reabierta":
            notify(self.page, "Tarea reabierta")

    def toggle(self, t: Tarea):  # propio
        """El circulito: hecha <-> pendiente (a la primera etapa que toque)."""
        etapas = ps.task_stages(self.proyecto)
        destino = next((e for e in etapas if e.cerrada != t.completada), None)
        if destino is None:
            notify(self.page, "Este proyecto no tiene una etapa "
                              + ("abierta" if t.completada else "de hecho")
                              + ". Revisa sus Etapas de tareas.")
            return
        self.move(t.id, destino.id)

    def _delete(self, t: Tarea) -> bool:  # propio
        try:
            Tarea.delete(t.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        notify(self.page, "Tarea eliminada")
        self.on_changed()
        return True

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        self.adjuntos = AttachmentsBox(self.page, MODELO_ADJUNTOS,
                                       lambda tarea_id: TAREAS_ADJUNTOS_DIR / str(tarea_id))
        # expand dentro de un Row = todo el ancho
        self.txt_titulo = ft.TextField(label="Tarea", max_length=150, autofocus=True,
                                       expand=True)
        self.txt_notas = ft.TextField(label="Notas", multiline=True, min_lines=3, max_lines=8,
                                      expand=True)
        self.fila_etapa = ft.Row()
        self.sw_fecha = ft.Switch(label="Con fecha (también sale en la Agenda)",
                                  on_change=self._toggle_date)
        self.campo_fecha = DateField(self.page, "Fecha")
        self.lbl_agenda = ft.Text(size=12, color=ft.Colors.OUTLINE)

        self.lbl_titulo = ft.Text("Nueva tarea")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        self.btn_eliminar = delete_button(self.confirm_delete)
        self.vista_form = ft.View(
            route=routes.TAREA,
            appbar=ft.AppBar(title=self.lbl_titulo, actions=[self.btn_eliminar]),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(spacing=10, controls=[
                        ft.Row([self.txt_titulo]),
                        self.fila_etapa,
                        self.sw_fecha,
                        self.campo_fecha.fila,
                        self.lbl_agenda,
                        ft.Row([self.txt_notas]),
                        self.adjuntos.control,
                        ft.Row([
                            self.btn_guardar,
                            ft.TextButton("Cancelar", icon=ft.Icons.CLOSE,
                                          on_click=lambda e: self.close()),
                        ]),
                    ])
                )
            ],
        )

    def _new_stage_dropdown(self, valor: int | None):  # propio
        """Dropdown nuevo cada vez (con las etapas que usa ESTE proyecto)."""
        self.dd_etapa = ft.Dropdown(
            label="Etapa", expand=True, value=str(valor) if valor else None,
            options=[ft.DropdownOption(key=str(e.id), text=e.nombre)
                     for e in ps.task_stages(self.proyecto)],
        )
        self.fila_etapa.controls = [self.dd_etapa]

    def _toggle_date(self, e=None):  # propio
        self.campo_fecha.fila.visible = bool(self.sw_fecha.value)
        if e is not None:
            self.page.update()

    def new(self):  # propio
        self.registro = None
        self.lbl_titulo.value = "Nueva tarea"
        self.btn_eliminar.visible = False
        self.txt_titulo.value = ""
        self.txt_titulo.error_text = None
        self.txt_notas.value = ""
        abierta = ps.first_open_stage(self.proyecto)
        self._new_stage_dropdown(abierta.id if abierta else None)
        self.sw_fecha.value = False
        self.sw_fecha.disabled = False
        self.campo_fecha.set_value(date.today())
        self.lbl_agenda.value = ""
        self.lbl_agenda.visible = False
        self.adjuntos.clear()
        self._toggle_date()
        self.page.navigate(routes.TAREA)

    @staticmethod
    def _get(tarea_id: int) -> Tarea | None:  # propio
        """La tarea con sus adjuntos ya cargados (la sesión se cierra al salir)."""
        with SessionLocal() as session:
            return session.get(Tarea, tarea_id, options=[selectinload(Tarea.adjuntos)])

    def open(self, t: Tarea):  # propio
        self.registro = self._get(t.id)
        t = self.registro
        self.adjuntos.load(t.adjuntos)
        self.lbl_titulo.value = "Tarea"
        self.btn_eliminar.visible = True
        self.txt_titulo.value = t.titulo
        self.txt_titulo.error_text = None
        self.txt_notas.value = t.notas or ""
        etapa = ps.stage_of(t, ps.task_stages(self.proyecto))
        self._new_stage_dropdown(etapa.id if etapa else None)
        self.sw_fecha.value = t.fecha is not None
        self.campo_fecha.set_value(t.fecha or date.today())
        # Lo que solo se edita en la Agenda
        extras = [x for x in (t.horario, t.frecuencia_label if t.recurrente else "") if x]
        self.lbl_agenda.value = (" · ".join(extras) + " — horario y frecuencia se editan "
                                 "en la Agenda.") if extras else ""
        self.lbl_agenda.visible = bool(extras)
        self.sw_fecha.disabled = t.recurrente  # una recurrente siempre lleva fecha
        self._toggle_date()
        self.page.navigate(routes.TAREA)

    def close(self):  # propio
        self.page.navigate(routes.BITACORA)

    def save(self, e=None):  # propio
        titulo = (self.txt_titulo.value or "").strip()
        if not titulo:
            self.txt_titulo.error_text = "Requerido"
            self.page.update()
            return
        fecha = self.campo_fecha.valor if self.sw_fecha.value else None
        notas = (self.txt_notas.value or "").strip() or None
        etapa_id = int(self.dd_etapa.value) if self.dd_etapa.value else None
        try:
            if self.registro is None:
                abierta = ps.first_open_stage(self.proyecto)
                t = Tarea.create(titulo=titulo, notas=notas, proyecto_id=self.proyecto.id,
                                 fecha=fecha, frecuencia="unica",
                                 etapa_id=abierta.id if abierta else etapa_id)
            else:
                t = Tarea.update(self.registro.id, titulo=titulo, notas=notas, fecha=fecha)
            self.adjuntos.apply(t.id)
            resultado = None
            if etapa_id and etapa_id != t.etapa_id:
                resultado = ps.move_task(t.id, etapa_id)  # marca hecha / reabre si toca
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return
        notify(self.page, "Tarea guardada" + (" · también en la Agenda" if fecha else ""))
        self.on_changed()
        self.close()
        if resultado == "hecha":
            from modulos.agenda.views.chismoso import ask_log_entry

            ask_log_entry(self.page, Tarea.get(t.id), on_registered=self.on_changed)

    def confirm_delete(self, e=None):  # propio
        t = self.registro

        def delete():  # propio
            if self._delete(t):
                self.close()

        confirm(self.page, "Eliminar tarea", f"¿Eliminar «{t.titulo}»?", delete)

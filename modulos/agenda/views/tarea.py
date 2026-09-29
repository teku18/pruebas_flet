"""
Formulario de una tarea (/agenda/tarea). Mismo patrón que Proyectos:
modos "nuevo" | "ver" | "editar".

  Proyecto:   opcional. "Sin proyecto" = tarea suelta (sacar a los perros)
  Fecha:      la próxima vez que toca
  Horario:    opcional; sin hora = todo el día
  Frecuencia: Una vez, Diario, Lunes a viernes, Cada semana, Cada mes

En modo "ver" aparece [✓ Marcar hecha] y, si es recurrente, su historial.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft

from core.ui import (
    DateField,
    TimeField,
    confirm,
    delete_button,
    dropdown_options,
    edit_button,
    notify,
    short_date,
)
from modulos.agenda import services
from modulos.agenda.models import FRECUENCIA_SELECTION, Cumplimiento, Tarea
from modulos.agenda.routes import BASE, TAREA
from modulos.agenda.views.chismoso import complete_task

SIN_PROYECTO = "0"  # clave de "Sin proyecto" en el desplegable


class TaskFormView:
    def __init__(self, page: ft.Page, on_saved):
        """on_saved(): refresca la pantalla de la Agenda al regresar."""
        self.page = page
        self.on_saved = on_saved
        self.registro: Tarea | None = None
        self.modo = "nuevo"
        self._build()

    # ==================================================================
    # Construcción
    # ==================================================================
    def _build(self):  # propio
        self.txt_titulo = ft.TextField(label="¿Qué hay que hacer?", max_length=150)
        self.dd_proyecto = ft.Dropdown(label="Proyecto", expand=True)
        self.campo_fecha = DateField(self.page, "Fecha")
        self.campo_inicio = TimeField(self.page, "Hora de inicio")
        self.campo_fin = TimeField(self.page, "Hora de fin")
        self.dd_frecuencia = ft.Dropdown(
            label="Se repite",
            options=dropdown_options(FRECUENCIA_SELECTION),
            value="unica",
            expand=True,
        )
        self.txt_notas = ft.TextField(label="Notas", multiline=True, min_lines=2, max_lines=6)

        # Solo en modo "ver"
        self.btn_hecha = ft.Button("Marcar hecha", icon=ft.Icons.CHECK, on_click=self.complete)
        self.col_historial = ft.Column(spacing=2)

        self.lbl_titulo_form = ft.Text("Nueva tarea")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista = ft.View(
            route=TAREA,
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.txt_titulo,
                            ft.Row([self.dd_proyecto]),
                            self.campo_fecha.fila,
                            self.campo_inicio.fila,
                            self.campo_fin.fila,
                            ft.Row([self.dd_frecuencia]),
                            self.txt_notas,
                            self.fila_botones,
                            self.btn_hecha,
                            self.col_historial,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _project_options(self, incluir_id: int | None = None):  # propio
        """
        Proyectos activos o en pausa (los terminados no reciben tareas nuevas),
        más el de la tarea aunque ya esté terminado, para no perderlo al editar.
        """
        from modulos.proyectos.models import Proyecto

        proyectos = [
            p for p in Proyecto.search_all()
            if p.estado in ("activo", "pausa") or p.id == incluir_id
        ]
        self.dd_proyecto.options = [ft.DropdownOption(key=SIN_PROYECTO, text="Sin proyecto")] + [
            ft.DropdownOption(key=str(p.id), text=p.nombre) for p in proyectos
        ]

    # ==================================================================
    # Modos
    # ==================================================================
    def _apply_mode(self):  # propio
        lectura = self.modo == "ver"
        self.txt_titulo.read_only = lectura
        self.txt_notas.read_only = lectura
        self.dd_proyecto.disabled = lectura
        self.dd_frecuencia.disabled = lectura
        self.campo_fecha.set_enabled(not lectura)
        self.campo_inicio.set_enabled(not lectura)
        self.campo_fin.set_enabled(not lectura)

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura
        pendiente = self.registro is not None and not self.registro.completada
        self.btn_hecha.visible = lectura and pendiente
        self.col_historial.visible = lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nueva tarea"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Tarea"
        else:
            self.lbl_titulo_form.value = "Editar tarea"
            self.btn_guardar.content = "Actualizar"

    def _fill(self, t: Tarea):  # propio
        self._project_options(t.proyecto_id)
        self.txt_titulo.value = t.titulo
        self.dd_proyecto.value = str(t.proyecto_id) if t.proyecto_id else SIN_PROYECTO
        self.campo_fecha.set_value(t.fecha)
        self.campo_inicio.set_value(t.hora_inicio)
        self.campo_fin.set_value(t.hora_fin)
        self.dd_frecuencia.value = t.frecuencia
        self.txt_notas.value = t.notas or ""
        self._fill_history(t)

    def _fill_history(self, t: Tarea):  # propio
        """Las últimas veces que la hiciste (útil para la renta: ¿ya pagué?)."""
        historial = Cumplimiento.search(Cumplimiento.tarea_id == t.id)[:6]
        if not historial:
            self.col_historial.controls = []
            return
        self.col_historial.controls = [
            ft.Text("Historial", size=16, weight=ft.FontWeight.BOLD),
            *[
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE, size=16, color=ft.Colors.GREEN),
                        ft.Text(
                            f"{short_date(c.hecho_en.date())}"
                            + ("" if c.hecho_en.date() == c.fecha_programada
                               else f"  (tocaba {short_date(c.fecha_programada)})"),
                            size=13,
                        ),
                    ],
                )
                for c in historial
            ],
        ]

    def clear_errors(self):  # propio
        self.txt_titulo.error_text = None
        self.campo_fin.txt.error_text = None

    def clear_form(self):  # propio
        self.clear_errors()
        self.registro = None
        self._project_options()
        self.txt_titulo.value = ""
        self.dd_proyecto.value = SIN_PROYECTO
        self.campo_fecha.set_value(date.today())
        self.campo_inicio.set_value(None)
        self.campo_fin.set_value(None)
        self.dd_frecuencia.value = "unica"
        self.txt_notas.value = ""
        self.col_historial.controls = []
        self.modo = "nuevo"
        self._apply_mode()

    # ==================================================================
    # Acciones
    # ==================================================================
    def new(self):  # propio
        self.clear_form()
        self.page.navigate(TAREA)

    def show(self, t: Tarea):  # propio
        self.clear_errors()
        self.registro = services.get_task(t.id)
        if self.registro is None:
            notify(self.page, "La tarea ya no existe")
            return
        self._fill(self.registro)
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(TAREA)

    def edit(self, e=None):  # propio
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            self.clear_errors()
            self.registro = services.get_task(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(BASE)

    def save(self, e=None):  # propio
        self.clear_errors()
        titulo = (self.txt_titulo.value or "").strip()
        if not titulo:
            self.txt_titulo.error_text = "Requerido"
            self.page.update()
            return
        inicio, fin = self.campo_inicio.valor, self.campo_fin.valor
        if fin and (not inicio or fin < inicio):
            self.campo_fin.txt.error_text = "Debe ser después del inicio"
            self.page.update()
            return

        frecuencia = self.dd_frecuencia.value or "unica"
        proyecto = self.dd_proyecto.value
        valores = dict(
            titulo=titulo,
            proyecto_id=int(proyecto) if proyecto and proyecto != SIN_PROYECTO else None,
            fecha=services.first_date(self.campo_fecha.valor, frecuencia),
            hora_inicio=inicio,
            hora_fin=fin,
            frecuencia=frecuencia,
            notas=(self.txt_notas.value or "").strip() or None,
        )
        try:
            if self.modo == "nuevo":
                Tarea.create(**valores)
            else:
                Tarea.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Tarea creada")
            self.on_saved()
            self.page.navigate(BASE)
        else:
            self.registro = services.get_task(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Tarea actualizada")
            self.page.update()

    def complete(self, e=None):  # propio
        def done():  # propio
            self.on_saved()
            self.clear_form()
            self.page.navigate(BASE)

        complete_task(self.page, self.registro, on_done=done)

    # ==================================================================
    # Eliminar
    # ==================================================================
    def confirm_delete(self, e=None):  # propio
        t = self.registro
        mensaje = f"¿Eliminar «{t.titulo}»?"
        if t.recurrente:
            mensaje += "\n\nTambién se borra su historial."

        def delete():  # propio
            try:
                Tarea.delete(t.id)
            except Exception as ex:  # noqa: BLE001
                notify(self.page, f"Error al eliminar: {ex}")
                return
            self.clear_form()
            notify(self.page, "Tarea eliminada")
            self.on_saved()
            self.page.navigate(BASE)

        confirm(self.page, "Eliminar tarea", mensaje, delete)

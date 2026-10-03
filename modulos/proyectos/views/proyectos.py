"""
Pantallas de Proyectos (cabecera de la bitácora):
  /proyectos                     -> Lista ☰ o Kanban ▥ (columnas = etapas), filtro por tipo
  /proyectos/proyecto            -> nuevo proyecto (desde el botón +)
  /proyectos/bitacora/proyecto   -> datos del proyecto abierto (desde el engrane)

Mismo patrón que Periodos: modos "nuevo" | "ver" | "editar".
Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft

from core.ui import (
    DateField,
    add_button,
    confirm,
    delete_button,
    dropdown_options,
    edit_button,
    icon_box,
    notify,
    short_date,
    swipe_to_delete,
)
from modulos.proyectos import routes
from modulos.proyectos.models import (
    TIPO_PROYECTO_SELECTION,
    EtapaProyecto,
    EtapaTarea,
    Proyecto,
)
from modulos.proyectos.services import (
    ProjectStats,
    all_stats,
    move_project,
    project_stats,
    projects_by_stage,
    set_task_stages,
    task_counts,
)
from modulos.proyectos.views.comun import (
    drag_handle,
    kanban_board,
    move_menu,
    stage_chip,
    view_toggle,
)

# Ícono y color de cada tipo (fijos: identifican el tipo de un vistazo)
ESTILO_TIPO = {
    "personal": (ft.Icons.PERSON, ft.Colors.BLUE),
    "familiar": (ft.Icons.FAMILY_RESTROOM, ft.Colors.PINK),
    "trabajo": (ft.Icons.WORK, ft.Colors.DEEP_PURPLE),
}


class ProjectsView:
    def __init__(self, page: ft.Page, on_open_project, on_open_settings):
        """
        on_open_project:  al tocar un proyecto (abre su bitácora)
        on_open_settings: engrane de la lista (Ajustes de Proyectos)
        """
        self.page = page
        self.on_open_project = on_open_project
        self.on_open_settings = on_open_settings
        self.registro: Proyecto | None = None
        self.modo = "nuevo"
        self.filtro: str | None = None  # None = todos los tipos
        self.vista_modo = "lista"       # "lista" | "kanban"
        self.ver_cerrados = False       # en la lista: ¿mostrar terminados/cancelados?
        self.etapas_tarea_elegidas: set[int] = set()  # chips del formulario

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista
    # ==================================================================
    def _build_list(self):  # propio
        self.fila_filtros = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        self._build_filters()

        self.lista = ft.ListView(expand=True, spacing=6, padding=ft.Padding.only(bottom=90))
        self.lbl_vacio = ft.Text("Aún no hay proyectos. Crea uno con el botón +.", italic=True)
        # El cuerpo cambia entre la lista y el tablero Kanban
        self.cuerpo = ft.Container(expand=True, content=self.lista)

        self.barra = ft.AppBar(title=ft.Text("Proyectos"))
        self.vista_lista = ft.View(
            route=routes.BASE,
            appbar=self.barra,
            floating_action_button=add_button("Nuevo proyecto", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        controls=[self.fila_filtros, self.lbl_vacio, self.cuerpo],
                    ),
                )
            ],
        )

    def _build_actions(self):  # propio
        self.barra.actions = [
            view_toggle(self.vista_modo, self.set_view_mode),
            ft.IconButton(ft.Icons.SETTINGS, tooltip="Ajustes de Proyectos",
                          on_click=lambda e: self.on_open_settings()),
        ]

    def set_view_mode(self, modo: str):  # propio
        self.vista_modo = modo
        self._build_filters()
        self.load()
        self.page.update()

    def _build_filters(self):  # propio
        """Chips: [Todos] [Personal] [Familiar] [Trabajo]."""
        opciones = [(None, "Todos")] + list(TIPO_PROYECTO_SELECTION.items())
        self.fila_filtros.controls = [
            ft.Chip(
                label=ft.Text(etiqueta),
                selected=self.filtro == clave,
                on_select=lambda e, c=clave: self.set_filter(c),
            )
            for clave, etiqueta in opciones
        ]
        if self.vista_modo == "lista":  # en el Kanban los cerrados ya tienen su columna
            self.fila_filtros.controls.append(ft.Chip(
                label=ft.Text("Cerrados"),
                leading=ft.Icon(ft.Icons.INVENTORY_2, size=16),
                show_checkmark=False,
                selected=self.ver_cerrados,
                on_select=self.toggle_closed,
            ))

    def toggle_closed(self, e=None):  # propio
        self.ver_cerrados = not self.ver_cerrados
        self._build_filters()
        self.load()
        self.page.update()

    def set_filter(self, tipo: str | None):  # propio
        self.filtro = tipo
        self._build_filters()
        self.load()
        self.page.update()

    def load(self):  # propio
        self._build_actions()
        proyectos = Proyecto.search_by_tipo(self.filtro)
        stats = all_stats()
        tareas = task_counts()
        if self.vista_modo == "kanban":
            self.lbl_vacio.visible = not proyectos
            self.cuerpo.content = kanban_board(
                "proyectos",
                projects_by_stage(proyectos),
                lambda p, etapa: self._card(p, stats.get(p.id, ProjectStats()),
                                            tareas.get(p.id, (0, 0))),
                self.move,
                vacio="Sin proyectos",
            )
        else:
            visibles = [p for p in proyectos if self.ver_cerrados or not p.cerrado]
            self.lista.controls = [
                self._row(p, stats.get(p.id, ProjectStats()), tareas.get(p.id, (0, 0)))
                for p in visibles
            ]
            ocultos = len(proyectos) - len(visibles)
            if ocultos:
                self.lista.controls.append(ft.TextButton(
                    f"Ver {ocultos} cerrado(s)", icon=ft.Icons.INVENTORY_2,
                    on_click=self.toggle_closed))
            self.cuerpo.content = self.lista
            self.lbl_vacio.visible = not visibles and not ocultos
        self.lbl_vacio.value = (
            "Aún no hay proyectos. Crea uno con el botón +."
            if self.filtro is None
            else "No hay proyectos de este tipo."
        )

    def move(self, proyecto_id: int, etapa_id: int):  # propio
        """Kanban: soltar en otra columna o "Mover a…"."""
        try:
            pro = move_project(proyecto_id, etapa_id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo mover: {ex}")
            return
        notify(self.page, f"«{pro.nombre}» → {pro.etapa_label}")
        self.load()
        self.page.update()

    @staticmethod
    def _footer(st: ProjectStats, tareas: tuple[int, int]) -> ft.Control:  # propio
        """Lo que más importa de un vistazo: estancado, o entradas y tareas."""
        hechas, total = tareas
        txt_tareas = f" · ✓ {hechas}/{total} tareas" if total else ""
        if st.estancado:
            return ft.Text(f"⚠ {st.dias_sin_avance} días sin avance{txt_tareas}", size=12,
                           color=ft.Colors.ORANGE)
        if st.entradas:
            texto = (f"{st.entradas} entrada{'s' if st.entradas > 1 else ''}"
                     f" · última {short_date(st.ultima)}")
        else:
            texto = "Sin entradas todavía"
        return ft.Text(texto + txt_tareas, size=12, color=ft.Colors.OUTLINE)

    @staticmethod
    def _name_row(pro: Proyecto, size: int = 16) -> ft.Row:  # propio
        """Nombre (+ estrella si es destacado)."""
        fila = [ft.Text(pro.nombre, size=size, weight=ft.FontWeight.W_500,
                        expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
        if pro.destacado:
            fila.append(ft.Icon(ft.Icons.STAR, size=size + 2, color=ft.Colors.AMBER))
        return ft.Row(fila, spacing=4)

    @staticmethod
    def _progress(tareas: tuple[int, int]) -> list[ft.Control]:  # propio
        hechas, total = tareas
        if not total:
            return []
        return [ft.ProgressBar(value=hechas / total, bar_height=4, border_radius=2)]

    def _card(self, pro: Proyecto, st: ProjectStats, tareas: tuple[int, int]) -> ft.Control:  # propio
        """Tarjeta del Kanban."""
        icono, color = ESTILO_TIPO.get(pro.tipo, (ft.Icons.FOLDER, ft.Colors.GREY))
        return ft.Container(
            border_radius=10,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.only(left=ft.BorderSide(4, color)),
            ink=True,
            on_click=lambda e, p=pro: self.on_open_project(p),
            padding=ft.Padding.only(left=4, top=4, bottom=8),
            content=ft.Row(
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    drag_handle("proyectos", pro.id, pro.nombre),
                    ft.Column(expand=True, spacing=3, controls=[
                        self._name_row(pro, 14),
                        ft.Row(spacing=4, controls=[
                            ft.Icon(icono, size=14, color=color),
                            ft.Text(f"{pro.tipo_label} · {st.duracion_texto}", size=11,
                                    color=ft.Colors.OUTLINE),
                        ]),
                        *self._progress(tareas),
                        self._footer(st, tareas),
                    ]),
                    move_menu(EtapaProyecto.search_all(), pro.etapa_id, self.move, pro.id),
                ],
            ),
        )

    def _row(self, pro: Proyecto, st: ProjectStats, tareas: tuple[int, int]) -> ft.Control:  # propio
        """Línea de la lista: tipo, nombre, etapa, duración, avance de tareas."""
        icono, color = ESTILO_TIPO.get(pro.tipo, (ft.Icons.FOLDER, ft.Colors.GREY))
        cantidad = st.entradas
        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=8, horizontal=8),
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ink=True,
            on_click=lambda e, p=pro: self.on_open_project(p),
            content=ft.Row(
                spacing=10,
                controls=[
                    icon_box(icono, color),
                    ft.Column(
                        expand=True,
                        spacing=3,
                        controls=[
                            self._name_row(pro),
                            ft.Row(spacing=6, controls=[
                                stage_chip(pro.etapa_label, pro.etapa.color),
                                ft.Text(f"{pro.tipo_label} · {st.duracion_texto}", size=12),
                            ]),
                            *self._progress(tareas),
                            self._footer(st, tareas),
                        ],
                    ),
                ],
            ),
        )
        return swipe_to_delete(
            self.page,
            key=f"proyecto-{pro.id}",
            contenido=linea,
            titulo="Eliminar proyecto",
            mensaje=self._delete_message(pro, cantidad),
            on_delete=lambda p=pro: self._delete(p),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        self.txt_nombre = ft.TextField(label="Nombre", max_length=100)
        self.fila_tipo = ft.Row()
        self.fila_estado = ft.Row()
        # Etapas de tarea que usa el proyecto (chips; ninguna = todas)
        self.fila_etapas_tarea = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.lbl_etapas_tarea = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self._new_dropdowns()
        self.campo_inicio = DateField(self.page, "Fecha de inicio")
        # Fecha fin: solo se ve si la etapa es cerrada (terminada/cancelada)
        self.campo_fin = DateField(self.page, "Fecha de fin")
        self.sw_destacado = ft.Switch(label="Destacado (para el resumen del año)")
        # Ficha en modo "ver": duración, entradas, hitos, última actividad
        self.lbl_resumen = ft.Text(size=13, color=ft.Colors.OUTLINE)
        self.txt_descripcion = ft.TextField(
            label="Descripción", multiline=True, min_lines=2, max_lines=6
        )

        self.lbl_titulo_form = ft.Text("Nuevo proyecto")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.PROYECTO,  # el módulo la ajusta: PROYECTO o BITACORA_PROYECTO
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
                            self.txt_nombre,
                            self.fila_tipo,
                            self.fila_estado,
                            self.campo_inicio.fila,
                            self.campo_fin.fila,
                            self.sw_destacado,
                            self.txt_descripcion,
                            ft.Text("Etapas de tareas", size=16, weight=ft.FontWeight.BOLD),
                            self.lbl_etapas_tarea,
                            self.fila_etapas_tarea,
                            self.lbl_resumen,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _new_dropdowns(self):  # propio
        """Dropdowns nuevos (mismo truco que en Movimientos para que se vean vacíos)."""
        self.dd_tipo = ft.Dropdown(
            label="Tipo", options=dropdown_options(TIPO_PROYECTO_SELECTION), expand=True
        )
        etapas = EtapaProyecto.search_all()
        defecto = EtapaProyecto.default()
        self.etapas_proyecto = {e.id: e for e in etapas}
        self.dd_estado = ft.Dropdown(
            label="Etapa",
            options=[ft.DropdownOption(key=str(e.id), text=e.nombre) for e in etapas],
            value=str(defecto.id) if defecto else None,
            expand=True,
            on_select=self._on_estado,
        )
        self.fila_tipo.controls = [self.dd_tipo]
        self.fila_estado.controls = [self.dd_estado]

    def _apply_mode(self):  # propio
        lectura = self.modo == "ver"
        self.txt_nombre.read_only = lectura
        self.txt_descripcion.read_only = lectura
        self.dd_tipo.disabled = lectura
        self.dd_estado.disabled = lectura
        self.campo_inicio.set_enabled(not lectura)
        self.campo_fin.set_enabled(not lectura)
        self.sw_destacado.disabled = lectura
        self._toggle_fin()
        self._render_task_stages()
        self.lbl_resumen.visible = lectura

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo proyecto"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Proyecto"
        else:
            self.lbl_titulo_form.value = "Editar proyecto"
            self.btn_guardar.content = "Actualizar"

    def _closed_stage(self) -> bool:  # propio
        """¿La etapa elegida en el formulario es cerrada?"""
        etapa = self.etapas_proyecto.get(int(self.dd_estado.value)) if self.dd_estado.value else None
        return bool(etapa and etapa.cerrada)

    def _toggle_fin(self):  # propio
        self.campo_fin.fila.visible = self._closed_stage()

    # --- Etapas de tareas (chips) --------------------------------------
    def _render_task_stages(self):  # propio
        lectura = self.modo == "ver"
        etapas = EtapaTarea.search_all()
        elegidas = self.etapas_tarea_elegidas
        self.lbl_etapas_tarea.value = (
            "Columnas del Kanban de tareas de este proyecto. "
            + ("Usa todas." if not elegidas else f"Usa {len(elegidas)} de {len(etapas)}.")
        )
        self.fila_etapas_tarea.controls = [
            ft.Chip(
                label=ft.Text(e.nombre),
                leading=ft.Container(width=10, height=10, border_radius=5, bgcolor=e.color),
                show_checkmark=False,
                selected=e.id in elegidas or not elegidas,
                disabled=lectura,
                on_select=lambda ev, i=e.id: self._toggle_task_stage(i),
            )
            for e in etapas
        ]

    def _toggle_task_stage(self, etapa_id: int):  # propio
        todas = {e.id for e in EtapaTarea.search_all()}
        elegidas = set(self.etapas_tarea_elegidas or todas)  # vacío = todas marcadas
        elegidas ^= {etapa_id}
        # Todas marcadas (o ninguna) = "usa todas": se guarda vacío
        self.etapas_tarea_elegidas = set() if elegidas in (todas, set()) else elegidas
        self._render_task_stages()
        self.page.update()

    def _on_estado(self, e=None):  # propio
        """Al pasar a una etapa cerrada aparece la fecha fin (propone hoy)."""
        if self._closed_stage() and not (self.registro and self.registro.fecha_fin):
            self.campo_fin.set_value(date.today())
        self._toggle_fin()
        self.page.update()

    def _fill(self, pro: Proyecto):  # propio
        self.txt_nombre.value = pro.nombre
        self.dd_tipo.value = pro.tipo
        self.dd_estado.value = str(pro.etapa_id)
        self.etapas_tarea_elegidas = {e.id for e in pro.etapas_tarea}
        self.campo_inicio.set_value(pro.fecha_inicio)
        self.campo_fin.set_value(pro.fecha_fin or date.today())
        self.sw_destacado.value = pro.destacado
        self.txt_descripcion.value = pro.descripcion or ""
        self.lbl_resumen.value = self._summary_text(pro)

    @staticmethod
    def _pending_tasks(proyecto_id: int) -> int:  # propio
        """Las tareas viven en la Agenda; Proyectos solo pregunta cuántas hay."""
        from modulos.agenda.services import pending_by_project

        return pending_by_project(proyecto_id)

    def _summary_text(self, pro: Proyecto) -> str:  # propio
        st = project_stats(pro)
        verbo = "Duró" if pro.cerrado else "Lleva"
        partes = [f"{verbo} {st.duracion_texto}"]
        partes.append("1 entrada" if st.entradas == 1 else f"{st.entradas} entradas")
        if st.hitos:
            partes.append("1 hito" if st.hitos == 1 else f"{st.hitos} hitos")
        tareas = self._pending_tasks(pro.id)
        if tareas:
            partes.append("1 tarea pendiente" if tareas == 1 else f"{tareas} tareas pendientes")
        texto = " · ".join(partes)
        if not pro.cerrado and st.ultima:
            dias = st.dias_sin_avance
            cuando = "hoy" if dias == 0 else "ayer" if dias == 1 else f"hace {dias} días"
            texto += f"\nÚltimo avance: {cuando}"
        return texto

    def clear_errors(self):  # propio
        self.txt_nombre.error_text = None
        self.dd_tipo.error_text = None
        self.dd_estado.error_text = None

    def clear_form(self):  # propio
        self.clear_errors()
        self.registro = None
        self._new_dropdowns()
        # Si hay un filtro activo, el proyecto nuevo propone ese tipo
        self.dd_tipo.value = self.filtro
        self.txt_nombre.value = ""
        self.txt_descripcion.value = ""
        self.campo_inicio.set_value(date.today())
        self.campo_fin.set_value(date.today())
        self.sw_destacado.value = False
        self.etapas_tarea_elegidas = set()
        self.modo = "nuevo"
        self._apply_mode()

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        self.clear_form()
        self.page.navigate(routes.PROYECTO)

    def show(self, pro: Proyecto):  # propio
        """Engrane (desde la bitácora): datos del proyecto en solo lectura."""
        self.clear_errors()
        self.registro = Proyecto.get(pro.id)
        self._new_dropdowns()  # por si cambiaron las etapas en Ajustes
        self._fill(self.registro)
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.BITACORA_PROYECTO)

    def edit(self, e=None):  # propio
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            self.clear_errors()
            self.registro = Proyecto.get(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(routes.BASE)

    def save(self, e=None):  # propio
        self.clear_errors()
        nombre = (self.txt_nombre.value or "").strip()
        faltantes = False
        if not nombre:
            self.txt_nombre.error_text = "Requerido"
            faltantes = True
        if not self.dd_tipo.value:
            self.dd_tipo.error_text = "Requerido"
            faltantes = True
        if faltantes:
            self.page.update()
            return

        if not self.dd_estado.value:
            self.dd_estado.error_text = "Requerido"
            self.page.update()
            return
        valores = dict(
            nombre=nombre,
            tipo=self.dd_tipo.value,
            etapa_id=int(self.dd_estado.value),
            fecha_inicio=self.campo_inicio.valor,
            # El modelo la limpia si la etapa no es cerrada
            fecha_fin=self.campo_fin.valor if self._closed_stage() else None,
            destacado=bool(self.sw_destacado.value),
            descripcion=(self.txt_descripcion.value or "").strip() or None,
        )
        try:
            if self.modo == "nuevo":
                nuevo = Proyecto.create(**valores)
                set_task_stages(nuevo.id, sorted(self.etapas_tarea_elegidas))
            else:
                set_task_stages(self.registro.id, sorted(self.etapas_tarea_elegidas))
                self.registro = Proyecto.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Proyecto creado")
            self.on_open_project(nuevo)  # directo a su bitácora
        else:
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Proyecto actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, pro: Proyecto, cantidad: int) -> str:  # propio
        mensaje = f"¿Seguro que deseas eliminar el proyecto «{pro.nombre}»?"
        if cantidad:
            mensaje += f"\n\nTambién se eliminarán sus {cantidad} entrada(s) y sus adjuntos."
        tareas = self._pending_tasks(pro.id)
        if tareas:
            mensaje += f"\n\nY sus {tareas} tarea(s) de la Agenda."
        return mensaje

    def confirm_delete(self, e=None):  # propio
        pro = self.registro
        cantidad = Proyecto.entries_summary().get(pro.id, (0, None))[0]

        def delete():  # propio
            if self._delete(pro):
                self.clear_form()
                self.page.navigate(routes.BASE)

        confirm(self.page, "Eliminar proyecto", self._delete_message(pro, cantidad), delete)

    def _delete(self, pro: Proyecto) -> bool:  # propio
        try:
            Proyecto.delete(pro.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Proyecto eliminado")
        self.page.update()
        return True

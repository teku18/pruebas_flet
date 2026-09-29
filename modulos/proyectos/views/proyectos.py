"""
Pantallas de Proyectos (cabecera de la bitácora):
  /proyectos                     -> lista con filtro por tipo
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
    ESTADO_PROYECTO_SELECTION,
    ESTADOS_CERRADOS,
    TIPO_PROYECTO_SELECTION,
    Proyecto,
)
from modulos.proyectos.services import ProjectStats, all_stats, project_stats

# Ícono y color de cada tipo (fijos: identifican el tipo de un vistazo)
ESTILO_TIPO = {
    "personal": (ft.Icons.PERSON, ft.Colors.BLUE),
    "familiar": (ft.Icons.FAMILY_RESTROOM, ft.Colors.PINK),
    "trabajo": (ft.Icons.WORK, ft.Colors.DEEP_PURPLE),
}


class ProjectsView:
    def __init__(self, page: ft.Page, on_open_project):
        """on_open_project: función que se llama al tocar un proyecto (abre su bitácora)."""
        self.page = page
        self.on_open_project = on_open_project
        self.registro: Proyecto | None = None
        self.modo = "nuevo"
        self.filtro: str | None = None  # None = todos los tipos

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista
    # ==================================================================
    def _build_list(self):  # propio
        self.fila_filtros = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        self._build_filters()

        self.lista = ft.ListView(expand=True, spacing=4, padding=ft.Padding.only(bottom=90))
        self.lbl_vacio = ft.Text("Aún no hay proyectos. Crea uno con el botón +.", italic=True)

        self.vista_lista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(title=ft.Text("Proyectos")),
            floating_action_button=add_button("Nuevo proyecto", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        controls=[self.fila_filtros, self.lbl_vacio, self.lista],
                    ),
                )
            ],
        )

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

    def set_filter(self, tipo: str | None):  # propio
        self.filtro = tipo
        self._build_filters()
        self.load()
        self.page.update()

    def load(self):  # propio
        proyectos = Proyecto.search_by_tipo(self.filtro)
        stats = all_stats()
        self.lista.controls = [self._row(p, stats.get(p.id, ProjectStats())) for p in proyectos]
        self.lbl_vacio.visible = not proyectos
        self.lbl_vacio.value = (
            "Aún no hay proyectos. Crea uno con el botón +."
            if self.filtro is None
            else "No hay proyectos de este tipo."
        )

    def _row(self, pro: Proyecto, st: ProjectStats) -> ft.Control:  # propio
        icono, color = ESTILO_TIPO.get(pro.tipo, (ft.Icons.FOLDER, ft.Colors.GREY))
        cantidad = st.entradas
        if cantidad:
            texto_entradas = "1 entrada" if cantidad == 1 else f"{cantidad} entradas"
            texto_entradas += f" · última {short_date(st.ultima)}"
        else:
            texto_entradas = "Sin entradas todavía"

        # Nombre (+ estrella si es destacado)
        fila_nombre = [ft.Text(pro.nombre, size=16, weight=ft.FontWeight.W_500,
                               expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)]
        if pro.destacado:
            fila_nombre.append(ft.Icon(ft.Icons.STAR, size=18, color=ft.Colors.AMBER))

        # Tercera línea: lo que más importa ver de un vistazo
        if st.estancado:
            pie = ft.Text(f"⚠ {st.dias_sin_avance} días sin avance", size=12,
                          color=ft.Colors.ORANGE)
        else:
            pie = ft.Text(texto_entradas, size=12, color=ft.Colors.OUTLINE)

        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,
            on_click=lambda e, p=pro: self.on_open_project(p),
            content=ft.Row(
                spacing=10,
                controls=[
                    icon_box(icono, color),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Row(fila_nombre, spacing=4),
                            ft.Text(
                                f"{pro.tipo_label} · {pro.estado_label} · {st.duracion_texto}",
                                size=12,
                            ),
                            pie,
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
        self._new_dropdowns()
        self.campo_inicio = DateField(self.page, "Fecha de inicio")
        # Fecha fin: solo se ve si el estado es Terminado o Cancelado
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
        self.dd_estado = ft.Dropdown(
            label="Estado",
            options=dropdown_options(ESTADO_PROYECTO_SELECTION),
            value="activo",
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

    def _toggle_fin(self):  # propio
        self.campo_fin.fila.visible = self.dd_estado.value in ESTADOS_CERRADOS

    def _on_estado(self, e=None):  # propio
        """Al pasar a Terminado/Cancelado aparece la fecha fin (propone hoy)."""
        if self.dd_estado.value in ESTADOS_CERRADOS and not (self.registro and self.registro.fecha_fin):
            self.campo_fin.set_value(date.today())
        self._toggle_fin()
        self.page.update()

    def _fill(self, pro: Proyecto):  # propio
        self.txt_nombre.value = pro.nombre
        self.dd_tipo.value = pro.tipo
        self.dd_estado.value = pro.estado
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

        estado = self.dd_estado.value or "activo"
        valores = dict(
            nombre=nombre,
            tipo=self.dd_tipo.value,
            estado=estado,
            fecha_inicio=self.campo_inicio.valor,
            # El modelo la limpia si el estado no es Terminado/Cancelado
            fecha_fin=self.campo_fin.valor if estado in ESTADOS_CERRADOS else None,
            destacado=bool(self.sw_destacado.value),
            descripcion=(self.txt_descripcion.value or "").strip() or None,
        )
        try:
            if self.modo == "nuevo":
                nuevo = Proyecto.create(**valores)
            else:
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

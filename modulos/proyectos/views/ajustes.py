"""
Ajustes de Proyectos (/proyectos/ajustes), desde el engrane de la lista:

  [Etapas de proyecto]  columnas del Kanban de proyectos
  [Etapas de tarea]     columnas del Kanban de tareas
  [Tipos de entrada]    tipos de la bitácora (Avance, Hito, …)

Cada línea: tocar = editar · ▲▼ = cambiar el orden (secuencia) ·
deslizar = borrar (solo si nadie la usa, como ondelete="restrict").

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, notify, swipe_to_delete
from modulos.proyectos import routes
from modulos.proyectos.models import EtapaProyecto, EtapaTarea, TipoEntrada
from modulos.proyectos.views.comun import catalog_dialog, icon_of

PESTANAS = [
    # (modelo, texto de la pestaña, botón +, qué usa el catálogo)
    (EtapaProyecto, "Etapas de proyecto", "Nueva etapa", "proyecto"),
    (EtapaTarea, "Etapas de tarea", "Nueva etapa", "tarea"),
    (TipoEntrada, "Tipos de entrada", "Nuevo tipo", "entrada"),
]

AYUDA = {
    EtapaProyecto: "Las columnas del Kanban de proyectos. Cada proyecto está en una.",
    EtapaTarea: "Las columnas del Kanban de tareas. En cada proyecto (engrane → "
                "Etapas de tareas) eliges cuáles usa; si no eliges, usa todas.",
    TipoEntrada: "Los tipos de las entradas de la bitácora. Los hitos arman la línea "
                 "de tiempo y el resumen del año.",
}


class ProjectSettingsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.indice = 0  # pestaña elegida

        self.fila_pestanas = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        self.lbl_ayuda = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.lista = ft.ListView(expand=True, spacing=4, padding=ft.Padding.only(bottom=90))
        self.fab = add_button("Nueva etapa", self.new)
        self.vista = ft.View(
            route=routes.AJUSTES,
            appbar=ft.AppBar(title=ft.Text("Ajustes de Proyectos")),
            floating_action_button=self.fab,
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[
                        self.fila_pestanas, self.lbl_ayuda, self.lista,
                    ]),
                )
            ],
        )

    @property
    def modelo(self):  # propio
        return PESTANAS[self.indice][0]

    def set_tab(self, indice: int):  # propio
        self.indice = indice
        self.load()
        self.page.update()

    def load(self):  # propio
        self.fila_pestanas.controls = [
            ft.Chip(label=ft.Text(texto), selected=i == self.indice,
                    on_select=lambda e, n=i: self.set_tab(n))
            for i, (_, texto, _, _) in enumerate(PESTANAS)
        ]
        self.fab.content = PESTANAS[self.indice][2]
        self.lbl_ayuda.value = AYUDA[self.modelo] + " Desliza a la izquierda para borrar."
        usos = self.modelo.usage_count()
        registros = self.modelo.search_all()
        self.lista.controls = [
            self._row(r, usos.get(r.id, 0), i == 0, i == len(registros) - 1)
            for i, r in enumerate(registros)
        ]

    # ------------------------------------------------------------------
    def _detail(self, r, usos: int) -> str:  # propio
        que = PESTANAS[self.indice][3]
        if que == "proyecto":
            partes = [r.clase_label, "1 proyecto" if usos == 1 else f"{usos} proyectos"]
        elif que == "tarea":
            partes = (["Cuenta como hecha"] if r.cerrada else []) + [
                "1 tarea" if usos == 1 else f"{usos} tareas"]
        else:
            partes = (["Hito ★"] if r.es_hito else []) + [
                "1 entrada" if usos == 1 else f"{usos} entradas"]
        return " · ".join(partes)

    def _row(self, r, usos: int, primero: bool, ultimo: bool) -> ft.Control:  # propio
        if isinstance(r, TipoEntrada):
            marca = ft.Container(width=36, height=36, border_radius=8,
                                 bgcolor=ft.Colors.with_opacity(0.18, r.color),
                                 alignment=ft.Alignment.CENTER,
                                 content=ft.Icon(icon_of(r.icono), color=r.color, size=20))
        else:
            marca = ft.Container(width=36, height=36, border_radius=8,
                                 bgcolor=ft.Colors.with_opacity(0.18, r.color),
                                 alignment=ft.Alignment.CENTER,
                                 content=ft.Container(width=14, height=14, border_radius=7,
                                                      bgcolor=r.color))
        linea = ft.Container(
            padding=ft.Padding.only(left=4, top=4, bottom=4),
            border_radius=8,
            ink=True,
            on_click=lambda e, x=r: self.edit(x),
            content=ft.Row(spacing=10, controls=[
                marca,
                ft.Column(expand=True, spacing=0, controls=[
                    ft.Text(r.nombre, size=16, weight=ft.FontWeight.W_500),
                    ft.Text(self._detail(r, usos), size=12, color=ft.Colors.OUTLINE),
                ]),
                ft.IconButton(ft.Icons.ARROW_UPWARD, tooltip="Subir", disabled=primero,
                              on_click=lambda e, x=r: self.move(x, -1)),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, tooltip="Bajar", disabled=ultimo,
                              on_click=lambda e, x=r: self.move(x, +1)),
            ]),
        )
        if usos:
            return linea  # en uso: no se puede borrar, sin deslizar
        return swipe_to_delete(
            self.page,
            key=f"{self.modelo.__tablename__}-{r.id}",
            contenido=linea,
            titulo="Eliminar",
            mensaje=f"¿Eliminar «{r.nombre}»?",
            on_delete=lambda x=r: self._delete(x),
        )

    # ------------------------------------------------------------------
    def _after_save(self, r):  # propio
        self.load()
        notify(self.page, f"«{r.nombre}» guardado")
        self.page.update()

    def new(self, e=None):  # propio
        catalog_dialog(self.page, self.modelo, self._after_save)

    def edit(self, r):  # propio
        catalog_dialog(self.page, self.modelo, self._after_save, r)

    def move(self, r, paso: int):  # propio
        self.modelo.move(r.id, paso)
        self.load()
        self.page.update()

    def _delete(self, r):  # propio
        try:
            self.modelo.delete(r.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo eliminar: {ex}")
        self.load()
        self.page.update()

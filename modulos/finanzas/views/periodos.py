"""
Pantallas de Periodos (cabecera de los movimientos):
  /finanzas                      -> lista de periodos
  /finanzas/periodo              -> nuevo periodo (desde el botón +)
  /finanzas/movimientos/periodo  -> datos del periodo abierto (desde el engrane)

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]

Los métodos marcados con  # propio  son nuestros; lo demás (page.update,
page.navigate, controles ft.*) viene de Flet.
"""
import calendar
from datetime import date

import flet as ft

from core.ui import (
    DateField,
    confirm,
    delete_button,
    edit_button,
    icon_box,
    notify,
    add_button,
    short_date,
    swipe_to_delete,
)
from modulos.finanzas import routes
from modulos.finanzas.models import Periodo


class PeriodsView:
    def __init__(self, page: ft.Page, on_open_period):
        """
        on_open_period: función que se llama al tocar un periodo
        (la pantalla de movimientos se encarga de mostrarlo).
        """
        self.page = page
        self.on_open_period = on_open_period
        self.registro: Periodo | None = None  # periodo mostrado en el formulario
        self.modo = "nuevo"                   # "nuevo" | "ver" | "editar"

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista
    # ==================================================================
    def _build_list(self):  # propio
        self.lista = ft.ListView(
            expand=True,
            spacing=4,
            padding=ft.Padding.only(bottom=90),  # espacio para el botón +
        )
        self.lbl_vacio = ft.Text(
            "Aún no hay periodos. Crea uno con el botón +.", italic=True
        )

        self.vista_lista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(title=ft.Text("Finanzas · Periodos")),
            floating_action_button=add_button("Nuevo periodo", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_vacio, self.lista]),
                )
            ],
        )

    def load(self):  # propio
        periodos = Periodo.search_all()
        cantidades = Periodo.count_movements()
        self.lista.controls = [self._row(p, cantidades.get(p.id, 0)) for p in periodos]
        self.lbl_vacio.visible = not periodos

    def _row(self, per: Periodo, cantidad: int) -> ft.Control:  # propio
        """Una línea de la lista de periodos. Al tocarla se abre el periodo."""
        texto_cantidad = "1 movimiento" if cantidad == 1 else f"{cantidad} movimientos"
        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,  # efecto al tocar
            on_click=lambda e, p=per: self.on_open_period(p),
            content=ft.Row(
                spacing=10,
                controls=[
                    # PRIMARY: toma el color del tema elegido en Configuración
                    icon_box(ft.Icons.CALENDAR_MONTH, ft.Colors.PRIMARY),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(per.nombre, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{short_date(per.fecha_inicio)} – {short_date(per.fecha_fin)}",
                                size=12,
                            ),
                            ft.Text(texto_cantidad, size=12, color=ft.Colors.OUTLINE),
                        ],
                    ),
                ],
            ),
        )
        # ◄── deslizar a la izquierda: eliminar (con confirmación), igual que movimientos
        return swipe_to_delete(
            self.page,
            key=f"periodo-{per.id}",
            contenido=linea,
            titulo="Eliminar periodo",
            mensaje=self._delete_message(per, cantidad),
            on_delete=lambda p=per: self._delete(p),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        self.txt_nombre = ft.TextField(label="Nombre", max_length=100)
        self.campo_inicio = DateField(self.page, "Fecha inicio")
        self.campo_fin = DateField(self.page, "Fecha fin")

        self.lbl_titulo_form = ft.Text("Nuevo periodo")  # va en la barra superior
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        # Lápiz y bote en la barra superior (solo en modo "ver")
        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.PERIODO,  # el módulo la ajusta: PERIODO o MOVIMIENTOS_PERIODO
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
                            self.campo_inicio.fila,
                            self.campo_fin.fila,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _apply_mode(self):  # propio
        """Ajusta campos, botones y título según self.modo."""
        lectura = self.modo == "ver"

        self.txt_nombre.read_only = lectura
        self.campo_inicio.set_enabled(not lectura)
        self.campo_fin.set_enabled(not lectura)

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo periodo"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Periodo"
        else:
            self.lbl_titulo_form.value = "Editar periodo"
            self.btn_guardar.content = "Actualizar"

    def _fill(self, per: Periodo):  # propio
        """Pasa los datos del registro a los campos."""
        self.txt_nombre.value = per.nombre
        self.campo_inicio.set_value(per.fecha_inicio)
        self.campo_fin.set_value(per.fecha_fin)

    def clear_errors(self):  # propio
        self.txt_nombre.error_text = None
        self.campo_fin.txt.error_text = None

    def clear_form(self):  # propio
        """Por defecto propone el mes actual completo."""
        self.clear_errors()
        hoy = date.today()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        self.txt_nombre.value = ""
        self.campo_inicio.set_value(hoy.replace(day=1))
        self.campo_fin.set_value(hoy.replace(day=ultimo_dia))
        self.registro = None
        self.modo = "nuevo"
        self._apply_mode()

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        """Botón +: abre el formulario de periodo vacío."""
        self.clear_form()
        self.page.navigate(routes.PERIODO)

    def show(self, per: Periodo):  # propio
        """Engrane (desde movimientos): muestra el periodo en solo lectura."""
        self.clear_errors()
        self.registro = Periodo.get(per.id)  # datos frescos de la BD
        self._fill(self.registro)
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.MOVIMIENTOS_PERIODO)

    def edit(self, e=None):  # propio
        """Lápiz: habilita los campos del periodo mostrado."""
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            # Descarta los cambios: vuelve a leer el registro y regresa a "ver"
            self.clear_errors()
            self.registro = Periodo.get(self.registro.id)
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
        if self.campo_fin.valor < self.campo_inicio.valor:
            self.campo_fin.txt.error_text = "No puede ser anterior a la fecha inicio"
            faltantes = True
        if faltantes:
            self.page.update()
            return

        valores = dict(
            nombre=nombre,
            fecha_inicio=self.campo_inicio.valor,
            fecha_fin=self.campo_fin.valor,
        )
        try:
            if self.modo == "nuevo":
                Periodo.create(**valores)
            else:
                self.registro = Periodo.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Periodo guardado")
            self.page.navigate(routes.BASE)  # regresa a la lista de periodos
        else:
            # Se queda en el registro, ahora en solo lectura
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Periodo actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, per: Periodo, cantidad: int) -> str:  # propio
        mensaje = f"¿Seguro que deseas eliminar el periodo «{per.nombre}»?"
        if cantidad:
            mensaje += f"\n\nTambién se eliminarán sus {cantidad} movimiento(s)."
        return mensaje

    def confirm_delete(self, e=None):  # propio
        """Bote de la barra: elimina el periodo mostrado, con confirmación."""
        per = self.registro
        cantidad = Periodo.count_movements().get(per.id, 0)

        def delete():  # propio
            if self._delete(per):
                self.clear_form()
                self.page.navigate(routes.BASE)  # el periodo ya no existe: a la lista

        confirm(self.page, "Eliminar periodo", self._delete_message(per, cantidad), delete)

    def _delete(self, per: Periodo) -> bool:  # propio
        """Borra el periodo (y sus movimientos) y refresca la lista."""
        try:
            Periodo.delete(per.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Periodo eliminado")
        self.page.update()
        return True

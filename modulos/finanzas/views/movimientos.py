"""
Pantallas de Movimientos (detalle de un periodo):
  /finanzas/movimientos -> lista de movimientos del periodo abierto
  /finanzas/movimiento  -> un movimiento: nuevo, ver (solo lectura) o editar

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]

Los métodos marcados con  # propio  son nuestros; lo demás (page.update,
page.navigate, controles ft.*) viene de Flet.
"""
from datetime import date

import flet as ft

from core.ui import (
    MESES,
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
from modulos.finanzas import routes
from modulos.finanzas.models import (
    INVERSION_SELECTION,
    PLATAFORMA_SELECTION,
    TIPO_SELECTION,
    Movimiento,
    Periodo,
)

# Ícono y color de cada tipo de movimiento
# (colores fijos a propósito: significan algo, no dependen del tema)
ESTILO_TIPO = {
    "deposito": (ft.Icons.SAVINGS, ft.Colors.GREEN),
    "retiro": (ft.Icons.ARROW_OUTWARD, ft.Colors.ORANGE),
    "rendimiento": (ft.Icons.TRENDING_UP, ft.Colors.TEAL),
}


class MovementsView:
    def __init__(self, page: ft.Page, on_show_period):
        """
        on_show_period: función que se llama al tocar el engrane
        (la pantalla de periodos se encarga de mostrar su detalle).
        """
        self.page = page
        self.on_show_period = on_show_period
        self.periodo: Periodo | None = None      # periodo abierto
        self.registro: Movimiento | None = None  # movimiento mostrado en el formulario
        self.modo = "nuevo"                      # "nuevo" | "ver" | "editar"

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista
    # ==================================================================
    def _build_list(self):  # propio
        # ListView: lista con scroll, ideal para muchos registros
        self.lista = ft.ListView(
            expand=True,
            spacing=4,
            # Espacio al final para que el botón + no tape el último registro
            padding=ft.Padding.only(bottom=90),
        )
        self.lbl_vacio = ft.Text("Este periodo aún no tiene movimientos", italic=True)
        self.lbl_titulo_lista = ft.Text("Movimientos")  # nombre del periodo

        self.vista_lista = ft.View(
            route=routes.MOVIMIENTOS,
            appbar=ft.AppBar(
                title=self.lbl_titulo_lista,
                actions=[
                    # Engrane: ver los datos del periodo
                    ft.IconButton(
                        ft.Icons.SETTINGS,
                        tooltip="Datos del periodo",
                        on_click=lambda e: self.on_show_period(self.periodo),
                    ),
                ],
            ),
            floating_action_button=add_button("Nuevo movimiento", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_vacio, self.lista]),
                )
            ],
        )

    def open_period(self, periodo: Periodo):  # propio
        """Lo llama la pantalla de Periodos al tocar una línea."""
        self.periodo = periodo
        self.page.navigate(routes.MOVIMIENTOS)

    def load(self):  # propio
        # Se relee el periodo por si se editó (nombre o fechas) desde su detalle
        self.periodo = Periodo.get(self.periodo.id)
        if self.periodo is None:  # se eliminó
            return
        self.lbl_titulo_lista.value = self.periodo.nombre
        movimientos = Movimiento.search_by_period(self.periodo.id)
        self.lista.controls = [self._row(m) for m in movimientos]
        self.lbl_vacio.visible = not movimientos

    def _row(self, m: Movimiento) -> ft.Control:  # propio
        """Una línea de la lista, al estilo de la imagen de referencia."""
        icono, color = ESTILO_TIPO.get(m.tipo, (ft.Icons.RECEIPT_LONG, ft.Colors.GREY))

        subtitulo = m.inversion_label
        if m.comentarios:
            subtitulo += f" · {m.comentarios}"

        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,  # efecto al tocar
            on_click=lambda e, mov=m: self.show(mov),  # tocar la línea -> ver detalle
            content=ft.Row(
                spacing=10,
                controls=[
                    # Fecha: mes arriba, día abajo
                    ft.Column(
                        width=36,
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(MESES[m.fecha.month - 1], size=12),
                            ft.Text(str(m.fecha.day), size=16),
                        ],
                    ),
                    icon_box(icono, color),
                    # Plataforma + inversión/comentarios (ocupa el espacio libre)
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(m.plataforma_label, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(
                                subtitulo,
                                size=12,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    # Tipo y monto a la derecha, con el color del tipo
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Text(m.tipo_label.lower(), size=12, color=color),
                            ft.Text(f"${m.monto:,.2f}", size=15, color=color),
                        ],
                    ),
                ],
            ),
        )
        # ◄── deslizar a la izquierda: eliminar (con confirmación)
        return swipe_to_delete(
            self.page,
            key=f"movimiento-{m.id}",
            contenido=linea,
            titulo="Eliminar movimiento",
            mensaje=self._delete_message(m),
            on_delete=lambda mov=m: self._delete(mov),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        # Filas que contienen los desplegables (se rellenan en _new_dropdowns)
        self.fila_inversion = ft.Row()
        self.fila_plataforma = ft.Row()
        self.fila_tipo = ft.Row()
        self._new_dropdowns()

        self.txt_monto = ft.TextField(
            label="Monto",
            prefix="$ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
        )
        self.campo_fecha = DateField(self.page, "Fecha")
        self.txt_comentarios = ft.TextField(label="Comentarios", max_length=255)

        self.lbl_titulo_form = ft.Text("Nuevo movimiento")  # va en la barra superior
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        # Lápiz y bote en la barra superior (solo en modo "ver")
        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.MOVIMIENTO,
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,  # flecha de regreso automática
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.fila_inversion,
                            self.txt_monto,
                            self.fila_plataforma,
                            self.campo_fecha.fila,
                            self.fila_tipo,
                            self.txt_comentarios,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _new_dropdowns(self):  # propio
        """
        Crea los Dropdown desde cero y los pone en su fila.

        ¿Por qué no solo `dd.value = None`? Porque el Dropdown de Flet, al
        regresarle el valor a None, sigue MOSTRANDO el texto anterior
        (en Python el valor sí es None, por eso marcaba "Requerido").
        Un Dropdown nuevo siempre arranca vacío.
        """
        self.dd_inversion = ft.Dropdown(
            label="Inversión", options=dropdown_options(INVERSION_SELECTION), expand=True
        )
        self.dd_plataforma = ft.Dropdown(
            label="Plataforma", options=dropdown_options(PLATAFORMA_SELECTION), expand=True
        )
        self.dd_tipo = ft.Dropdown(
            label="Tipo", options=dropdown_options(TIPO_SELECTION), expand=True
        )
        self.fila_inversion.controls = [self.dd_inversion]
        self.fila_plataforma.controls = [self.dd_plataforma]
        self.fila_tipo.controls = [self.dd_tipo]

    def _apply_mode(self):  # propio
        """Ajusta campos, botones y título según self.modo."""
        lectura = self.modo == "ver"

        for dd in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            dd.disabled = lectura
        for txt in (self.txt_monto, self.txt_comentarios):
            txt.read_only = lectura
        self.campo_fecha.set_enabled(not lectura)

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo movimiento"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Movimiento"
        else:
            self.lbl_titulo_form.value = "Editar movimiento"
            self.btn_guardar.content = "Actualizar"

    def _default_date(self) -> date:  # propio
        """Hoy, pero ajustado para que quede dentro del periodo abierto."""
        hoy = date.today()
        if self.periodo is None:
            return hoy
        return min(max(hoy, self.periodo.fecha_inicio), self.periodo.fecha_fin)

    def _fill(self, mov: Movimiento):  # propio
        """Pasa los datos del registro a los campos."""
        self.dd_inversion.value = mov.inversion
        self.txt_monto.value = f"{mov.monto:.2f}"
        self.dd_plataforma.value = mov.plataforma
        self.dd_tipo.value = mov.tipo
        self.txt_comentarios.value = mov.comentarios or ""
        self.campo_fecha.set_value(mov.fecha)

    def clear_errors(self):  # propio
        for campo in (self.dd_inversion, self.txt_monto, self.dd_plataforma,
                      self.dd_tipo, self.campo_fecha.txt):
            campo.error_text = None

    def clear_form(self):  # propio
        self.clear_errors()
        self._new_dropdowns()  # ver la explicación en ese método
        self.txt_monto.value = ""
        self.txt_comentarios.value = ""
        self.campo_fecha.set_value(self._default_date())
        self.registro = None
        self.modo = "nuevo"
        self._apply_mode()

    def _prepare_calendar(self):  # propio
        # Solo se pueden elegir fechas dentro del periodo abierto
        self.campo_fecha.set_range(self.periodo.fecha_inicio, self.periodo.fecha_fin)

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        """Botón +: abre el formulario vacío, listo para capturar."""
        self.clear_form()
        self._prepare_calendar()
        self.page.navigate(routes.MOVIMIENTO)

    def show(self, mov: Movimiento):  # propio
        """Tocar una línea: muestra el movimiento en solo lectura."""
        self.clear_errors()
        self.registro = mov
        self._fill(mov)
        self._prepare_calendar()
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.MOVIMIENTO)

    def edit(self, e=None):  # propio
        """Lápiz: habilita los campos del movimiento mostrado."""
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            # Descarta los cambios: vuelve a leer el registro y regresa a "ver"
            self.clear_errors()
            self.registro = Movimiento.get(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)

    def save(self, e=None):  # propio
        self.clear_errors()
        faltantes = False
        for campo in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            if not campo.value:
                campo.error_text = "Requerido"
                faltantes = True
        try:
            monto = float(self.txt_monto.value)
            if monto <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.txt_monto.error_text = "Monto inválido"
            faltantes = True

        # La fecha debe caer dentro del periodo
        periodo = self.periodo
        if not (periodo.fecha_inicio <= self.campo_fecha.valor <= periodo.fecha_fin):
            self.campo_fecha.txt.error_text = (
                f"Debe estar entre {short_date(periodo.fecha_inicio)} "
                f"y {short_date(periodo.fecha_fin)}"
            )
            faltantes = True

        if faltantes:
            self.page.update()
            return

        valores = dict(
            inversion=self.dd_inversion.value,
            monto=monto,
            plataforma=self.dd_plataforma.value,
            fecha=self.campo_fecha.valor,
            tipo=self.dd_tipo.value,
            comentarios=(self.txt_comentarios.value or "").strip() or None,
            periodo_id=periodo.id,
        )
        try:
            if self.modo == "nuevo":
                Movimiento.create(**valores)
            else:
                self.registro = Movimiento.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Movimiento guardado")
            self.page.navigate(routes.MOVIMIENTOS)  # regresa a la lista del periodo
        else:
            # Se queda en el registro, ahora en solo lectura
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Movimiento actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, mov: Movimiento) -> str:  # propio
        return (
            f"¿Seguro que deseas eliminar el {mov.tipo_label.lower()} de "
            f"${mov.monto:,.2f} en {mov.plataforma_label} ({mov.fecha.isoformat()})?"
        )

    def confirm_delete(self, e=None):  # propio
        """Bote de la barra: elimina el movimiento mostrado, con confirmación."""
        mov = self.registro

        def delete():  # propio
            if self._delete(mov):
                self.clear_form()
                self.page.navigate(routes.MOVIMIENTOS)

        confirm(self.page, "Eliminar movimiento", self._delete_message(mov), delete)

    def _delete(self, mov: Movimiento) -> bool:  # propio
        """Borra el movimiento y refresca la lista. Regresa True si se borró."""
        try:
            Movimiento.delete(mov.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Movimiento eliminado")
        self.page.update()
        return True

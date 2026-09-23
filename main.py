from datetime import date

import flet as ft

from database import init_db
from models import (
    INVERSION_SELECTION,
    PLATAFORMA_SELECTION,
    TIPO_SELECTION,
    Movimiento,
)


def opciones_dropdown(seleccion: dict) -> list[ft.DropdownOption]:
    return [ft.DropdownOption(key=k, text=v) for k, v in seleccion.items()]


def main(page: ft.Page):
    # Crea la BD / tablas si no existen
    init_db()

    # Configuración visual para la pantalla móvil
    page.title = "Mi Primera App"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0  # el margen lo maneja el SafeArea de abajo

    # Tamaño de ventana (ahora se configura en page.window, no en ft.run)
    page.window.width = 412
    page.window.height = 915
    page.window.resizable = False
    page.window.maximizable = False

    def mostrar_logro(e):
        page.show_dialog(ft.SnackBar(ft.Text("LO LOGRASTE...")))
        print("LO LOGRASTE...")

    # ------------------------------------------------------------------
    # Formulario de Movimientos
    # ------------------------------------------------------------------
    dd_inversion = ft.Dropdown(
        label="Inversión", options=opciones_dropdown(INVERSION_SELECTION), expand=True
    )
    txt_monto = ft.TextField(
        label="Monto",
        prefix="$ ",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
    )
    dd_plataforma = ft.Dropdown(
        label="Plataforma", options=opciones_dropdown(PLATAFORMA_SELECTION), expand=True
    )
    dd_tipo = ft.Dropdown(
        label="Tipo", options=opciones_dropdown(TIPO_SELECTION), expand=True
    )
    txt_comentarios = ft.TextField(label="Comentarios", max_length=255)

    # Fecha: TextField de solo lectura que abre un DatePicker
    fecha_seleccionada = {"valor": date.today()}
    txt_fecha = ft.TextField(
        label="Fecha",
        value=date.today().isoformat(),
        read_only=True,
        suffix=ft.Icon(ft.Icons.CALENDAR_MONTH),
    )

    def fecha_cambiada(e):
        if e.control.value:
            fecha_seleccionada["valor"] = e.control.value.date() if hasattr(
                e.control.value, "date"
            ) else e.control.value
            txt_fecha.value = fecha_seleccionada["valor"].isoformat()
            page.update()

    date_picker = ft.DatePicker(
        first_date=date(2000, 1, 1),
        last_date=date(2100, 12, 31),
        on_change=fecha_cambiada,
    )

    def abrir_calendario(e):
        date_picker.value = fecha_seleccionada["valor"]
        page.show_dialog(date_picker)

    txt_fecha.on_click = abrir_calendario
    btn_fecha = ft.IconButton(ft.Icons.EDIT_CALENDAR, on_click=abrir_calendario)

    # ------------------------------------------------------------------
    # Tabla de Movimientos
    # ------------------------------------------------------------------
    # Estado del formulario: None = creando, un id = editando ese movimiento
    estado = {"editando_id": None}

    tabla = ft.DataTable(
        columns=[
            ft.DataColumn("Inversión"),
            ft.DataColumn("Monto", numeric=True),
            ft.DataColumn("Plataforma"),
            ft.DataColumn("Tipo"),
            ft.DataColumn("Fecha"),
            ft.DataColumn("Comentarios"),
            ft.DataColumn("Acciones"),
        ],
        rows=[],
        column_spacing=20,
    )
    lbl_vacio = ft.Text("Aún no hay movimientos registrados", italic=True)

    def cargar_tabla():
        movimientos = Movimiento.search_all()
        tabla.rows = [
            ft.DataRow(
                selected=m.id == estado["editando_id"],
                cells=[
                    ft.DataCell(ft.Text(m.inversion_label)),
                    ft.DataCell(ft.Text(f"${m.monto:,.2f}")),
                    ft.DataCell(ft.Text(m.plataforma_label)),
                    ft.DataCell(ft.Text(m.tipo_label)),
                    ft.DataCell(ft.Text(m.fecha.isoformat())),
                    ft.DataCell(ft.Text(m.comentarios or "")),
                    ft.DataCell(
                        ft.Row(
                            spacing=0,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.EDIT,
                                    icon_color=ft.Colors.BLUE,
                                    tooltip="Editar",
                                    on_click=lambda e, mov=m: editar(mov),
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE,
                                    icon_color=ft.Colors.RED,
                                    tooltip="Eliminar",
                                    on_click=lambda e, mov=m: confirmar_eliminar(mov),
                                ),
                            ],
                        )
                    ),
                ]
            )
            for m in movimientos
        ]
        lbl_vacio.visible = not movimientos

    # ------------------------------------------------------------------
    # Guardar
    # ------------------------------------------------------------------
    def limpiar_errores():
        for campo in (dd_inversion, txt_monto, dd_plataforma, dd_tipo):
            campo.error_text = None

    def limpiar_formulario():
        dd_inversion.value = None
        dd_plataforma.value = None
        dd_tipo.value = None
        txt_monto.value = ""
        txt_comentarios.value = ""
        fecha_seleccionada["valor"] = date.today()
        txt_fecha.value = date.today().isoformat()
        salir_modo_edicion()

    # ------------------------------------------------------------------
    # Modo edición
    # ------------------------------------------------------------------
    lbl_titulo_form = ft.Text("Nuevo movimiento", size=18, weight=ft.FontWeight.BOLD)
    btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE)
    btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, visible=False)

    def salir_modo_edicion():
        estado["editando_id"] = None
        lbl_titulo_form.value = "Nuevo movimiento"
        btn_guardar.content = "Guardar"
        btn_cancelar.visible = False

    def editar(mov: Movimiento):
        limpiar_errores()
        estado["editando_id"] = mov.id
        dd_inversion.value = mov.inversion
        txt_monto.value = f"{mov.monto:.2f}"
        dd_plataforma.value = mov.plataforma
        dd_tipo.value = mov.tipo
        txt_comentarios.value = mov.comentarios or ""
        fecha_seleccionada["valor"] = mov.fecha
        txt_fecha.value = mov.fecha.isoformat()

        lbl_titulo_form.value = f"Editar movimiento #{mov.id}"
        btn_guardar.content = "Actualizar"
        btn_cancelar.visible = True
        cargar_tabla()  # resalta la fila en edición
        page.update()

        # Sube al formulario para que se vea lo que se está editando.
        # scroll_to es async en Flet 1.0, así que se lanza como tarea.
        page.run_task(contenido.scroll_to, offset=0, duration=300)

    def cancelar_edicion(e):
        limpiar_errores()
        limpiar_formulario()
        cargar_tabla()
        page.update()

    btn_cancelar.on_click = cancelar_edicion

    # ------------------------------------------------------------------
    # Eliminar (con confirmación)
    # ------------------------------------------------------------------
    def confirmar_eliminar(mov: Movimiento):
        def eliminar(e):
            page.pop_dialog()
            try:
                Movimiento.delete(mov.id)
            except Exception as ex:  # noqa: BLE001
                page.show_dialog(ft.SnackBar(ft.Text(f"Error al eliminar: {ex}")))
                return
            # Si se borra el que se estaba editando, se limpia el formulario
            if estado["editando_id"] == mov.id:
                limpiar_errores()
                limpiar_formulario()
            cargar_tabla()
            page.show_dialog(ft.SnackBar(ft.Text("Movimiento eliminado")))
            page.update()

        page.show_dialog(
            ft.AlertDialog(
                modal=True,
                title=ft.Text("Eliminar movimiento"),
                content=ft.Text(
                    f"¿Seguro que deseas eliminar el {mov.tipo_label.lower()} de "
                    f"${mov.monto:,.2f} en {mov.plataforma_label} "
                    f"({mov.fecha.isoformat()})?"
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                    ft.TextButton(
                        "Eliminar",
                        style=ft.ButtonStyle(color=ft.Colors.RED),
                        on_click=eliminar,
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    def guardar(e):
        limpiar_errores()
        faltantes = False
        for campo in (dd_inversion, dd_plataforma, dd_tipo):
            if not campo.value:
                campo.error_text = "Requerido"
                faltantes = True
        try:
            monto = float(txt_monto.value)
            if monto <= 0:
                raise ValueError
        except (TypeError, ValueError):
            txt_monto.error_text = "Monto inválido"
            faltantes = True

        if faltantes:
            page.update()
            return

        valores = dict(
            inversion=dd_inversion.value,
            monto=monto,
            plataforma=dd_plataforma.value,
            fecha=fecha_seleccionada["valor"],
            tipo=dd_tipo.value,
            comentarios=(txt_comentarios.value or "").strip() or None,
        )
        editando_id = estado["editando_id"]
        try:
            if editando_id is None:
                Movimiento.create(**valores)
            else:
                Movimiento.update(editando_id, **valores)
        except Exception as ex:  # noqa: BLE001
            page.show_dialog(ft.SnackBar(ft.Text(f"Error al guardar: {ex}")))
            return

        limpiar_formulario()
        cargar_tabla()
        mensaje = "Movimiento guardado" if editando_id is None else "Movimiento actualizado"
        page.show_dialog(ft.SnackBar(ft.Text(mensaje)))
        page.update()

    btn_guardar.on_click = guardar

    formulario = ft.Container(
        padding=15,
        border=ft.Border.all(1, ft.Colors.BLUE_100),
        border_radius=10,
        content=ft.Column(
            spacing=10,
            controls=[
                lbl_titulo_form,
                ft.Row([dd_inversion]),
                txt_monto,
                ft.Row([dd_plataforma]),
                ft.Row([ft.Container(txt_fecha, expand=True), btn_fecha]),
                ft.Row([dd_tipo]),
                txt_comentarios,
                ft.Row([btn_guardar, btn_cancelar]),
            ],
        ),
    )

    seccion_tabla = ft.Column(
        controls=[
            ft.Text("Movimientos", size=18, weight=ft.FontWeight.BOLD),
            lbl_vacio,
            # Scroll horizontal porque la tabla es más ancha que la pantalla
            ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
        ],
    )

    cargar_tabla()

    # Contenido con scroll propio
    contenido = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(ft.Icons.PHONE_ANDROID, size=50, color=ft.Colors.BLUE),
            ft.Text(
                "¡Hola Mundo!",
                size=30,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLUE_900,
            ),
            ft.Text("Mi primera app móvil con Python y Flet", size=14),
            ft.Button(
                "¡Hacer clic!",
                on_click=mostrar_logro,
            ),
            ft.Divider(),
            formulario,
            ft.Divider(),
            seccion_tabla,
            # Espacio extra al final para que la tabla no quede pegada
            # a los botones de navegación del celular
            ft.Container(height=10),
        ],
    )

    # SafeArea evita que la barra de estado (arriba) y los botones de
    # navegación del celular (abajo) tapen el contenido.
    page.add(
        ft.SafeArea(
            expand=True,
            maintain_bottom_view_padding=True,
            minimum_padding=ft.Padding.only(left=12, top=12, right=12, bottom=12),
            content=contenido,
        )
    )


# Ejecuta la aplicación
if __name__ == "__main__":
    ft.run(main)

"""Piezas de interfaz que comparten varias pantallas."""
from datetime import date

import flet as ft

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sept", "oct", "nov", "dic"]


def fecha_corta(d: date) -> str:
    """date(2026, 9, 1) -> '1 sept 2026'"""
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def opciones_dropdown(seleccion: dict) -> list[ft.DropdownOption]:
    """Convierte un *_SELECTION del modelo en opciones de un Dropdown."""
    return [ft.DropdownOption(key=k, text=v) for k, v in seleccion.items()]


def aviso(page: ft.Page, texto: str):
    """Mensaje corto en la parte inferior (SnackBar)."""
    page.show_dialog(ft.SnackBar(ft.Text(texto)))


def boton_agregar(texto: str, on_click) -> ft.FloatingActionButton:
    """Botón verde flotante de 'Nuevo ...'."""
    return ft.FloatingActionButton(
        icon=ft.Icons.ADD,
        content=texto,
        bgcolor=ft.Colors.GREEN_600,
        foreground_color=ft.Colors.WHITE,
        on_click=on_click,
    )


def boton_editar(on_click) -> ft.IconButton:
    """Lápiz para la barra superior del detalle de un registro."""
    return ft.IconButton(ft.Icons.EDIT, tooltip="Editar", on_click=on_click)


def boton_eliminar(on_click) -> ft.IconButton:
    """Bote de basura para la barra superior del detalle de un registro."""
    return ft.IconButton(
        ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Eliminar", on_click=on_click
    )


def cuadro_icono(icono, color) -> ft.Container:
    """Ícono dentro de un cuadro de color suave (inicio de cada línea)."""
    return ft.Container(
        width=42,
        height=42,
        border_radius=6,
        bgcolor=ft.Colors.with_opacity(0.15, color),
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(icono, color=color),
    )


def fondo_deslizar(icono, texto: str, color, alineacion: ft.MainAxisAlignment) -> ft.Container:
    """Fondo de color que aparece detrás de una línea al deslizarla (Dismissible)."""
    return ft.Container(
        bgcolor=color,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=20),
        content=ft.Row(
            alignment=alineacion,
            controls=[
                ft.Icon(icono, color=ft.Colors.WHITE),
                ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            ],
        ),
    )


def deslizar_para_eliminar(
    page: ft.Page, key: str, contenido: ft.Control, titulo: str, mensaje: str, al_eliminar
) -> ft.Dismissible:
    """
    Envuelve una línea de lista para que se pueda deslizar a la izquierda
    y eliminar, siempre con confirmación.
      ◄── deslizar -> fondo rojo "Eliminar" -> confirmar -> al_eliminar()
    """

    def al_deslizar(e):
        dismissible = e.control
        # confirm_dismiss es async: se lanza con run_task desde este handler normal
        responder = lambda decision: page.run_task(  # noqa: E731
            dismissible.confirm_dismiss, decision
        )
        # La línea sale solo si el usuario confirma; si cancela, regresa
        confirmar(
            page, titulo, mensaje,
            al_confirmar=lambda: responder(True),
            al_cancelar=lambda: responder(False),
        )

    return ft.Dismissible(
        key=key,  # identifica la línea de forma única
        content=contenido,
        # Solo se puede deslizar a la izquierda (de fin a inicio)
        dismiss_direction=ft.DismissDirection.END_TO_START,
        # Con una sola dirección basta "background"
        # ("secondary_background" solo se usa si hay dos direcciones)
        background=fondo_deslizar(
            ft.Icons.DELETE, "Eliminar", ft.Colors.RED, ft.MainAxisAlignment.END
        ),
        on_confirm_dismiss=al_deslizar,              # antes de quitar la línea
        on_dismiss=lambda e: al_eliminar(),          # la línea ya salió
    )


def confirmar(page: ft.Page, titulo: str, mensaje: str, al_confirmar, al_cancelar=None):
    """
    Diálogo de confirmación con botones Cancelar / Eliminar.
    al_cancelar (opcional): se llama si el usuario elige Cancelar.
    """

    def aceptar(e):
        page.pop_dialog()
        al_confirmar()

    def cancelar(e):
        page.pop_dialog()
        if al_cancelar:
            al_cancelar()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Text(mensaje),
            actions=[
                ft.TextButton("Cancelar", on_click=cancelar),
                ft.TextButton(
                    "Eliminar",
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                    on_click=aceptar,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


class CampoFecha:
    """
    Campo de fecha: TextField de solo lectura + DatePicker.

    Uso:
        campo = CampoFecha(page, "Fecha")
        campo.fila          -> control para poner en el formulario
        campo.valor         -> fecha elegida (date)
        campo.asignar(d)    -> cambia la fecha mostrada
        campo.limitar(a, b) -> solo permite elegir entre a y b
        campo.habilitar(False) -> modo lectura (no abre el calendario)
        campo.txt.error_text = "..."  -> mostrar un error
    """

    def __init__(self, page: ft.Page, etiqueta: str):
        self.page = page
        self.valor = date.today()
        self.activo = True
        self.txt = ft.TextField(
            label=etiqueta,
            value=self.valor.isoformat(),
            read_only=True,
            suffix=ft.Icon(ft.Icons.CALENDAR_MONTH),
            on_click=self.abrir,
        )
        self.picker = ft.DatePicker(
            first_date=date(2000, 1, 1),
            last_date=date(2100, 12, 31),
            on_change=self._al_cambiar,
        )
        self.btn = ft.IconButton(ft.Icons.EDIT_CALENDAR, on_click=self.abrir)
        self.fila = ft.Row([ft.Container(self.txt, expand=True), self.btn])

    def asignar(self, valor: date):
        self.valor = valor
        self.txt.value = valor.isoformat()

    def limitar(self, inicio: date, fin: date):
        self.picker.first_date = inicio
        self.picker.last_date = fin

    def habilitar(self, activo: bool):
        self.activo = activo
        self.btn.visible = activo  # en modo lectura se oculta el botón del calendario

    def abrir(self, e=None):
        if not self.activo:
            return
        self.picker.value = self.valor
        self.page.show_dialog(self.picker)

    def _al_cambiar(self, e):
        if e.control.value:
            valor = e.control.value
            self.asignar(valor.date() if hasattr(valor, "date") else valor)
            self.page.update()

"""Piezas de interfaz que comparten varias pantallas y módulos."""
import asyncio
from datetime import date, time

import flet as ft

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sept", "oct", "nov", "dic"]


def short_date(d: date) -> str:  # propio
    """date(2026, 9, 1) -> '1 sept 2026'"""
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


def dropdown_options(seleccion: dict) -> list[ft.DropdownOption]:  # propio
    """Convierte un *_SELECTION del modelo en opciones de un Dropdown."""
    return [ft.DropdownOption(key=k, text=v) for k, v in seleccion.items()]


def service(page: ft.Page, clase):  # propio
    """
    Un servicio de Flet (ft.FilePicker, ft.UrlLauncher…) BIEN SUJETO a la página.

    Por qué: Flet da de baja, después de cada evento, los servicios que "nadie
    usa" (cuenta referencias y su índice de controles es débil). Uno guardado
    solo en self.picker queda en el límite y a veces se da de baja mientras
    esperas el selector de archivos -> "Control with ID … is not registered".

    Aquí se crea al usarlo (cuando la app ya está armada) y se guarda en
    page.services, la lista de la PRIMERA vista (el Inicio, que nunca se quita).
    Uno por página, compartido por todos los módulos.

    Uso:  archivos = await service(self.page, ft.FilePicker).pick_files(...)
    """
    for existente in page.services:
        if type(existente) is clase:
            return existente
    nuevo = clase()
    page.services.append(nuevo)
    return nuevo


# Servicios de preferencias que ya no respondieron en esta sesión (por id):
# no se les vuelve a esperar 10 s en cada lectura.
_PREFS_MUDOS: set[int] = set()


async def pref_get(prefs, clave: str, defecto=None, intentos: int = 2):  # propio
    """
    Lee una preferencia guardada SIN tronar la app.

    Al arrancar (sobre todo en el celular) el servicio SharedPreferences puede
    no estar listo: Flet espera 10 s y lanza "Timeout waiting for invoke method
    listener". Aquí se reintenta y, si no responde, se usa el valor por defecto
    (la app abre con lo de fábrica en vez de quedarse a medias). Si ya falló
    una vez, las siguientes lecturas regresan el defecto al instante.
    """
    if id(prefs) in _PREFS_MUDOS:
        return defecto
    for intento in range(intentos):
        try:
            valor = await prefs.get(clave)
            return defecto if valor is None else valor
        except RuntimeError:
            if intento < intentos - 1:
                await asyncio.sleep(1)
    _PREFS_MUDOS.add(id(prefs))
    return defecto


async def pref_set(prefs, clave: str, valor) -> bool:  # propio
    """Guarda una preferencia; si el servicio no responde, regresa False sin tronar."""
    if id(prefs) in _PREFS_MUDOS:
        return False
    try:
        await prefs.set(clave, valor)
        return True
    except RuntimeError:
        return False


def notify(page: ft.Page, texto: str):  # propio
    """Mensaje corto en la parte inferior (SnackBar)."""
    page.show_dialog(ft.SnackBar(ft.Text(texto)))


def add_button(texto: str, on_click) -> ft.FloatingActionButton:  # propio
    """Botón flotante de 'Nuevo ...'. Toma el color del tema elegido."""
    return ft.FloatingActionButton(icon=ft.Icons.ADD, content=texto, on_click=on_click)


def edit_button(on_click) -> ft.IconButton:  # propio
    """Lápiz para la barra superior del detalle de un registro."""
    return ft.IconButton(ft.Icons.EDIT, tooltip="Editar", on_click=on_click)


def delete_button(on_click) -> ft.IconButton:  # propio
    """Bote de basura para la barra superior del detalle de un registro."""
    return ft.IconButton(
        ft.Icons.DELETE, icon_color=ft.Colors.RED, tooltip="Eliminar", on_click=on_click
    )


def icon_box(icono, color) -> ft.Container:  # propio
    """Ícono dentro de un cuadro de color suave (inicio de cada línea)."""
    return ft.Container(
        width=42,
        height=42,
        border_radius=6,
        bgcolor=ft.Colors.with_opacity(0.15, color),
        alignment=ft.Alignment.CENTER,
        content=ft.Icon(icono, color=color),
    )


def swipe_background(icono, texto: str, color, alineacion: ft.MainAxisAlignment) -> ft.Container:  # propio
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


def swipe_to_delete(  # propio
    page: ft.Page, key: str, contenido: ft.Control, titulo: str, mensaje: str, on_delete
) -> ft.Dismissible:
    """
    Envuelve una línea de lista para que se pueda deslizar a la izquierda
    y eliminar, siempre con confirmación.
      ◄── deslizar -> fondo rojo "Eliminar" -> confirmar -> on_delete()
    """

    def on_swipe(e):  # propio
        dismissible = e.control
        # confirm_dismiss es async: se lanza con run_task desde este handler normal
        respond = lambda decision: page.run_task(  # noqa: E731
            dismissible.confirm_dismiss, decision
        )
        # La línea sale solo si el usuario confirma; si cancela, regresa
        confirm(
            page, titulo, mensaje,
            on_accept=lambda: respond(True),
            on_cancel=lambda: respond(False),
        )

    return ft.Dismissible(
        key=key,  # identifica la línea de forma única
        content=contenido,
        # Solo se puede deslizar a la izquierda (de fin a inicio)
        dismiss_direction=ft.DismissDirection.END_TO_START,
        # Con una sola dirección basta "background"
        # ("secondary_background" solo se usa si hay dos direcciones)
        background=swipe_background(
            ft.Icons.DELETE, "Eliminar", ft.Colors.RED, ft.MainAxisAlignment.END
        ),
        on_confirm_dismiss=on_swipe,              # antes de quitar la línea
        on_dismiss=lambda e: on_delete(),         # la línea ya salió
    )


def confirm(page: ft.Page, titulo: str, mensaje: str, on_accept, on_cancel=None):  # propio
    """
    Diálogo de confirmación con botones Cancelar / Eliminar.
    on_cancel (opcional): se llama si el usuario elige Cancelar.
    """

    def accept(e):  # propio
        page.pop_dialog()
        on_accept()

    def cancel(e):  # propio
        page.pop_dialog()
        if on_cancel:
            on_cancel()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Text(mensaje),
            actions=[
                ft.TextButton("Cancelar", on_click=cancel),
                ft.TextButton(
                    "Eliminar",
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                    on_click=accept,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )


def coming_soon_view(route: str, titulo: str, icono, texto: str) -> ft.View:  # propio
    """Pantalla de un módulo que todavía no tiene contenido."""
    return ft.View(
        route=route,
        appbar=ft.AppBar(title=ft.Text(titulo)),
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Icon(icono, size=72, color=ft.Colors.PRIMARY),
            ft.Text(titulo, size=22, weight=ft.FontWeight.BOLD),
            ft.Text(texto, text_align=ft.TextAlign.CENTER, color=ft.Colors.OUTLINE),
            ft.Container(height=8),
            ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.CONSTRUCTION, size=18, color=ft.Colors.OUTLINE),
                    ft.Text("Próximamente", italic=True, color=ft.Colors.OUTLINE),
                ],
            ),
        ],
    )


class DateField:
    """
    Campo de fecha: TextField de solo lectura + DatePicker.

    Uso:
        campo = DateField(page, "Fecha")
        campo.fila             -> control para poner en el formulario
        campo.valor            -> fecha elegida (date)
        campo.set_value(d)     -> cambia la fecha mostrada
        campo.set_range(a, b)  -> solo permite elegir entre a y b
        campo.set_enabled(False) -> modo lectura (no abre el calendario)
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
            on_click=self.open,
        )
        self.picker = ft.DatePicker(
            first_date=date(2000, 1, 1),
            last_date=date(2100, 12, 31),
            on_change=self._on_change,
        )
        self.btn = ft.IconButton(ft.Icons.EDIT_CALENDAR, on_click=self.open)
        self.fila = ft.Row([ft.Container(self.txt, expand=True), self.btn])

    def set_value(self, valor: date):  # propio
        self.valor = valor
        self.txt.value = valor.isoformat()

    def set_range(self, inicio: date, fin: date):  # propio
        self.picker.first_date = inicio
        self.picker.last_date = fin

    def set_enabled(self, activo: bool):  # propio
        self.activo = activo
        self.btn.visible = activo  # en modo lectura se oculta el botón del calendario

    def open(self, e=None):  # propio
        if not self.activo:
            return
        self.picker.value = self.valor
        self.page.show_dialog(self.picker)

    def _on_change(self, e):  # propio
        if e.control.value:
            valor = e.control.value
            self.set_value(valor.date() if hasattr(valor, "date") else valor)
            self.page.update()


class TimeField:
    """
    Campo de hora OPCIONAL: TextField de solo lectura + TimePicker + botón ✕.
    Sin hora = "todo el día".

    Uso (igual que DateField):
        campo = TimeField(page, "Hora de inicio")
        campo.fila             -> control para el formulario
        campo.valor            -> time o None
        campo.set_value(t)     -> cambia la hora (None la borra)
        campo.set_enabled(False) -> modo lectura
    """

    def __init__(self, page: ft.Page, etiqueta: str):
        self.page = page
        self.valor: time | None = None
        self.activo = True
        self.txt = ft.TextField(
            label=etiqueta,
            hint_text="Todo el día",
            read_only=True,
            suffix=ft.Icon(ft.Icons.ACCESS_TIME),
            on_click=self.open,
        )
        self.picker = ft.TimePicker(
            hour_format=ft.TimePickerHourFormat.H24, on_change=self._on_change
        )
        self.btn_borrar = ft.IconButton(ft.Icons.CLEAR, tooltip="Quitar hora",
                                        on_click=self.clear)
        self.fila = ft.Row([ft.Container(self.txt, expand=True), self.btn_borrar])

    def set_value(self, valor: time | None):  # propio
        self.valor = valor
        self.txt.value = f"{valor:%H:%M}" if valor else ""

    def set_enabled(self, activo: bool):  # propio
        self.activo = activo
        self.btn_borrar.visible = activo

    def open(self, e=None):  # propio
        if not self.activo:
            return
        self.picker.value = self.valor or time(9, 0)
        self.page.show_dialog(self.picker)

    def clear(self, e=None):  # propio
        self.set_value(None)
        self.page.update()

    def _on_change(self, e):  # propio
        if e.control.value:
            self.set_value(e.control.value.replace(second=0, microsecond=0))
            self.page.update()

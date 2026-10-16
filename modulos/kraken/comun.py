"""
Piezas de pantalla que comparten las herramientas de Kraken Tools.

  tabs_row(...)          fila de chips que funcionan como pestañas
  method_badge(metodo)   "GET" verde, "POST" naranja…
  status_chip(codigo)    200 verde · 3xx azul · 4xx naranja · 5xx rojo
  ask_text(page, ...)    diálogo con un campo (nombre de colección, etc.)
  copy_text(page, txt)   copia al portapapeles y avisa
  KeyValueEditor         filas [✓] clave  valor  ✕  (params, headers, variables…)

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import notify, service

MONO = "monospace"   # letra de ancho fijo (código, JSON, SQL)

COLOR_METODO = {"GET": ft.Colors.GREEN, "POST": ft.Colors.ORANGE, "PUT": ft.Colors.BLUE,
                "PATCH": ft.Colors.PURPLE, "DELETE": ft.Colors.RED,
                "HEAD": ft.Colors.TEAL, "OPTIONS": ft.Colors.BLUE_GREY}


def tabs_row(opciones: list[tuple[str, str]], actual: str, on_select) -> ft.Row:  # propio
    """opciones = [(clave, texto)] -> chips; el de `actual` va marcado."""
    return ft.Row(spacing=6, run_spacing=6, wrap=True, controls=[
        ft.Chip(label=ft.Text(texto), show_checkmark=False, selected=clave == actual,
                on_select=lambda e, c=clave: on_select(c))
        for clave, texto in opciones
    ])


def method_badge(metodo: str, ancho: int = 58) -> ft.Control:  # propio
    color = COLOR_METODO.get(metodo, ft.Colors.GREY)
    return ft.Container(
        width=ancho, alignment=ft.Alignment.CENTER_LEFT,
        content=ft.Text(metodo, size=11, weight=ft.FontWeight.BOLD, color=color,
                        font_family=MONO),
    )


def status_color(codigo: int | None):  # propio
    if codigo is None:
        return ft.Colors.RED
    if codigo < 300:
        return ft.Colors.GREEN
    if codigo < 400:
        return ft.Colors.BLUE
    if codigo < 500:
        return ft.Colors.ORANGE
    return ft.Colors.RED


def status_chip(codigo: int | None, motivo: str = "") -> ft.Control:  # propio
    color = status_color(codigo)
    texto = f"{codigo} {motivo}".strip() if codigo is not None else "Error"
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.18, color),
        content=ft.Text(texto, size=12, weight=ft.FontWeight.BOLD, color=color),
    )


def ask_text(page: ft.Page, titulo: str, on_ok, valor: str = "", etiqueta: str = "Nombre",  # propio
             boton: str = "Guardar", multilinea: bool = False, ayuda: str | None = None):
    """
    Diálogo con un campo. on_ok(texto) puede lanzar ValueError: el mensaje
    se muestra debajo del campo y el diálogo sigue abierto.
    """
    campo = ft.TextField(label=etiqueta, value=valor, autofocus=True, multiline=multilinea,
                         min_lines=6 if multilinea else None,
                         max_lines=12 if multilinea else None,
                         text_style=ft.TextStyle(font_family=MONO) if multilinea else None,
                         helper=ayuda)

    def aceptar(e=None):  # propio
        try:
            on_ok((campo.value or "").strip() if not multilinea else (campo.value or ""))
        except ValueError as ex:
            campo.error = str(ex)
            campo.update()
            return
        page.pop_dialog()

    if not multilinea:
        campo.on_submit = aceptar
    page.show_dialog(ft.AlertDialog(
        title=ft.Text(titulo),
        content=ft.Container(width=520, content=campo),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton(boton, on_click=aceptar)],
    ))


async def copy_text(page: ft.Page, texto: str, aviso: str = "Copiado"):  # propio
    await service(page, ft.Clipboard).set(texto)
    notify(page, aviso)


def empty_state(icono, titulo: str, texto: str) -> ft.Control:  # propio
    return ft.Container(
        padding=ft.Padding.only(top=40, left=16, right=16), alignment=ft.Alignment.TOP_CENTER,
        content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
            ft.Icon(icono, size=56, color=ft.Colors.OUTLINE),
            ft.Text(titulo, size=16, weight=ft.FontWeight.BOLD),
            ft.Text(texto, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
        ]),
    )


class KeyValueEditor:
    """
    Lista editable de filas {"clave", "valor", "activo"}:

      [✓] page        2        ✕
      [ ] debug       true     ✕     <- sin palomita: se guarda pero no se manda
      + Agregar

    Trabaja SOBRE la lista que le pasas (la modifica en su lugar) y llama
    on_change() en cada cambio. Al escribir NO se redibuja (el cursor
    saltaría); solo al agregar o quitar filas.
    """

    def __init__(self, page: ft.Page, on_change, clave: str = "Clave", valor: str = "Valor",
                 agregar: str = "Agregar", asistente=None, grupo: str = ""):
        """asistente: un VariableAssist (pinta y autocompleta {{variables}}); grupo: su nombre."""
        self.page = page
        self.asistente = asistente
        self.grupo = grupo or str(id(self))
        self.on_change = on_change
        self.textos = (clave, valor, agregar)
        self.filas: list[dict] = []
        self._enfocar: int | None = None
        self.control = ft.Column(spacing=2)

    def load(self, filas: list[dict]):  # propio
        self.filas = filas
        self._render()

    def _render(self):  # propio
        clave, valor, agregar = self.textos
        if self.asistente is not None:
            self.asistente.forget(self.grupo)   # los campos viejos se van
        controles = [self._row(k, f, clave, valor) for k, f in enumerate(self.filas)]
        controles.append(ft.TextButton(agregar, icon=ft.Icons.ADD, on_click=self.add))
        self.control.controls = controles
        self._enfocar = None

    def _row(self, k: int, fila: dict, clave: str, valor: str) -> ft.Control:  # propio
        def set_field(campo: str, texto):  # propio
            fila[campo] = texto
            self.on_change()

        txt_clave = ft.TextField(value=fila.get("clave", ""), hint_text=clave, dense=True, expand=2,
                                 autofocus=k == self._enfocar,
                                 text_style=ft.TextStyle(font_family=MONO),
                                 on_change=lambda e: set_field("clave", e.control.value))
        txt_valor = ft.TextField(value=fila.get("valor", ""), hint_text=valor, dense=True,
                                 expand=3, text_style=ft.TextStyle(font_family=MONO),
                                 on_change=lambda e: set_field("valor", e.control.value))
        campos: list[ft.Control] = [txt_clave, txt_valor]
        if self.asistente is not None:
            campos = [self.asistente.attach(txt_clave, self.grupo),
                      self.asistente.attach(txt_valor, self.grupo)]
        alineado = (ft.CrossAxisAlignment.START if self.asistente is not None
                    else ft.CrossAxisAlignment.CENTER)
        return ft.Row(spacing=4, vertical_alignment=alineado, controls=[
            ft.Checkbox(value=fila.get("activo", True),
                        on_change=lambda e: set_field("activo", e.control.value)),
            *campos,
            ft.IconButton(ft.Icons.CLOSE, icon_size=18, tooltip="Quitar",
                          on_click=lambda e, kk=k: self.remove(kk)),
        ])

    def add(self, e=None):  # propio
        self.filas.append({"clave": "", "valor": "", "activo": True})
        self._enfocar = len(self.filas) - 1
        self._render()
        self.on_change()
        self.page.update()

    def remove(self, k: int):  # propio
        self.filas.pop(k)
        self._render()
        self.on_change()
        self.page.update()

    @property
    def activos(self) -> int:  # propio
        return sum(1 for f in self.filas if f.get("activo", True) and (f.get("clave") or "").strip())

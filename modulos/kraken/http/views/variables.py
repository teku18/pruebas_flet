"""
Ayuda con las {{variables}} en el editor de peticiones (como Postman):

  [ {{base}}/api/users/{{id}}                                      ]
   {{base}} /api/users/ {{id}}        <- azul = definida · rojo = no existe
                                         (tocar: ver sus valores)
  [ {{to|                                                          ]
   (token = eyJhbGciOi…)  (token_admin = abc…)   <- tocar = se completa {{token}}

Flet no puede pintar de colores una parte del texto DENTRO del campo, así
que la versión de colores va justo debajo, y solo aparece si hay variables.

Uso:  asistente.attach(campo, grupo="url")  -> control para poner en la pantalla
      asistente.refresh()                    -> repintar (cambió el entorno)
      asistente.forget(grupo)                -> soltar campos que ya no existen

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from types import SimpleNamespace

import flet as ft

from modulos.kraken.comun import MONO
from modulos.kraken.http import services

AZUL = ft.Colors.BLUE
ROJO = ft.Colors.RED


class _Campo:
    """Un campo con su línea de colores y sus sugerencias."""

    def __init__(self, campo: ft.TextField, grupo: str, lista: bool):
        self.campo = campo
        self.grupo = grupo
        self.lista = lista              # body: solo la lista de variables, no el texto entero
        self.colores = ft.Text(size=11, font_family=MONO, max_lines=3,
                               overflow=ft.TextOverflow.ELLIPSIS)
        self.caja_colores = ft.Container(content=self.colores, visible=False, ink=True,
                                         border_radius=4,
                                         padding=ft.Padding.symmetric(horizontal=4, vertical=1))
        self.sugerencias = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6, visible=False)
        self.inicio: int | None = None   # dónde empiezan las {{ que estás escribiendo


class VariableAssist:
    def __init__(self, page: ft.Page, get_vars, on_edit_vars=None):
        """get_vars() -> {"base": "http://…"} · on_edit_vars(): abrir Entornos."""
        self.page = page
        self.get_vars = get_vars
        self.on_edit_vars = on_edit_vars
        self.campos: list[_Campo] = []

    # ==================================================================
    def attach(self, campo: ft.TextField, grupo: str = "", lista: bool = False,  # propio
               expand=None) -> ft.Control:
        c = _Campo(campo, grupo, lista)
        original = campo.on_change

        def changed(e):  # propio
            if original:
                original(e)
            self._update(c)

        campo.on_change = changed
        campo.on_selection_change = lambda e: self._suggest(c, update=True)
        c.caja_colores.on_click = lambda e: self.show_values(campo.value or "")
        self.campos.append(c)
        self._paint(c)
        return ft.Column(spacing=2, expand=campo.expand if expand is None else expand,
                         controls=[campo, c.sugerencias, c.caja_colores])

    def forget(self, grupo: str):  # propio
        self.campos = [c for c in self.campos if c.grupo != grupo]

    def refresh(self):  # propio
        """Cambió el entorno o se cargó otra petición: repintar todo (sin update)."""
        for c in self.campos:
            c.sugerencias.visible = False
            self._paint(c)

    # ==================================================================
    def _update(self, c: _Campo):  # propio
        self._paint(c)
        self._suggest(c, update=False)
        self._safe_update(c.caja_colores, c.sugerencias)

    @staticmethod
    def _safe_update(*controles):  # propio
        for x in controles:
            try:
                x.update()
            except (RuntimeError, AssertionError):
                pass    # aún no está en pantalla

    def _paint(self, c: _Campo):  # propio
        texto = c.campo.value or ""
        partes = services.split_variables(texto)
        nombres = [n for _, n in partes if n]
        if not nombres:
            c.caja_colores.visible = False
            return
        valores = self.get_vars()
        if c.lista:     # body: solo las variables que usa
            vistos = list(dict.fromkeys(nombres))
            partes = []
            for k, n in enumerate(vistos):
                partes.append(("{{" + n + "}}", n))
                if k < len(vistos) - 1:
                    partes.append(("  ", None))
        spans = []
        for trozo, nombre in partes:
            if nombre is None:
                spans.append(ft.TextSpan(trozo, style=ft.TextStyle(color=ft.Colors.OUTLINE)))
            else:
                definida = nombre in valores
                spans.append(ft.TextSpan(trozo, style=ft.TextStyle(
                    color=AZUL if definida else ROJO, weight=ft.FontWeight.BOLD,
                    decoration=None if definida else ft.TextDecoration.UNDERLINE)))
        c.colores.spans = spans
        c.colores.value = None
        c.caja_colores.visible = True

    def _suggest(self, c: _Campo, update: bool):  # propio
        texto = c.campo.value or ""
        sel = c.campo.selection
        cursor = sel.extent_offset if sel is not None else None
        escribiendo = services.variable_at_cursor(texto, cursor)
        opciones = services.suggest_variables(escribiendo[1], self.get_vars()) if escribiendo else []
        antes = c.sugerencias.visible
        if not opciones:
            c.sugerencias.visible, c.inicio = False, None
        else:
            c.inicio = escribiendo[0]
            c.sugerencias.controls = [self._chip(c, nombre, valor) for nombre, valor in opciones]
            c.sugerencias.visible = True
        if update and (antes or c.sugerencias.visible):
            self._safe_update(c.sugerencias)

    def _chip(self, c: _Campo, nombre: str, valor: str) -> ft.Control:  # propio
        corto = valor if len(valor) <= 24 else valor[:22] + "…"
        return ft.Chip(
            label=ft.Text(spans=[
                ft.TextSpan(nombre, style=ft.TextStyle(color=AZUL, weight=ft.FontWeight.BOLD,
                                                       font_family=MONO)),
                ft.TextSpan(f"  {corto}" if corto else "  (vacía)",
                            style=ft.TextStyle(color=ft.Colors.OUTLINE, size=11))]),
            on_click=lambda e: self._pick(c, nombre))

    def _pick(self, c: _Campo, nombre: str):  # propio
        if c.inicio is None:
            return
        sel = c.campo.selection
        cursor = sel.extent_offset if sel is not None else None
        nuevo, posicion = services.insert_variable(c.campo.value or "", c.inicio, cursor, nombre)
        c.campo.value = nuevo
        c.sugerencias.visible, c.inicio = False, None
        if c.campo.on_change:    # que el editor se entere (como si lo hubieras escrito)
            c.campo.on_change(SimpleNamespace(control=c.campo, data=nuevo))
        self._safe_update(c.campo)

        async def cursor_al_final():  # propio
            await c.campo.focus()
            c.campo.selection = ft.TextSelection(base_offset=posicion, extent_offset=posicion)
            self._safe_update(c.campo)

        self.page.run_task(cursor_al_final)

    # ==================================================================
    def show_values(self, texto: str):  # propio
        """Tocar la línea de colores: qué vale cada variable (y si falta alguna)."""
        valores = self.get_vars()
        nombres = list(dict.fromkeys(n for _, n in services.split_variables(texto) if n))
        filas = []
        for n in nombres:
            definida = n in valores
            filas.append(ft.Column(spacing=0, controls=[
                ft.Text("{{" + n + "}}", font_family=MONO, weight=ft.FontWeight.BOLD,
                        color=AZUL if definida else ROJO),
                ft.Text(valores[n] if definida else "No existe en Globales ni en el entorno "
                        "elegido", selectable=True, size=13, font_family=MONO if definida else None,
                        color=None if definida else ROJO)]))

        def editar(e):  # propio
            self.page.pop_dialog()
            if self.on_edit_vars:
                self.on_edit_vars()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Variables"),
            content=ft.Container(width=440, content=ft.Column(
                tight=True, spacing=10, controls=filas,
                scroll=ft.ScrollMode.AUTO if len(filas) > 6 else None)),
            actions=[ft.TextButton("Editar variables", on_click=editar),
                     ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())],
        ))

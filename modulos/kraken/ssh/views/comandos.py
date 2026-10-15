"""
Comandos guardados de SSH.

  commands_sheet(page, sesion, equipo)  la hoja para CORRER uno (desde el panel):
      Reiniciar Odoo            sudo systemctl restart odoo
      Reiniciar PostgreSQL      …
      [Administrar comandos]
    tocar -> "¿Reiniciar Odoo en Cliente ACME?" -> corre -> muestra la salida
  commands_manager(page, equipo)        agregar, editar o borrar comandos
      (equipo None = los de todos los servidores)

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import confirm, notify
from modulos.kraken.comun import MONO, copy_text
from modulos.kraken.models import ComandoSsh, Equipo
from modulos.kraken.red import historial
from modulos.kraken.ssh import acciones
from modulos.kraken.ssh.conexion import Sesion


def commands_sheet(page: ft.Page, sesion: Sesion, equipo: Equipo):  # propio
    def pick(c: ComandoSsh):  # propio
        page.pop_dialog()
        if c.confirmar:
            def ok():  # propio
                page.run_task(_run, page, sesion, equipo, c)
            confirm(page, c.nombre, f"¿Correr en «{equipo.nombre}»?\n\n{c.comando}", ok,
                    boton="Correr")
        else:
            page.run_task(_run, page, sesion, equipo, c)

    comandos = ComandoSsh.for_server(equipo.id)
    filas = [ft.ListTile(
        leading=ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, color=ft.Colors.PURPLE),
        title=ft.Text(c.nombre),
        subtitle=ft.Text(c.comando, font_family=MONO, size=11, max_lines=1,
                         overflow=ft.TextOverflow.ELLIPSIS),
        on_click=lambda e, x=c: pick(x)) for c in comandos]
    page.show_dialog(ft.BottomSheet(
        show_drag_handle=True, scrollable=True,
        content=ft.Container(padding=ft.Padding.only(bottom=20), content=ft.Column(
            tight=True, spacing=0, scroll=ft.ScrollMode.AUTO, controls=[
                ft.ListTile(title=ft.Text(f"Comandos · {equipo.nombre}",
                                          weight=ft.FontWeight.BOLD)),
                *(filas or [ft.ListTile(title=ft.Text("Aún no hay comandos", italic=True))]),
                ft.TextButton("Administrar comandos", icon=ft.Icons.EDIT,
                              on_click=lambda e: (page.pop_dialog(),
                                                  commands_manager(page, equipo))),
            ])),
    ))


async def _run(page: ft.Page, sesion: Sesion, equipo: Equipo, c: ComandoSsh):  # propio
    page.show_dialog(ft.AlertDialog(modal=True, content=ft.Row(tight=True, controls=[
        ft.ProgressRing(width=24, height=24), ft.Text(f"{c.nombre}…")])))
    r = await asyncio.to_thread(acciones.run_command, sesion, c.nombre, c.comando)
    page.pop_dialog()
    historial.record("ssh", f"{equipo.nombre}: {c.nombre}", r)
    show_output(page, r.to_dict())


def show_output(page: ft.Page, d: dict):  # propio
    """La salida de un comando (también desde el historial)."""
    if d.get("error"):
        titulo, color = "No se pudo correr", ft.Colors.RED
    elif d.get("codigo") == 0:
        titulo, color = "Listo", ft.Colors.GREEN
    else:
        titulo, color = f"Terminó con error ({d.get('codigo')})", ft.Colors.ORANGE
    texto = "\n".join(x for x in (d.get("salida", "").rstrip(), d.get("errores", "").rstrip(),
                                  d.get("error") or "") if x) or "(sin salida)"
    page.show_dialog(ft.AlertDialog(
        title=ft.Row(controls=[ft.Icon(ft.Icons.CIRCLE, size=12, color=color),
                               ft.Text(f"{d.get('nombre')}: {titulo}", size=16, expand=True)]),
        content=ft.Container(width=520, content=ft.Column(
            tight=True, controls=[
            ft.Text(f"$ {d.get('comando')}", font_family=MONO, size=12, color=ft.Colors.OUTLINE),
            # salida larga: se desliza dentro de una caja; corta: el diálogo queda chico
            ft.Container(height=360 if texto.count("\n") > 18 else None, content=ft.Column(
                scroll=ft.ScrollMode.AUTO if texto.count("\n") > 18 else None, controls=[
                    ft.Text(texto, font_family=MONO, size=12, selectable=True)])),
            ft.Text(f"{d.get('tiempo_ms', 0)} ms", size=11, color=ft.Colors.OUTLINE)])),
        actions=[ft.TextButton("Copiar", on_click=lambda e: page.run_task(copy_text, page, texto)),
                 ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))


# ============================================================================
# Administrar
# ============================================================================
def commands_manager(page: ft.Page, equipo: Equipo | None):  # propio
    def reopen():  # propio
        page.pop_dialog()
        commands_manager(page, equipo)

    comandos = ComandoSsh.for_server(equipo.id) if equipo else ComandoSsh.search_all()
    filas = []
    for c in comandos:
        de_quien = "Todos" if c.equipo_id is None else (
            "Solo este" if equipo and c.equipo_id == equipo.id else
            (Equipo.get(c.equipo_id).nombre if Equipo.get(c.equipo_id) else "?"))
        filas.append(ft.ListTile(
            title=ft.Text(c.nombre),
            subtitle=ft.Text(f"{de_quien} · {c.comando}", size=11, max_lines=1,
                             overflow=ft.TextOverflow.ELLIPSIS),
            on_click=lambda e, x=c: (page.pop_dialog(), command_dialog(page, x, equipo, reopen)),
        ))
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Comandos" + (f" · {equipo.nombre}" if equipo else "")),
        content=ft.Container(width=480, content=ft.Column(
            tight=True, scroll=ft.ScrollMode.AUTO,
            controls=filas or [ft.Text("Aún no hay comandos.", italic=True)])),
        actions=[ft.TextButton("Nuevo", icon=ft.Icons.ADD,
                               on_click=lambda e: (page.pop_dialog(),
                                                   command_dialog(page, None, equipo, reopen))),
                 ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))


def command_dialog(page: ft.Page, c: ComandoSsh | None, equipo: Equipo | None,  # propio
                   on_done):
    txt_nombre = ft.TextField(label="Nombre", value=c.nombre if c else "", autofocus=not c,
                              hint_text="Reiniciar Odoo")
    txt_comando = ft.TextField(label="Comando", value=c.comando if c else "", multiline=True,
                               min_lines=2, max_lines=5, text_style=ft.TextStyle(font_family=MONO),
                               hint_text="sudo systemctl restart odoo", autocorrect=False,
                               capitalization=ft.TextCapitalization.NONE,
                               helper="Con sudo al inicio, se usa la contraseña del servidor")
    sw_confirmar = ft.Switch(label="Preguntar antes de correrlo",
                             value=c.confirmar if c else True)
    sw_solo = ft.Switch(label=f"Solo para {equipo.nombre}" if equipo else "Solo para un servidor",
                        value=bool(c and c.equipo_id), visible=equipo is not None)

    def save(e):  # propio
        valores = dict(nombre=(txt_nombre.value or "").strip(),
                       comando=(txt_comando.value or "").strip(), confirmar=sw_confirmar.value)
        if equipo is not None:
            valores["equipo_id"] = equipo.id if sw_solo.value else None
        try:
            ComandoSsh.update(c.id, **valores) if c else ComandoSsh.create(**valores)
        except ValueError as ex:
            (txt_comando if "comando" in str(ex) else txt_nombre).error = str(ex)
            page.update()
            return
        notify(page, "Comando guardado")
        on_done()

    def delete(e):  # propio
        page.pop_dialog()

        def ok():  # propio
            ComandoSsh.delete(c.id)
            notify(page, "Comando eliminado")
            commands_manager(page, equipo)
        confirm(page, "Eliminar comando", f"¿Eliminar «{c.nombre}»?", ok)

    acciones_ = [ft.TextButton("Cancelar", on_click=lambda e: on_done()),
                 ft.FilledButton("Guardar", on_click=save)]
    if c:
        acciones_.insert(0, ft.TextButton("Eliminar", style=ft.ButtonStyle(color=ft.Colors.RED),
                                          on_click=delete))
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar comando" if c else "Nuevo comando"),
        content=ft.Container(width=480, content=ft.Column(
            tight=True, spacing=10, controls=[txt_nombre, txt_comando, sw_confirmar, sw_solo])),
        actions=acciones_,
    ))

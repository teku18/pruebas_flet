"""
Diálogo para dar de alta / editar un servidor PostgreSQL o MySQL.

  Nombre        [Cliente ACME · Odoo     ]
  Host          [localhost               ]  Puerto [5432]
  Usuario       [odoo    ]  Contraseña [secreto]      <- texto normal, a propósito
  Base de datos [produccion              ]
  Por SSH       [Directo (sin túnel)    ▾]   <- o un servidor de Kraken > SSH
  [Probar conexión]
  PostgreSQL 16.4 · 38 ms · toca una base para usarla:  (produccion) (pruebas)

Con túnel SSH, "Host" es como lo ve EL SERVIDOR (casi siempre localhost).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import notify
from modulos.kraken.comun import MONO
from modulos.kraken.models import Equipo
from modulos.kraken.models.sqlite import PUERTOS
from modulos.kraken.sqlite import services
from modulos.kraken.sqlite.services import BaseInfo

NOMBRES = {"postgres": "PostgreSQL", "mysql": "MySQL / MariaDB"}
DIRECTO = "0"


def server_dialog(page: ft.Page, tipo: str, on_saved, base: BaseInfo | None = None):  # propio
    """Abre el diálogo. on_saved() se llama tras guardar."""
    servidores = [e for e in Equipo.search_all() if e.tiene_ssh]

    def campo(label, valor="", **kw):  # propio
        return ft.TextField(label=label, value=valor or "", dense=True, autocorrect=False,
                            capitalization=ft.TextCapitalization.NONE, **kw)

    txt_nombre = campo("Nombre", base.nombre if base else "")
    txt_host = campo("Host", base.host if base else "localhost", expand=True)
    txt_puerto = campo("Puerto", str(base.puerto) if base and base.puerto else "", width=95,
                       hint_text=str(PUERTOS[tipo]), keyboard_type=ft.KeyboardType.NUMBER)
    txt_usuario = campo("Usuario", base.usuario if base else "", expand=True)
    txt_clave = campo("Contraseña", base.clave if base else "", expand=True)
    txt_base = campo("Base de datos", base.base_datos if base else "")
    dd_ssh = ft.Dropdown(
        label="Conectar", dense=True, expand=True,
        value=str(base.ssh_equipo_id) if base and base.ssh_equipo_id else DIRECTO,
        options=[ft.DropdownOption(key=DIRECTO, text="Directo (sin túnel)")]
        + [ft.DropdownOption(key=str(e.id), text=f"Por SSH: {e.nombre}") for e in servidores])
    lbl_ayuda = ft.Text(size=11, color=ft.Colors.OUTLINE)
    lbl_prueba = ft.Text(size=12, selectable=True)
    bases_chips = ft.Row(wrap=True, spacing=6, run_spacing=6)
    btn_probar = ft.OutlinedButton("Probar conexión", icon=ft.Icons.PLAY_ARROW)

    def help_text():  # propio
        lbl_ayuda.value = ("Host = como lo ve el servidor SSH (casi siempre localhost)."
                           if dd_ssh.value != DIRECTO else
                           "Sin túnel el puerto debe estar abierto hacia tu celular.")

    def on_ssh(e):  # propio
        help_text()
        page.update()

    dd_ssh.on_select = on_ssh
    help_text()

    def values() -> dict:  # propio
        texto = (txt_puerto.value or "").strip()
        if texto and not texto.isdigit():
            raise ValueError("El puerto debe ser un número")
        return dict(tipo=tipo, nombre=(txt_nombre.value or "").strip() or (txt_base.value or "").strip(),
                    host=txt_host.value, puerto=int(texto) if texto else None,
                    usuario=txt_usuario.value, clave=txt_clave.value or None,
                    base_datos=txt_base.value,
                    ssh_equipo_id=None if dd_ssh.value in (None, DIRECTO) else int(dd_ssh.value))

    def pick(nombre):  # propio
        txt_base.value = nombre
        if not (txt_nombre.value or "").strip():
            txt_nombre.value = nombre
        page.update()

    async def probar(e):  # propio
        try:
            v = values()
        except ValueError as ex:
            lbl_prueba.value, lbl_prueba.color = str(ex), ft.Colors.RED
            page.update()
            return
        prueba_base = BaseInfo(-1, v["nombre"] or "prueba", None, True, False, None, tipo,
                               (v["host"] or "").strip(), v["puerto"], (v["base_datos"] or "").strip() or None,
                               (v["usuario"] or "").strip(), v["clave"], v["ssh_equipo_id"])
        btn_probar.disabled = True
        lbl_prueba.value, lbl_prueba.color = "Conectando…", None
        bases_chips.controls = []
        page.update()
        prueba = await asyncio.to_thread(services.test_server, prueba_base)
        btn_probar.disabled = False
        lbl_prueba.value = prueba.mensaje
        lbl_prueba.color = ft.Colors.GREEN if prueba.ok else ft.Colors.RED
        if prueba.ok and prueba.bases:
            lbl_prueba.value += " · toca una base para usarla:"
            bases_chips.controls = [ft.Chip(label=ft.Text(b, size=11, font_family=MONO),
                                            on_click=lambda e, x=b: pick(x))
                                    for b in prueba.bases]
        page.update()

    btn_probar.on_click = probar

    def guardar(e):  # propio
        try:
            v = values()
            services.save_server(base.id if base else None, **v)
        except ValueError as ex:
            lbl_prueba.value, lbl_prueba.color = str(ex), ft.Colors.RED
            page.update()
            return
        page.pop_dialog()
        notify(page, "Servidor guardado" + ("" if base else " (solo lectura)"))
        on_saved()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(("Editar " if base else "Nuevo ") + NOMBRES[tipo]),
        content=ft.Container(width=440, content=ft.Column(
            tight=True, scroll=ft.ScrollMode.AUTO, spacing=10, controls=[
                txt_nombre, ft.Row([dd_ssh]), lbl_ayuda,
                ft.Row([txt_host, txt_puerto]),
                ft.Row([txt_usuario, txt_clave]), txt_base,
                ft.Row([btn_probar]), lbl_prueba, bases_chips])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar", on_click=guardar)],
    ))

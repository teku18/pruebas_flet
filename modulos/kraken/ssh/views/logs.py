"""
Logs de un servidor (/kraken/ssh/logs).

  ← Logs · Cliente ACME
  [/var/log/odoo/odoo-server.log            ]
  [Últimas 200 ▾] [🔍 buscar (error, traceback…)] [ ] con sudo
  [            Leer            ]
  2026-10-15 09:31:02 INFO …
  2026-10-15 09:31:05 ERROR … Traceback       <- ERROR/CRITICAL en rojo, WARNING naranja

La ruta que uses se recuerda en el equipo. Si dice "Permission denied",
activa "con sudo" (usa la contraseña guardada).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import notify
from modulos.kraken import routes
from modulos.kraken.comun import MONO, copy_text
from modulos.kraken.models import Equipo
from modulos.kraken.models.red import LOG_POR_DEFECTO
from modulos.kraken.ssh import acciones
from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly

LINEAS = {"100": "Últimas 100", "200": "Últimas 200", "500": "Últimas 500",
          "1000": "Últimas 1,000"}
SUGERIDOS = ["/var/log/odoo/odoo-server.log", "/var/log/nginx/error.log",
             "/var/log/postgresql/postgresql-16-main.log", "/var/log/syslog"]


def line_color(linea: str):  # propio
    alto = linea.upper()
    if " ERROR " in alto or " CRITICAL " in alto or "TRACEBACK" in alto or "EXCEPTION" in alto:
        return ft.Colors.RED
    if " WARNING " in alto or " WARN " in alto:
        return ft.Colors.ORANGE
    return None


class LogsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.equipo: Equipo | None = None
        self.activo = False
        self.texto = ""
        self.leyendo = False

        self.titulo = ft.Text()
        self.txt_ruta = ft.TextField(label="Archivo", expand=True, dense=True,
                                     text_style=ft.TextStyle(font_family=MONO), autocorrect=False,
                                     capitalization=ft.TextCapitalization.NONE,
                                     on_submit=lambda e: self.page.run_task(self.read))
        self.sugeridos = ft.Row(wrap=True, spacing=6, run_spacing=6, controls=[
            ft.Chip(label=ft.Text(r.rsplit("/", 1)[-1], size=11),
                    on_click=lambda e, x=r: self._use(x)) for r in SUGERIDOS])
        self.dd_lineas = ft.Dropdown(value="200", width=185, dense=True,
                                     options=[ft.DropdownOption(key=k, text=v)
                                              for k, v in LINEAS.items()])
        self.txt_buscar = ft.TextField(hint_text="Buscar (error, traceback…)", dense=True,
                                       expand=True, prefix_icon=ft.Icons.SEARCH,
                                       on_submit=lambda e: self.page.run_task(self.read))
        self.chk_sudo = ft.Checkbox(label="con sudo", value=False)
        self.btn_leer = ft.FilledButton("Leer", icon=ft.Icons.REFRESH, expand=True,
                                        on_click=lambda e: self.page.run_task(self.read))
        self.lbl_info = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.salida = ft.Container(padding=10, border_radius=8, expand=True,
                                   bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST)
        self.vista = ft.View(
            route=routes.SSH_LOGS,
            appbar=ft.AppBar(title=self.titulo, actions=[
                ft.IconButton(ft.Icons.COPY, tooltip="Copiar todo",
                              on_click=lambda e: self.page.run_task(copy_text, self.page,
                                                                    self.texto))]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                ft.Row([self.txt_ruta]), self.sugeridos,
                ft.Row([self.dd_lineas, self.txt_buscar]), self.chk_sudo,
                ft.Row([self.btn_leer]), self.lbl_info, ft.Row([self.salida]),
                ft.Container(height=30)]))],
        )

    def open(self, equipo: Equipo):  # propio
        self.equipo = Equipo.get(equipo.id)
        self.activo = True
        self.titulo.value = f"Logs · {self.equipo.nombre}"
        self.txt_ruta.value = self.equipo.ssh_log or LOG_POR_DEFECTO
        self.texto = ""
        self.salida.content = ft.Text("Toca Leer.", italic=True, color=ft.Colors.OUTLINE)
        self.lbl_info.value = ""
        self.page.navigate(routes.SSH_LOGS)
        self.page.run_task(self.read)

    def close(self):  # propio
        self.activo = False

    def _use(self, ruta: str):  # propio
        self.txt_ruta.value = ruta
        self.page.run_task(self.read)

    async def read(self):  # propio
        if self.leyendo or not self.equipo:
            return
        ruta = (self.txt_ruta.value or "").strip()
        if not ruta:
            notify(self.page, "Escribe la ruta del archivo")
            return
        self.leyendo = True
        self.btn_leer.disabled = True
        self.lbl_info.value = "Leyendo…"
        self.page.update()
        try:
            salida = await asyncio.to_thread(self._read_blocking, ruta)
        except HuellaCambio:
            self.lbl_info.value = "La huella del servidor cambió: ábrelo desde el panel para revisarla."
            salida = None
        except Exception as ex:  # noqa: BLE001
            self.lbl_info.value = friendly(ex, self.equipo)
            salida = None
        finally:
            self.leyendo = False
            self.btn_leer.disabled = False
        if salida is not None:
            if ruta != (self.equipo.ssh_log or ""):
                self.equipo = Equipo.update(self.equipo.id, ssh_log=ruta)
            self._show(salida)
        if self.activo:
            self.page.update()

    def _read_blocking(self, ruta: str):  # propio
        with Sesion(self.equipo) as sesion:
            return acciones.read_log(sesion, ruta, int(self.dd_lineas.value or 200),
                                     self.txt_buscar.value or "", bool(self.chk_sudo.value))

    def _show(self, salida):  # propio
        self.texto = salida.texto
        lineas = salida.texto.splitlines()
        if salida.errores.strip() and not lineas:
            permiso = "permission denied" in salida.errores.lower()
            self.lbl_info.value = ("Sin permiso para leerlo: activa «con sudo» y vuelve a leer."
                                   if permiso else salida.errores.strip()[:300])
            self.salida.content = ft.Text(salida.errores.strip(), font_family=MONO, size=11,
                                          color=ft.Colors.RED, selectable=True)
            return
        buscar = (self.txt_buscar.value or "").strip()
        self.lbl_info.value = (f"{len(lineas)} línea{'s' if len(lineas) != 1 else ''}"
                               + (f" con «{buscar}»" if buscar else "")
                               + f" · {salida.tiempo_ms} ms")
        if not lineas:
            self.salida.content = ft.Text("(nada)" if not buscar else "Nada coincide.",
                                          italic=True, color=ft.Colors.OUTLINE)
            return
        self.salida.content = ft.Text(
            selectable=True, size=11, font_family=MONO,
            spans=[ft.TextSpan(linea + "\n", style=ft.TextStyle(color=line_color(linea)))
                   for linea in lineas[-1000:]])

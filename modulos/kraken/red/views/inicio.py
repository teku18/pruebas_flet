"""
Red (/kraken/red):

  ← Red                                         [🕘 historial] [⚙]
  Mis equipos                                   [+ Agregar]
  ┌ 🖥 Servidor casa   192.168.1.10 · 22, 8069  ┐  tocar: ping, puertos,
  └ 🖥 Router          192.168.1.1              ┘  certificado, encender…
  Pruebas
  [Ping] [Puertos] [DNS] [Mi IP] [Certificado] [Whois] [Wake-on-LAN]

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import confirm, icon_box, notify
from modulos.kraken import routes
from modulos.kraken.models import Equipo
from modulos.kraken.red.herramientas import PRUEBAS, Prueba
from modulos.kraken.red.views.ajustes import network_settings_dialog
from modulos.kraken.red.views.equipos import equipment_dialog


class NetworkHome:
    def __init__(self, page: ft.Page, on_test):
        """on_test(clave, objetivo="", puertos_texto=None, ejecutar=False): abre una prueba."""
        self.page = page
        self.on_test = on_test
        self.lista_equipos = ft.Column(spacing=4)
        self.vista = ft.View(
            route=routes.RED,
            appbar=ft.AppBar(title=ft.Text("Red"), actions=[
                ft.IconButton(ft.Icons.HISTORY, tooltip="Historial",
                              on_click=lambda e: page.navigate(routes.RED_HISTORIAL)),
                ft.IconButton(ft.Icons.SETTINGS, tooltip="Ajustes de Red",
                              on_click=lambda e: network_settings_dialog(page)),
            ]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                    ft.Text("Mis equipos", size=16, weight=ft.FontWeight.BOLD, expand=True),
                    ft.TextButton("Agregar", icon=ft.Icons.ADD,
                                  on_click=lambda e: self.new_equipment())]),
                self.lista_equipos,
                ft.Text("Pruebas", size=16, weight=ft.FontWeight.BOLD),
                ft.ResponsiveRow(spacing=10, run_spacing=10,
                                 controls=[self._card(p) for p in PRUEBAS]),
                ft.Container(height=30),
            ]))],
        )

    def load(self):  # propio
        equipos = Equipo.search_all()
        if not equipos:
            self.lista_equipos.controls = [ft.Text(
                "Guarda aquí tus servidores, router o PC para probarlos con un toque.",
                size=12, color=ft.Colors.OUTLINE)]
        else:
            self.lista_equipos.controls = [self._equipment_row(e) for e in equipos]

    def refresh(self):  # propio
        self.load()
        self.page.update()

    # ==================================================================
    def _card(self, p: Prueba) -> ft.Control:  # propio
        return ft.Card(
            col={"xs": 6, "md": 4},
            content=ft.Container(
                padding=12, ink=True, border_radius=12,
                on_click=lambda e: self.on_test(p.clave),
                content=ft.Column(spacing=6, controls=[
                    icon_box(p.icono, p.color),
                    ft.Text(p.nombre, weight=ft.FontWeight.BOLD),
                    ft.Text(p.descripcion, size=11, color=ft.Colors.OUTLINE, max_lines=2),
                ])))

    def _equipment_row(self, e: Equipo) -> ft.Control:  # propio
        detalle = e.host + (f" · {e.puertos}" if e.puertos else "")
        return ft.Card(content=ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8), ink=True, border_radius=12,
            on_click=lambda ev: self.actions(e),
            content=ft.Row(spacing=12, controls=[
                ft.Icon(ft.Icons.DNS, color=ft.Colors.TEAL),
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(e.nombre, weight=ft.FontWeight.W_500, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(detalle, size=12, color=ft.Colors.OUTLINE, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS)]),
                ft.Icon(ft.Icons.POWER_SETTINGS_NEW, size=16, color=ft.Colors.OUTLINE,
                        visible=bool(e.mac), tooltip="Tiene MAC: se puede encender"),
            ])))

    def actions(self, e: Equipo):  # propio
        """Lo que se puede hacer con un equipo (hoja de abajo)."""
        def go(clave: str, objetivo: str, puertos_texto: str | None = None):  # propio
            self.page.pop_dialog()
            self.on_test(clave, objetivo, puertos_texto, ejecutar=True)

        opciones = [
            (ft.Icons.NETWORK_PING, "Ping", lambda: go("ping", e.host)),
            (ft.Icons.SETTINGS_ETHERNET, "Revisar sus puertos" + (f" ({e.puertos})" if e.puertos
                                                                   else " comunes"),
             lambda: go("puertos", e.host, e.puertos)),
            (ft.Icons.VERIFIED_USER, "Certificado HTTPS", lambda: go("cert", e.host)),
            (ft.Icons.TRAVEL_EXPLORE, "DNS", lambda: go("dns", e.host)),
        ]
        if e.mac:
            opciones.append((ft.Icons.POWER_SETTINGS_NEW, "Encender (Wake-on-LAN)",
                             lambda: go("wol", e.mac)))
        opciones += [
            (ft.Icons.EDIT, "Editar", lambda: (self.page.pop_dialog(), self.edit(e))),
            (ft.Icons.DELETE, "Eliminar", lambda: (self.page.pop_dialog(), self.delete(e))),
        ]
        self.page.show_dialog(ft.BottomSheet(
            show_drag_handle=True,
            content=ft.Container(padding=ft.Padding.only(bottom=20), content=ft.Column(
                tight=True, spacing=0, controls=[
                    ft.ListTile(title=ft.Text(e.nombre, weight=ft.FontWeight.BOLD),
                                subtitle=ft.Text(e.host + (f" · MAC {e.mac}" if e.mac else ""))),
                    *(ft.ListTile(leading=ft.Icon(icono), title=ft.Text(texto),
                                  on_click=lambda ev, f=accion: f())
                      for icono, texto, accion in opciones)])),
        ))

    def new_equipment(self):  # propio
        equipment_dialog(self.page, None, lambda eq: self.refresh())

    def edit(self, e: Equipo):  # propio
        equipment_dialog(self.page, e, lambda eq: self.refresh())

    def delete(self, e: Equipo):  # propio
        def ok():  # propio
            Equipo.delete(e.id)
            notify(self.page, "Equipo eliminado (su historial se queda)")
            self.refresh()
        confirm(self.page, "Eliminar equipo", f"¿Quitar «{e.nombre}» de Mis equipos?", ok)

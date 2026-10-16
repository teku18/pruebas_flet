"""
SSH (/kraken/ssh): tus servidores.

  🖥 Cliente ACME         edgar@201.1.2.3:22          ⋮
  🖥 Mi PC                edgar@192.168.0.217:22      ⋮
  Tus otros equipos (sin SSH): Router  [+ SSH]
                                              [+ Agregar servidor]

Son los mismos "Mis equipos" de Red: un equipo con usuario SSH aparece aquí.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, icon_box
from modulos.kraken import routes
from modulos.kraken.comun import empty_state
from modulos.kraken.models import Equipo
from modulos.kraken.red.views.equipos import equipment_dialog
from modulos.kraken.ssh.views.comandos import commands_manager


class ServersView:
    def __init__(self, page: ft.Page, on_open):
        """on_open(equipo): abre su panel."""
        self.page = page
        self.on_open = on_open
        self.lista = ft.Column(spacing=6)
        self.vista = ft.View(
            route=routes.SSH,
            appbar=ft.AppBar(title=ft.Text("SSH"), actions=[
                ft.IconButton(ft.Icons.PUBLIC, tooltip="Exponer puertos (ngrok / Cloudflare)",
                              on_click=lambda e: page.navigate(routes.SSH_TUNELES)),
                ft.IconButton(ft.Icons.PLAYLIST_PLAY, tooltip="Comandos guardados",
                              on_click=lambda e: commands_manager(page, None))]),
            scroll=ft.ScrollMode.AUTO,
            floating_action_button=add_button("Agregar servidor", lambda e: self.new()),
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                self.lista, ft.Container(height=80)]))],
        )

    def load(self):  # propio
        equipos = Equipo.search_all()
        servidores = [e for e in equipos if e.tiene_ssh]
        otros = [e for e in equipos if not e.tiene_ssh]
        controles: list[ft.Control] = [self._row(e) for e in servidores] or [empty_state(
            ft.Icons.TERMINAL, "Tu primer servidor",
            "Agrega un servidor con su usuario y contraseña SSH para ver su CPU, memoria, "
            "discos y servicios, leer sus logs y correr comandos como «Reiniciar Odoo».")]
        if otros:
            controles.append(ft.Container(padding=ft.Padding.only(top=12), content=ft.Text(
                "Tus otros equipos (sin SSH)", size=13, weight=ft.FontWeight.BOLD,
                color=ft.Colors.OUTLINE)))
            controles += [ft.Row(controls=[
                ft.Text(f"{e.nombre} · {e.host}", expand=True, size=13),
                ft.TextButton("SSH", icon=ft.Icons.ADD, on_click=lambda ev, x=e: self.edit(x))])
                for e in otros]
        self.lista.controls = controles

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _row(self, e: Equipo) -> ft.Control:  # propio
        return ft.Card(content=ft.Container(
            padding=12, ink=True, border_radius=12, on_click=lambda ev: self.on_open(e),
            content=ft.Row(spacing=12, controls=[
                icon_box(ft.Icons.DNS, ft.Colors.PURPLE),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(e.nombre, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{e.ssh_usuario}@{e.host}:{e.ssh_puerto or 22}", size=12,
                            color=ft.Colors.OUTLINE, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS)]),
                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                    ft.PopupMenuItem(content=ft.Text("Editar"), icon=ft.Icons.EDIT,
                                     on_click=lambda ev: self.edit(e)),
                    ft.PopupMenuItem(content=ft.Text("Sus comandos"), icon=ft.Icons.PLAYLIST_PLAY,
                                     on_click=lambda ev: commands_manager(self.page, e)),
                ]),
            ])))

    def new(self):  # propio
        equipment_dialog(self.page, None, lambda eq: self.refresh(), ssh=True)

    def edit(self, e: Equipo):  # propio
        equipment_dialog(self.page, e, lambda eq: self.refresh(), ssh=True)

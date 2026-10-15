"""
Historial de Red (/kraken/red/historial): todas las pruebas, la más nueva arriba.

  (Todas) (Ping) (Puertos) (DNS) …
  ✓ Ping       192.168.1.10   4/4 · 3.2 ms          14:32
  ✗ Certificado viejo.com     Venció hace 3 días     ayer

Tocar una la abre con su resultado (y se puede volver a ejecutar).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft

from modulos.kraken import routes
from modulos.kraken.comun import empty_state, tabs_row
from modulos.kraken.models import HistorialRed
from modulos.kraken.red import historial
from modulos.kraken.red.herramientas import POR_CLAVE, PRUEBAS


class NetworkHistoryView:
    def __init__(self, page: ft.Page, on_open):
        """on_open(fila_del_historial)."""
        self.page = page
        self.on_open = on_open
        self.filtro: str | None = None
        self.filtros = ft.Container()
        self.lista = ft.ListView(expand=True, spacing=2, padding=ft.Padding.only(bottom=40))
        self.vista = ft.View(
            route=routes.RED_HISTORIAL,
            appbar=ft.AppBar(title=ft.Text("Historial de Red")),
            controls=[ft.SafeArea(expand=True, content=ft.Column(
                expand=True, spacing=8, controls=[self.filtros, self.lista]))],
        )

    def load(self):  # propio
        self.filtros.content = tabs_row(
            [("", "Todas"), *((p.clave, p.nombre) for p in PRUEBAS)], self.filtro or "",
            self.set_filter)
        pruebas = historial.history(self.filtro)
        self.lista.controls = [self._row(h) for h in pruebas] or [
            empty_state(ft.Icons.HISTORY, "Sin pruebas", "Lo que corras en Red aparece aquí.")]

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def set_filter(self, clave: str):  # propio
        self.filtro = clave or None
        self.refresh()

    def _row(self, h: HistorialRed) -> ft.Control:  # propio
        p = POR_CLAVE.get(h.herramienta)
        cuando = (f"{h.creado_en:%H:%M}" if h.creado_en.date() == date.today()
                  else f"{h.creado_en:%d/%m/%y}")
        return ft.Container(
            ink=True, border_radius=8, padding=ft.Padding.symmetric(horizontal=6, vertical=8),
            on_click=lambda e: self.on_open(h),
            content=ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE if h.exito else ft.Icons.CANCEL, size=20,
                        color=ft.Colors.GREEN if h.exito else ft.Colors.RED),
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(f"{p.nombre if p else h.herramienta.upper()} · {h.objetivo}",
                            weight=ft.FontWeight.W_500, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(h.resumen, size=12, color=ft.Colors.OUTLINE, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS)]),
                ft.Text(cuando, size=11, color=ft.Colors.OUTLINE),
            ]))

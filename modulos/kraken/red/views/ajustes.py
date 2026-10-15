"""
Diálogo ⚙ Ajustes de Red (en la BD: viajan en el respaldo).

  Servidor DNS   [1.1.1.1        ]   (Cloudflare) (Google) (Quad9) (OpenDNS)
  Guardar en el historial  [200 pruebas ▾]
  Hoy: 37 pruebas guardadas       [Borrar historial]
"""
import flet as ft

from core.ui import confirm, dropdown_options, notify
from modulos.kraken.comun import MONO
from modulos.kraken.models import Ajustes
from modulos.kraken.models.ajustes import DNS_SUGERIDOS, HISTORIAL_OPCIONES
from modulos.kraken.red import historial
from modulos.kraken.red.consulta_dns import parse_server


def network_settings_dialog(page: ft.Page):  # propio
    a = Ajustes.current()
    resumen = ft.Text(size=12, color=ft.Colors.OUTLINE)
    txt_dns = ft.TextField(label="Servidor DNS", value=a.dns_servidor, expand=True,
                           text_style=ft.TextStyle(font_family=MONO))

    def refresh_stats():  # propio
        n = historial.count()
        resumen.value = f"Hoy: {n} prueba{'s' if n != 1 else ''} guardada{'s' if n != 1 else ''}"

    def save_dns(e=None):  # propio
        valor = (txt_dns.value or "").strip()
        try:
            parse_server(valor)
        except ValueError as ex:
            txt_dns.error = str(ex)
            txt_dns.update()
            return
        txt_dns.error = None
        if valor != Ajustes.current().dns_servidor:
            Ajustes.change(dns_servidor=valor)
            notify(page, f"Servidor DNS: {valor}")
        txt_dns.update()

    def suggest(ip: str):  # propio
        txt_dns.value = ip
        save_dns()

    def change_max(valor: str):  # propio
        Ajustes.change(red_historial_max=int(valor))
        borrados = historial.prune(int(valor))
        if borrados:
            notify(page, f"Se borraron {borrados} pruebas viejas")
        refresh_stats()
        resumen.update()

    def clear(e):  # propio
        def ok():  # propio
            historial.clear()
            refresh_stats()
            page.update()
        confirm(page, "Borrar historial", "¿Borrar todas las pruebas de Red guardadas?", ok)

    txt_dns.on_submit = save_dns
    txt_dns.on_blur = save_dns
    refresh_stats()
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Ajustes de Red"),
        content=ft.Container(width=460, content=ft.Column(
            tight=True, spacing=12, controls=[
                ft.Row([txt_dns]),
                ft.Text("La herramienta DNS le pregunta a este servidor (no cambia el "
                        "internet de tu celular).", size=12, color=ft.Colors.OUTLINE),
                ft.Row(wrap=True, spacing=6, run_spacing=6, controls=[
                    ft.Chip(label=ft.Text(f"{nombre} {ip}", size=12),
                            on_click=lambda e, x=ip: suggest(x))
                    for ip, nombre in DNS_SUGERIDOS.items()]),
                ft.Row([ft.Dropdown(
                    label="Guardar en el historial (pruebas)", expand=True,
                    value=str(a.red_historial_max),
                    options=dropdown_options({str(k): v for k, v in HISTORIAL_OPCIONES.items()}),
                    on_select=lambda e: change_max(e.control.value))]),
                resumen,
                ft.Row([ft.TextButton("Borrar historial", icon=ft.Icons.DELETE_SWEEP,
                                      style=ft.ButtonStyle(color=ft.Colors.RED),
                                      on_click=clear)]),
            ])),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: (save_dns(), page.pop_dialog()))],
    ))

"""
Diálogo ⚙ Ajustes del cliente HTTP (se guardan en la BD: viajan en el respaldo).

  Guardar en el historial   [200 envíos ▾]      (50 … 1,000 o sin límite)
  De cada respuesta guardar [256 KB ▾]          (64 KB … 20 MB o completa)
  Esperar respuesta         [30 s ▾]
  Hoy: 37 envíos · 1.2 MB          [Borrar historial]

En pantalla SIEMPRE ves la respuesta completa (hasta 50 MB); el recorte es
solo para lo que se guarda en el historial.
"""
import flet as ft

from core.storage import human_size
from core.ui import confirm, dropdown_options, notify
from modulos.kraken.http import services
from modulos.kraken.models import Ajustes
from modulos.kraken.models.ajustes import (HISTORIAL_OPCIONES, RESPUESTA_OPCIONES,
                                           TIMEOUT_OPCIONES)


def settings_dialog(page: ft.Page, on_changed=None):  # propio
    a = Ajustes.current()
    resumen = ft.Text(size=12, color=ft.Colors.OUTLINE)

    def refresh_stats():  # propio
        n, peso = services.history_stats()
        resumen.value = f"Hoy: {n} envío{'s' if n != 1 else ''} guardados · {human_size(peso)}"

    def change(campo: str, valor: str):  # propio
        Ajustes.change(**{campo: int(valor)})
        if campo == "historial_max":
            borrados = services.prune_history(int(valor))
            if borrados:
                notify(page, f"Se borraron {borrados} envíos viejos")
        refresh_stats()
        resumen.update()
        if on_changed:
            on_changed()

    def dropdown(etiqueta: str, campo: str, opciones: dict) -> ft.Control:  # propio
        return ft.Row([ft.Dropdown(
            label=etiqueta, value=str(getattr(a, campo)), expand=True,
            options=dropdown_options({str(k): v for k, v in opciones.items()}),
            on_select=lambda e: change(campo, e.control.value))])

    def clear(e):  # propio
        def ok():  # propio
            services.clear_history()
            refresh_stats()
            page.update()
            if on_changed:
                on_changed()
        confirm(page, "Borrar historial", "¿Borrar todos los envíos guardados?", ok)

    refresh_stats()
    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Ajustes del cliente HTTP"),
        content=ft.Container(width=460, content=ft.Column(
            tight=True, spacing=14, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[
            dropdown("Guardar en el historial (envíos)", "historial_max", HISTORIAL_OPCIONES),
            dropdown("De cada respuesta guardar", "respuesta_max_kb", RESPUESTA_OPCIONES),
            dropdown("Esperar la respuesta hasta", "timeout_s", TIMEOUT_OPCIONES),
            ft.Text("En pantalla siempre ves la respuesta completa; el límite es solo para "
                    "lo que se guarda (y se respalda).", size=12, color=ft.Colors.OUTLINE),
            ft.Row([resumen], wrap=True),
            ft.Row([ft.TextButton("Borrar historial", icon=ft.Icons.DELETE_SWEEP,
                                  style=ft.ButtonStyle(color=ft.Colors.RED), on_click=clear)]),
        ])),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))

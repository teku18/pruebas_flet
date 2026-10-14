"""
Sección "Avisos" de Configuración: ¿llegan los avisos de la Agenda?

  Avisos
  Notificaciones: ✓ permitidas        Hora exacta: ✓ / ✗ (pueden llegar unos min tarde)
  Próximo: «Pagar renta» · mañana 8:00 · 5 programados
  [🔔 Probar aviso]  [⏰ Permitir hora exacta]  [⚙ Ajustes de notificaciones]
  Tip Xiaomi / Redmi: Inicio automático + batería "Sin restricciones"

En la compu solo muestra el próximo aviso (los avisos llegan en el celular).
El trabajo de verdad lo hace core/avisos.py.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date, timedelta

import flet as ft

from core import avisos
from core.database import ES_MOVIL
from core.ui import notify


def when_text(cuando) -> str:  # propio
    """'hoy 9:45', 'mañana 8:00' o '20/10 8:00'."""
    hoy = date.today()
    if cuando.date() == hoy:
        dia = "hoy"
    elif cuando.date() == hoy + timedelta(days=1):
        dia = "mañana"
    else:
        dia = f"{cuando:%d/%m}"
    return f"{dia} {cuando:%H:%M}"


class NotificationsSection:
    def __init__(self, page: ft.Page):
        self.page = page
        self.lbl_estado = ft.Text(size=13)
        self.lbl_proximo = ft.Text(size=13, color=ft.Colors.OUTLINE)
        botones = []
        if ES_MOVIL:
            botones = [
                ft.OutlinedButton("Probar aviso", icon=ft.Icons.NOTIFICATIONS_ACTIVE,
                                  on_click=lambda e: self.page.run_task(self.test)),
                ft.OutlinedButton("Permitir hora exacta", icon=ft.Icons.ALARM,
                                  on_click=lambda e: self.page.run_task(self.allow_exact)),
                ft.TextButton("Ajustes de notificaciones", icon=ft.Icons.SETTINGS,
                              on_click=lambda e: self.page.run_task(self.open_settings)),
            ]
        consejo = ft.Text(
            "Xiaomi / Redmi (HyperOS): para que los avisos lleguen aunque pases días "
            "sin abrir la app, en Ajustes → Apps → ControlKraken activa «Inicio "
            "automático» y en Ahorro de batería elige «Sin restricciones».",
            size=12, color=ft.Colors.OUTLINE, visible=ES_MOVIL,
        )
        self.controles = [
            ft.Text("Avisos", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Las tareas de la Agenda te avisan aunque la app esté cerrada. "
                "Cada tarea elige cuándo (a la hora, 15 min antes…; sin hora: 8:00 am).",
                size=12, color=ft.Colors.OUTLINE,
            ),
            self.lbl_estado,
            self.lbl_proximo,
            ft.Row(wrap=True, controls=botones),
            consejo,
        ]

    async def load(self):  # propio
        """Estado de permisos y el próximo aviso (se llama al abrir Configuración)."""
        lista = avisos.upcoming()
        if lista:
            a = lista[0]
            self.lbl_proximo.value = (f"Próximo: «{a.titulo}» · {when_text(a.cuando)}"
                                      f" · {len(lista)} programado(s) en 2 semanas")
        else:
            self.lbl_proximo.value = "No hay avisos en las próximas 2 semanas."
        if not ES_MOVIL:
            self.lbl_estado.value = "Los avisos llegan en el celular (en la compu no)."
            return
        actual = avisos.current()
        estado = await actual.status() if actual else {"permitidos": False, "exactos": False}
        self.lbl_estado.value = (
            ("Notificaciones: ✓ permitidas" if estado["permitidos"]
             else "Notificaciones: ✗ sin permiso (toca «Ajustes de notificaciones»)")
            + (" · Hora exacta: ✓" if estado["exactos"]
               else " · Hora exacta: ✗ (pueden llegar unos minutos tarde)")
        )
        self.lbl_estado.color = None if estado["permitidos"] else ft.Colors.ORANGE

    async def refresh(self):  # propio
        await self.load()
        self.page.update()

    async def test(self):  # propio
        actual = avisos.current()
        if actual and await actual.test():
            notify(self.page, "Aviso enviado: revisa tus notificaciones")
        else:
            notify(self.page, "No se pudo: revisa el permiso de notificaciones")

    async def allow_exact(self):  # propio
        actual = avisos.current()
        if actual:
            await actual.ask_exact()
            await actual.sync()  # reprograma con el modo que ahora corresponda
        await self.refresh()

    async def open_settings(self):  # propio
        actual = avisos.current()
        if actual:
            await actual.open_settings()

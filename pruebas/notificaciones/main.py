"""
PRUEBA (no es parte de ControlKraken): ¿llegan las notificaciones programadas
con la app CERRADA usando flet-android-notifications sobre Flet 1.0?

Es una app aparte (otro id: com.teku18.cknotifprueba), así que se instala
junto a ControlKraken sin tocarlo.

Botones:
  1. Pedir permisos        -> notificaciones (Android 13+) y alarmas exactas
  2. Notificación ahora    -> ¿compila y se ve una notificación?
  3. Programar en 2 min    -> dos avisos: uno "exacto" y uno "inexacto"
  4. Ver programadas       -> lo que Android tiene pendiente

La prueba de verdad: programa, CIERRA la app (deslízala fuera de recientes),
bloquea el celular y espera 2-5 minutos.
"""
from datetime import datetime, timedelta

import flet as ft
from flet_android_notifications import FletAndroidNotifications

CANAL = dict(channel_id="ck_prueba", channel_name="Prueba de avisos",
             channel_description="Avisos de prueba de ControlKraken")


def main(page: ft.Page):
    page.title = "CK · Prueba de avisos"
    avisos = FletAndroidNotifications()
    page.services.append(avisos)  # mismo truco que core.ui.service()

    log = ft.ListView(expand=True, spacing=4, auto_scroll=True)

    def write(texto: str):
        log.controls.append(ft.Text(f"{datetime.now():%H:%M:%S}  {texto}", size=13))
        page.update()

    async def permissions(e):
        try:
            write(f"Notificaciones: {'✓' if await avisos.request_permissions() else '✗'}")
            write(f"Alarmas exactas: {'✓' if await avisos.request_exact_alarm_permission() else '✗'}")
        except Exception as ex:  # noqa: BLE001
            write(f"Error permisos: {ex!r}")

    async def now(e):
        try:
            await avisos.show_notification(1, "ControlKraken", "Notificación inmediata ✓",
                                           **CANAL)
            write("Mostrada la inmediata")
        except Exception as ex:  # noqa: BLE001
            write(f"Error inmediata: {ex!r}")

    async def schedule(e):
        cuando = datetime.now() + timedelta(minutes=2)
        for nid, modo in ((2, "exact_allow_while_idle"), (3, "inexact_allow_while_idle")):
            try:
                await avisos.schedule_notification(
                    nid, f"Aviso {modo.split('_')[0]}",
                    f"Programado para las {cuando:%H:%M:%S}", cuando,
                    schedule_mode=modo, time_zone="America/Mexico_City", **CANAL,
                )
                write(f"Programado #{nid} ({modo}) para {cuando:%H:%M:%S}")
            except Exception as ex:  # noqa: BLE001
                write(f"Error #{nid} ({modo}): {ex!r}")
        write("Ahora CIERRA la app y bloquea el celular.")

    async def pending(e):
        try:
            lista = await avisos.get_pending_notifications()
            write(f"Programadas: {len(lista)} {[p.get('id') for p in lista]}")
        except Exception as ex:  # noqa: BLE001
            write(f"Error pendientes: {ex!r}")

    page.add(ft.SafeArea(expand=True, content=ft.Column(expand=True, controls=[
        ft.Text("Prueba de avisos con la app cerrada", size=18, weight=ft.FontWeight.BOLD),
        ft.Button("1. Pedir permisos", on_click=permissions),
        ft.Button("2. Notificación ahora", on_click=now),
        ft.Button("3. Programar en 2 min", on_click=schedule),
        ft.Button("4. Ver programadas", on_click=pending),
        ft.Divider(),
        log,
    ])))


ft.run(main)

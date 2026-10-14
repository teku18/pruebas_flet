"""
Avisos (notificaciones) en el celular, aunque la app esté CERRADA.

Python solo corre con la app abierta. Por eso no "esperamos" la hora: le
pedimos a Android que nos despierte (AlarmManager) y él muestra el aviso.

  app abierta ──► Avisos.sync(): borra lo programado y programa lo que viene
                         │        (los próximos HORIZONTE_DIAS días)
  app cerrada            ▼  a la hora indicada
                 Android muestra la notificación (Python ni se entera)

Quién dice QUÉ avisar: los "proveedores". Cada módulo registra una función
    proveedor(desde: datetime, hasta: datetime) -> list[Aviso]
(la Agenda registra sus tareas en modulos/agenda/avisos.py). Así un módulo
nuevo (Notas, Kraken Tools) agrega recordatorios sin tocar este archivo.

Cuándo se reprograma:
  - al abrir la app (on_start de la Agenda)
  - cada vez que cambia algo que avisa (request_sync(), con una pausa corta
    para juntar varios cambios seguidos en una sola reprogramación)

La parte de Android la hace la extensión flet-android-notifications (Flutter
flutter_local_notifications). En la compu no hay avisos: todo aquí se vuelve
"no hacer nada" y la app funciona igual.
"""
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import flet as ft

from core.database import ES_MOVIL

HORIZONTE_DIAS = 14       # se programa lo que cae en las próximas 2 semanas
MAXIMO = 200              # Android limita las alarmas por app (~500): margen de sobra
PAUSA_SEGUNDOS = 1.5      # junta varios cambios seguidos en una sola reprogramación
CANAL = dict(channel_id="ck_agenda", channel_name="Agenda",
             channel_description="Avisos de tus tareas")


@dataclass
class Aviso:
    cuando: datetime   # hora local (sin zona): la del celular
    titulo: str
    cuerpo: str


Proveedor = Callable[[datetime, datetime], list[Aviso]]
_PROVEEDORES: list[Proveedor] = []


def register_provider(proveedor: Proveedor) -> None:  # propio
    """Un módulo dice "yo también tengo cosas que avisar"."""
    if proveedor not in _PROVEEDORES:
        _PROVEEDORES.append(proveedor)


def upcoming(ahora: datetime | None = None) -> list[Aviso]:  # propio
    """Todo lo que hay que avisar desde ahora y hasta HORIZONTE_DIAS, en orden."""
    ahora = ahora or datetime.now()
    hasta = ahora + timedelta(days=HORIZONTE_DIAS)
    avisos = []
    for proveedor in _PROVEEDORES:
        avisos += [a for a in proveedor(ahora, hasta) if ahora < a.cuando <= hasta]
    return sorted(avisos, key=lambda a: a.cuando)[:MAXIMO]


class Avisos:
    """Habla con Android. Una por página (ver install())."""

    def __init__(self, page: ft.Page):
        self.page = page
        self._turno = 0  # para la pausa: solo la última petición reprograma

    # --- La extensión (solo en el celular) ------------------------------
    def _service(self):  # propio
        from flet_android_notifications import FletAndroidNotifications

        from core.ui import service

        return service(self.page, FletAndroidNotifications)

    # --- Permisos -------------------------------------------------------
    async def ask_permission(self) -> bool:  # propio
        """Android 13+: el diálogo "¿Permitir notificaciones?" (si ya diste permiso, no sale)."""
        if not ES_MOVIL:
            return False
        try:
            return await self._service().request_permissions()
        except Exception as ex:  # noqa: BLE001
            print(f"[avisos] permiso: {ex!r}")
            return False

    async def ask_exact(self) -> bool:  # propio
        """Abre el ajuste de Android "Alarmas y recordatorios" (avisos a la hora exacta)."""
        if not ES_MOVIL:
            return False
        try:
            return await self._service().request_exact_alarm_permission()
        except Exception as ex:  # noqa: BLE001
            print(f"[avisos] alarmas exactas: {ex!r}")
            return False

    async def status(self) -> dict:  # propio
        """{"permitidos": bool, "exactos": bool} (en la compu, todo False)."""
        if not ES_MOVIL:
            return {"permitidos": False, "exactos": False}
        try:
            svc = self._service()
            return {"permitidos": await svc.are_notifications_enabled(),
                    "exactos": await svc.can_schedule_exact_notifications()}
        except Exception as ex:  # noqa: BLE001
            print(f"[avisos] estado: {ex!r}")
            return {"permitidos": False, "exactos": False}

    async def open_settings(self) -> None:  # propio
        if ES_MOVIL:
            try:
                await self._service().open_app_notification_settings()
            except Exception as ex:  # noqa: BLE001
                print(f"[avisos] ajustes: {ex!r}")

    async def test(self) -> bool:  # propio
        """Un aviso ahora mismo, para ver que todo funciona."""
        if not ES_MOVIL:
            return False
        try:
            await self._service().show_notification(
                1, "ControlKraken", "Así se verán tus avisos ✓", **CANAL)
            return True
        except Exception as ex:  # noqa: BLE001
            print(f"[avisos] prueba: {ex!r}")
            return False

    # --- Programar ------------------------------------------------------
    async def sync(self) -> int:  # propio
        """
        Borra lo programado y programa lo que viene. Regresa cuántos quedaron.
        Se borra TODO y se vuelve a armar: así nunca queda un aviso de una
        tarea que ya cambiaste, hiciste o borraste.
        """
        if not ES_MOVIL:
            return 0
        avisos = upcoming()
        try:
            svc = self._service()
            exactos = await svc.can_schedule_exact_notifications()
            modo = "exact_allow_while_idle" if exactos else "inexact_allow_while_idle"
            await svc.cancel_all()
            for n, a in enumerate(avisos, start=10):  # 1-9: reservados (prueba)
                # astimezone(): la hora local con la zona del celular (un instante exacto)
                await svc.schedule_notification(n, a.titulo, a.cuerpo, a.cuando.astimezone(),
                                                schedule_mode=modo, **CANAL)
        except Exception as ex:  # noqa: BLE001
            print(f"[avisos] programar: {ex!r}")
            return 0
        return len(avisos)

    def request_sync(self) -> None:  # propio
        """Pide reprogramar "en un momento" (varios cambios seguidos = una sola vez)."""
        if not ES_MOVIL:
            return
        self._turno += 1
        self.page.run_task(self._sync_later, self._turno)

    async def _sync_later(self, turno: int):  # propio
        await asyncio.sleep(PAUSA_SEGUNDOS)
        if turno == self._turno:  # nadie pidió otra después: ahora sí
            await self.sync()


_ACTUAL: Avisos | None = None


def install(page: ft.Page) -> Avisos:  # propio
    """Crea (una vez) el objeto de avisos de la app. Lo llama main.py al arrancar."""
    global _ACTUAL
    if _ACTUAL is None or _ACTUAL.page is not page:
        _ACTUAL = Avisos(page)
    return _ACTUAL


def current() -> Avisos | None:  # propio
    """El objeto instalado (None si la app aún no arranca, p. ej. en pruebas)."""
    return _ACTUAL


def request_sync() -> None:  # propio
    """Atajo para los módulos: "algo cambió, reprograma"."""
    if _ACTUAL is not None:
        _ACTUAL.request_sync()

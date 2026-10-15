"""
Una prueba de Red (/kraken/red/prueba): la misma pantalla para todas.

  ← Puertos
  [ 192.168.1.10                     ] [📋 Mis equipos]
  (servidor) (google.com)                       <- lo último que probaste
  [ 22, 80, 443                      ]          <- solo Puertos
  (Comunes) (Web) (Bases de datos) (1-1024)
  [          Ejecutar          ]
  ─────────────────────────────
  resultado (se va pintando mientras corre: ping y puertos)
  [Guardar en Mis equipos]

Cada prueba termina en el historial (Ajustes: cuántas se guardan).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
from datetime import datetime

import flet as ft

from core.ui import notify
from modulos.kraken import routes
from modulos.kraken.comun import MONO
from modulos.kraken.models import Ajustes, Equipo
from modulos.kraken.red import (certificado, consulta_dns, dispositivos, historial, mi_ip, ping,
                                puertos, whois, wol)
from modulos.kraken.red.comun import clean_host
from modulos.kraken.red.herramientas import POR_CLAVE, Prueba
from modulos.kraken.red.views.equipos import equipment_dialog
from modulos.kraken.red.views.resultados import error_box, render

PRESETS_PUERTOS = [
    ("Comunes", ", ".join(map(str, puertos.COMUNES))),
    ("Web", "80, 443, 8000, 8069, 8080, 8443"),
    ("Bases de datos", "1433, 1521, 3306, 5432, 6379, 9200, 27017"),
    ("Remoto", "22, 23, 3389, 5900"),
    ("1-1024", "1-1024"),
]
VECES_PING = {"4": "4 veces", "10": "10 veces", "20": "20 veces"}


class TestView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.prueba: Prueba = POR_CLAVE["ping"]
        self.detalle: dict | None = None     # resultado actual (o del historial)
        self.cuando: datetime | None = None  # si viene del historial
        self.corriendo = False
        self.desde_historial = False
        self._tarea: asyncio.Task | None = None
        self._parcial = None                 # resultado a medias (ping/puertos)

        self.txt_objetivo = ft.TextField(dense=True, expand=True, on_submit=self._submit,
                                         text_style=ft.TextStyle(font_family=MONO),
                                         autocorrect=False, capitalization=ft.TextCapitalization.NONE)
        self.btn_equipos = ft.IconButton(ft.Icons.DEVICES, tooltip="Elegir de Mis equipos",
                                         on_click=lambda e: self.pick_equipment())
        self.fila_objetivo = ft.Row([self.txt_objetivo, self.btn_equipos])
        self.recientes = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.txt_puertos = ft.TextField(label="Puertos", dense=True, expand=True,
                                        hint_text="22, 80, 443 u 8000-8100",
                                        text_style=ft.TextStyle(font_family=MONO))
        self.presets = ft.Row(wrap=True, spacing=6, run_spacing=6, controls=[
            ft.Chip(label=ft.Text(nombre), on_click=lambda e, v=valor: self._preset(v))
            for nombre, valor in PRESETS_PUERTOS])
        self.bloque_puertos = ft.Column(spacing=6, controls=[ft.Row([self.txt_puertos]),
                                                             self.presets])
        self.dd_veces = ft.Dropdown(label="Intentos", value="4", width=160, dense=True,
                                    options=[ft.DropdownOption(key=k, text=v)
                                             for k, v in VECES_PING.items()])
        self.lbl_nota = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.btn_ejecutar = ft.FilledButton("Ejecutar", icon=ft.Icons.PLAY_ARROW, expand=True,
                                            on_click=self.run)
        self.btn_cancelar = ft.OutlinedButton("Cancelar", icon=ft.Icons.STOP, expand=True,
                                              visible=False, on_click=self.cancel)
        self.lbl_cuando = ft.Text(size=12, italic=True, color=ft.Colors.OUTLINE)
        self.resultado = ft.Column(spacing=8)
        self.btn_guardar_equipo = ft.TextButton("Guardar en Mis equipos", icon=ft.Icons.ADD,
                                                on_click=lambda e: self.save_equipment())
        self.titulo = ft.Text()
        self.vista = ft.View(
            route=routes.RED_PRUEBA,
            appbar=ft.AppBar(title=self.titulo),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                self.fila_objetivo, self.recientes, self.bloque_puertos, self.dd_veces,
                self.lbl_nota, ft.Row([self.btn_ejecutar, self.btn_cancelar]),
                ft.Divider(), self.lbl_cuando, self.resultado,
                ft.Row([self.btn_guardar_equipo]), ft.Container(height=30),
            ]))],
        )

    # ==================================================================
    # Abrir
    # ==================================================================
    def open(self, clave: str, objetivo: str = "", puertos_texto: str | None = None,  # propio
             detalle: dict | None = None, cuando: datetime | None = None,
             desde_historial: bool = False, ejecutar: bool = False):
        self.prueba = POR_CLAVE[clave]
        self.detalle, self.cuando = detalle, cuando
        self.desde_historial = desde_historial
        self.txt_objetivo.value = objetivo
        self.txt_objetivo.error = None
        if puertos_texto is not None:
            self.txt_puertos.value = puertos_texto
        elif clave == "puertos" and not self.txt_puertos.value:
            self.txt_puertos.value = PRESETS_PUERTOS[0][1]
        if clave == "dispositivos" and not objetivo:  # tu red, ya escrita
            try:
                self.txt_objetivo.value = str(dispositivos.parse_network(None))
            except ValueError:
                self.txt_objetivo.value = ""
        if clave == "puertos" and detalle:  # del historial: los mismos puertos
            self.txt_puertos.value = ", ".join(str(p["puerto"]) for p in detalle.get("puertos", []))
        self._render_form()
        self._render_result()
        self.page.navigate(routes.RED_PRUEBA)
        if ejecutar or (clave == "mi_ip" and detalle is None):
            self.page.run_task(self.run)

    def _render_form(self):  # propio
        p = self.prueba
        self.titulo.value = p.nombre
        self.fila_objetivo.visible = p.entrada is not None
        self.btn_equipos.visible = p.entrada in ("host", "mac")
        self.txt_objetivo.label = {"host": "IP o dominio", "dominio": "Dominio",
                                   "mac": "MAC del equipo", "red": "Red"}.get(p.entrada, "")
        self.txt_objetivo.hint_text = p.ejemplo
        self.txt_objetivo.autofocus = p.entrada is not None and not self.txt_objetivo.value
        self.bloque_puertos.visible = p.clave == "puertos"
        self.dd_veces.visible = p.clave == "ping"
        notas = {
            "dns": f"Se pregunta al servidor DNS {Ajustes.current().dns_servidor} "
                   "(cámbialo en Ajustes de Red).",
            "puertos": "Úsalo con tus equipos: escanear equipos ajenos puede verse como un ataque.",
            "wol": "El equipo debe estar en tu misma red (Wi-Fi de casa) y tener Wake-on-LAN "
                   "activado.",
            "whois": "Funciona con dominios (.com, .mx, .com.mx…), no con IPs.",
            "dispositivos": "Tarda unos segundos. Android no deja ver la MAC ni la marca de "
                            "los aparatos; por sus puertos se adivina qué son. Uno dormido "
                            "puede no aparecer.",
        }
        self.lbl_nota.value = notas.get(p.clave, "")
        self.lbl_nota.visible = bool(self.lbl_nota.value)
        recientes = historial.recent_targets(p.clave) if p.entrada else []
        self.recientes.controls = [
            ft.Chip(label=ft.Text(o, size=12), on_click=lambda e, x=o: self._use_recent(x))
            for o in recientes]
        self.recientes.visible = bool(recientes)

    def _render_result(self):  # propio
        self.btn_ejecutar.visible = not self.corriendo
        self.btn_cancelar.visible = self.corriendo
        self.btn_ejecutar.content = ("Otra vez" if self.detalle and self.prueba.clave == "mi_ip"
                                     else "Ejecutar")
        self.lbl_cuando.value = (f"Del historial · {self.cuando:%d/%m/%Y %H:%M}"
                                 if self.cuando else "")
        self.lbl_cuando.visible = bool(self.cuando)
        if self.detalle is None:
            self.resultado.controls = ([ft.ProgressRing()] if self.corriendo else
                                       [ft.Text("El resultado aparece aquí.", italic=True,
                                                color=ft.Colors.OUTLINE)])
        else:
            try:
                self.resultado.controls = render(self.page, self.prueba.clave, self.detalle,
                                                 self.corriendo, on_save=self.save_device)
            except Exception as ex:  # noqa: BLE001  (detalle viejo con otra forma)
                self.resultado.controls = [error_box(f"No se pudo mostrar: {ex}")]
        self.btn_guardar_equipo.visible = self._can_save_equipment()

    def refresh(self):  # propio
        self._render_result()
        self.page.update()

    # ==================================================================
    def _submit(self, e):  # propio
        self.page.run_task(self.run)

    def _use_recent(self, objetivo: str):  # propio
        self.txt_objetivo.value = objetivo
        self.page.run_task(self.run)

    def _preset(self, valor: str):  # propio
        self.txt_puertos.value = valor
        self.txt_puertos.update()

    def pick_equipment(self):  # propio
        mac = self.prueba.entrada == "mac"
        equipos = [e for e in Equipo.search_all() if (e.mac if mac else True)]
        if not equipos:
            notify(self.page, "Aún no tienes equipos con MAC" if mac else
                   "Aún no tienes equipos: guárdalos en la pantalla de Red")
            return

        def pick(eq: Equipo):  # propio
            self.page.pop_dialog()
            self.txt_objetivo.value = eq.mac if mac else eq.host
            if self.prueba.clave == "puertos" and eq.puertos:
                self.txt_puertos.value = eq.puertos
            self.txt_objetivo.error = None
            self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Mis equipos"),
            content=ft.Column(tight=True, scroll=ft.ScrollMode.AUTO, controls=[
                ft.ListTile(title=ft.Text(eq.nombre),
                            subtitle=ft.Text(eq.mac if mac else eq.host, font_family=MONO),
                            leading=ft.Icon(ft.Icons.DNS), on_click=lambda e, x=eq: pick(x))
                for eq in equipos]),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog())],
        ))

    def _can_save_equipment(self) -> bool:  # propio
        if self.prueba.entrada != "host" or not self.detalle or self.corriendo:
            return False
        if self.detalle.get("error"):
            return False
        try:
            host = clean_host(self.txt_objetivo.value or "")
        except ValueError:
            return False
        return host not in {e.host.lower() for e in Equipo.search_all()}

    def save_equipment(self):  # propio
        host = clean_host(self.txt_objetivo.value or "")
        puertos_texto = None
        if self.prueba.clave == "puertos" and self.detalle:
            abiertos = [p["puerto"] for p in self.detalle.get("puertos", [])
                        if p["estado"] == "abierto"]
            puertos_texto = ", ".join(map(str, abiertos)) or None

        def saved(eq):  # propio
            notify(self.page, f"«{eq.nombre}» guardado en Mis equipos")
            self.refresh()

        equipment_dialog(self.page, None, saved, host=host, puertos=puertos_texto)

    def save_device(self, ip: str, puertos_lista: list[int], nombre: str | None):  # propio
        """Un dispositivo encontrado -> Mis equipos."""
        def saved(eq):  # propio
            notify(self.page, f"«{eq.nombre}» guardado en Mis equipos")
            self.refresh()

        equipment_dialog(self.page, None, saved, host=ip,
                         puertos=", ".join(map(str, puertos_lista)) or None, nombre=nombre)

    # ==================================================================
    # Ejecutar
    # ==================================================================
    async def run(self, e=None):  # propio
        if self.corriendo:
            return
        p = self.prueba
        objetivo = (self.txt_objetivo.value or "").strip()
        if p.entrada and not objetivo:
            self.txt_objetivo.error = "Escribe " + {"mac": "la MAC", "dominio": "el dominio",
                                                    "red": "la red (192.168.1.0/24)"}.get(
                p.entrada, "la IP o el dominio")
            self.txt_objetivo.update()
            return
        self.txt_objetivo.error = None
        self.corriendo, self.detalle, self.cuando, self._parcial = True, None, None, None
        self.refresh()
        self._tarea = asyncio.current_task()
        cancelado = False
        try:
            r = await self._call(p.clave, objetivo)
        except asyncio.CancelledError:
            cancelado, r = True, self._parcial
            if r is not None and hasattr(r, "cancelado"):
                r.cancelado = True
        finally:
            self._tarea = None
            self.corriendo = False
        if r is not None:
            self.detalle = r.to_dict()
            historial.record(p.clave, objetivo or "Este equipo", r)
            self._render_form()  # los "recientes" incluyen el de ahora
        if cancelado:
            notify(self.page, "Cancelado")
        self.refresh()

    async def cancel(self, e=None):  # propio
        if self._tarea is not None:
            self._tarea.cancel()

    def _progress(self, r):  # propio
        """Resultado a medias (ping/puertos): se repinta mientras corre."""
        self._parcial = r
        self.detalle = r.to_dict()
        self._render_result()
        try:
            self.resultado.update()
        except RuntimeError:  # la pantalla aún se está montando (se abrió con "ejecutar")
            self.page.update()

    async def _call(self, clave: str, objetivo: str):  # propio
        if clave == "ping":
            return await ping.ping(objetivo, veces=int(self.dd_veces.value or 4),
                                   on_progress=self._progress)
        if clave == "puertos":
            return await puertos.scan(objetivo, self.txt_puertos.value or "",
                                      on_progress=self._progress)
        if clave == "dns":
            return await consulta_dns.lookup(objetivo, Ajustes.current().dns_servidor)
        if clave == "mi_ip":
            return await mi_ip.my_ip()
        if clave == "cert":
            return await certificado.check(objetivo)
        if clave == "whois":
            return await whois.lookup(objetivo)
        if clave == "wol":
            return wol.wake(objetivo)
        if clave == "dispositivos":
            return await dispositivos.discover(objetivo, on_progress=self._progress)
        raise ValueError(clave)

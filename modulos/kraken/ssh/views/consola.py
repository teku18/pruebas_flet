"""
Consola de un servidor (/kraken/ssh/consola): escribe cualquier comando.

  ← Consola · Cliente ACME                           [copiar] [limpiar]
  ┌──────────────────────────────────────────────────────────────┐
  │ edgar@ACME:/opt/odoo$ ls -la                                  │
  │ drwxr-xr-x  5 odoo odoo 4096 …                                │
  │ edgar@ACME:/opt/odoo$ sudo systemctl restart odoo             │
  │ (listo · 1.2 s)                                               │
  └──────────────────────────────────────────────────────────────┘
  edgar@ACME:/opt/odoo$
  [ comando…                                             ] [enviar]
  (Tab) (arriba) (abajo) (Ctrl+C) (ls -la) (df -h) (free -h) …

La salida llega en vivo; la pantalla se pinta cada 0.2 s (no por cada
pedazo) para no saturar el celular. Cada comando queda en el historial de Red.
Sin TTY: vim, nano, htop… no se pueden (se avisa qué usar).

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from modulos.kraken import routes
from modulos.kraken.comun import MONO, copy_text
from modulos.kraken.models import Equipo
from modulos.kraken.red import historial
from modulos.kraken.ssh import consola
from modulos.kraken.ssh.acciones import ComandoResultado
from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly

FONDO = "#1E1E1E"
VERDE = "#7EE787"
GRIS = "#A0A0A0"
TEXTO = "#E6E6E6"
MAX_BLOQUES = 60          # comandos que se quedan en pantalla
MAX_TEXTO_BLOQUE = 60_000 # lo que se pinta de cada salida (lo demás: "Copiar")


class ConsoleView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.equipo: Equipo | None = None
        self.sesion: Sesion | None = None
        self.consola: consola.Consola | None = None
        self.activo = False
        self.corriendo = False
        self.historia: list[str] = []   # comandos (el último al final)
        self.pos = 0                     # posición al navegar con arriba/abajo
        self.texto_total: list[str] = []
        self._pendiente: list[str] = []  # salida que llegó del hilo y falta pintar
        self._teclado_anterior = None

        self.titulo = ft.Text()
        self.salida = ft.ListView(expand=True, spacing=2, auto_scroll=True, padding=10)
        self.lbl_prompt = ft.Text(size=12, font_family=MONO, color=ft.Colors.GREEN,
                                  max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.txt = ft.TextField(
            hint_text="comando (ls, cd, sudo systemctl restart odoo…)", dense=True, expand=True,
            text_style=ft.TextStyle(font_family=MONO, size=13), autocorrect=False,
            enable_suggestions=False, capitalization=ft.TextCapitalization.NONE,
            shift_enter=False, on_submit=lambda e: self.page.run_task(self.send))
        self.btn_enviar = ft.IconButton(ft.Icons.SEND, tooltip="Ejecutar",
                                        on_click=lambda e: self.page.run_task(self.send))
        self.btn_cancelar = ft.FilledTonalButton(
            "Ctrl+C", icon=ft.Icons.STOP, visible=False,
            style=ft.ButtonStyle(color=ft.Colors.RED), on_click=lambda e: self.cancel())
        self.sugerencias = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6, visible=False)
        teclas = [
            self._key("Tab", lambda e: self.page.run_task(self.tab)),
            self._key(None, lambda e: self.recall(-1), ft.Icons.KEYBOARD_ARROW_UP, "Anterior"),
            self._key(None, lambda e: self.recall(1), ft.Icons.KEYBOARD_ARROW_DOWN, "Siguiente"),
            self._key("Ctrl+C", lambda e: self.cancel()),
            *[self._key(c, lambda e, x=c: self.use(x)) for c in consola.FRECUENTES],
        ]
        self.vista = ft.View(
            route=routes.SSH_CONSOLA,
            appbar=ft.AppBar(title=self.titulo, actions=[
                ft.IconButton(ft.Icons.COPY, tooltip="Copiar todo",
                              on_click=lambda e: self.page.run_task(
                                  copy_text, self.page, "".join(self.texto_total))),
                ft.IconButton(ft.Icons.CLEANING_SERVICES, tooltip="Limpiar pantalla",
                              on_click=lambda e: self.clear())]),
            padding=0,
            controls=[ft.SafeArea(expand=True, content=ft.Column(expand=True, spacing=6, controls=[
                ft.Container(expand=True, bgcolor=FONDO, border_radius=8,
                             margin=ft.Margin.only(left=8, right=8, top=4), content=self.salida),
                ft.Container(padding=ft.Padding.symmetric(horizontal=10), content=ft.Column(
                    spacing=4, controls=[
                        self.sugerencias,
                        ft.Row([self.lbl_prompt, self.btn_cancelar],
                               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([self.txt, self.btn_enviar]),
                        # el espacio de la izquierda: ahí flota el botón de captura de la app
                        ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6,
                               controls=[ft.Container(width=44), *teclas]),
                        ft.Container(height=6)])),
            ]))],
        )

    @staticmethod
    def _key(texto, on_click, icono=None, tooltip=None) -> ft.Control:  # propio
        if icono:
            return ft.IconButton(icono, tooltip=tooltip, on_click=on_click,
                                 style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
        return ft.OutlinedButton(texto, on_click=on_click,
                                 style=ft.ButtonStyle(text_style=ft.TextStyle(font_family=MONO,
                                                                              size=12)))

    # ==================================================================
    def open(self, equipo: Equipo):  # propio
        self.close()
        self.equipo = Equipo.get(equipo.id)
        self.activo = True
        self.titulo.value = f"Consola · {self.equipo.nombre}"
        self.salida.controls = []
        self.texto_total = []
        self.historia = self._load_history()
        self.pos = len(self.historia)
        self.txt.value = ""
        self.lbl_prompt.value = "Conectando…"
        self._busy(True)
        self._teclado_anterior = self.page.on_keyboard_event
        self.page.on_keyboard_event = self._on_key
        self.page.navigate(routes.SSH_CONSOLA)
        self.page.run_task(self._connect)

    def close(self):  # propio
        if not self.activo:
            return
        self.activo = False
        self.page.on_keyboard_event = self._teclado_anterior
        if self.consola is not None:
            self.consola.cancel()
        if self.sesion is not None:
            sesion, self.sesion, self.consola = self.sesion, None, None
            self.page.run_thread(sesion.close)

    def _load_history(self) -> list[str]:  # propio
        """Los comandos que ya escribiste en ESTE servidor (del historial de Red)."""
        vistos: list[str] = []
        for h in historial.history("ssh", 400):
            d = h.detalle or {}
            if d.get("nombre") == "Consola" and d.get("servidor") == self.equipo.nombre:
                if d.get("comando") and d["comando"] not in vistos:
                    vistos.append(d["comando"])
            if len(vistos) >= 100:
                break
        return list(reversed(vistos))

    async def _connect(self):  # propio
        try:
            self.sesion = Sesion(self.equipo)
            await asyncio.to_thread(self.sesion.open)
            self.consola = consola.Consola(self.sesion)
            await asyncio.to_thread(self.consola.start)
        except HuellaCambio:
            self._line("La huella del servidor cambió: ábrelo desde el panel para revisarla.",
                       ft.Colors.RED_300)
            self.lbl_prompt.value = "Sin conexión"
            self.sesion = self.consola = None
        except Exception as ex:  # noqa: BLE001
            self._line(friendly(ex, self.equipo), ft.Colors.RED_300)
            self.lbl_prompt.value = "Sin conexión (sal y vuelve a entrar para reintentar)"
            self.sesion = self.consola = None
        else:
            self._line(f"Conectado a {self.equipo.ssh_usuario}@{self.equipo.host} "
                       f"en {self.sesion.ms_conexion} ms. Escribe un comando.", GRIS)
            self.lbl_prompt.value = self.consola.prompt()
        self._busy(False)
        self._paint()

    # ==================================================================
    def _busy(self, si: bool):  # propio
        self.corriendo = si
        self.btn_enviar.disabled = si
        self.btn_cancelar.visible = si and self.consola is not None

    def _paint(self):  # propio
        if not self.activo:
            return
        try:
            self.page.update()
        except RuntimeError:
            pass

    def _line(self, texto: str, color=TEXTO, negrita=False) -> ft.Text:  # propio
        t = ft.Text(texto, font_family=MONO, size=12, color=color, selectable=True,
                    weight=ft.FontWeight.BOLD if negrita else None)
        self.salida.controls.append(t)
        self.texto_total.append(texto + "\n")
        if len(self.salida.controls) > MAX_BLOQUES * 3:
            self.salida.controls = self.salida.controls[-MAX_BLOQUES * 3:]
        return t

    def clear(self):  # propio
        self.salida.controls = []
        self._paint()

    def use(self, comando: str):  # propio
        self.txt.value = comando
        self.sugerencias.visible = False
        self._paint()
        self.page.run_task(self.txt.focus)

    def recall(self, delta: int):  # propio
        if not self.historia:
            return
        self.pos = max(0, min(len(self.historia), self.pos + delta))
        self.txt.value = self.historia[self.pos] if self.pos < len(self.historia) else ""
        self._paint()

    def _on_key(self, e: ft.KeyboardEvent):  # propio
        """En la PC: flecha arriba/abajo = historial, Ctrl+C = cortar (si corre algo)."""
        if self.page.route == routes.SSH_CONSOLA:
            if e.key == "Arrow Up":
                self.recall(-1)
            elif e.key == "Arrow Down":
                self.recall(1)
            elif e.ctrl and e.key.upper() == "C" and self.corriendo:
                self.cancel()
        if callable(self._teclado_anterior):
            self._teclado_anterior(e)

    def cancel(self):  # propio
        if self.consola is not None and self.corriendo:
            self.consola.cancel()
        self.page.run_task(self.txt.focus)

    # ==================================================================
    async def send(self):  # propio
        comando = (self.txt.value or "").strip()
        if self.corriendo or self.consola is None:
            return
        if not comando:
            return
        self.txt.value = ""
        self.sugerencias.visible = False
        self.page.run_task(self.txt.focus)   # seguir escribiendo sin tocar el campo
        if not self.historia or self.historia[-1] != comando:
            self.historia.append(comando)
        self.pos = len(self.historia)
        self._line(f"{self.consola.prompt()} {comando}", VERDE, negrita=True)
        if comando in ("clear", "reset", "cls"):
            self.clear()
            return
        if comando in ("exit", "logout"):
            self._line("Para salir usa la flecha de atrás.", GRIS)
            self._paint()
            return
        aviso = consola.full_screen_hint(comando)
        if aviso:
            self._line(aviso, ft.Colors.ORANGE_300)
            self._paint()
            return
        bloque = self._line("", TEXTO)
        self._busy(True)
        self._pendiente = []
        self._paint()
        corriendo = asyncio.create_task(asyncio.to_thread(
            self.consola.run, comando, self._pendiente.append))
        visto = 0
        while not corriendo.done():
            await asyncio.sleep(0.2)
            if len(self._pendiente) != visto:
                visto = len(self._pendiente)
                bloque.value = "".join(self._pendiente)[-MAX_TEXTO_BLOQUE:].rstrip("\n")
                self._paint()
        try:
            r = corriendo.result()
        except Exception as ex:  # noqa: BLE001  (se cayó la conexión)
            r = consola.Resultado(comando, None, "".join(self._pendiente), self.consola.cwd or "~",
                                  0, error=friendly(ex, self.equipo))
        bloque.value = r.salida[-MAX_TEXTO_BLOQUE:].rstrip("\n")
        if not bloque.value:
            self.salida.controls.remove(bloque)
        self.texto_total.append(r.salida)
        if r.error:
            self._line(r.error, ft.Colors.RED_300)
        elif r.cancelado:
            self._line("^C (cortado)", ft.Colors.ORANGE_300)
        elif r.codigo not in (0, None):
            self._line(f"(terminó con código {r.codigo} · {r.tiempo_ms / 1000:.1f} s)",
                       ft.Colors.RED_300)
        elif r.tiempo_ms > 1500:
            self._line(f"(listo · {r.tiempo_ms / 1000:.1f} s)", GRIS)
        self.lbl_prompt.value = self.consola.prompt() if self.consola else "Sin conexión"
        self._busy(False)
        self._paint()
        self._record(r)

    def _record(self, r: consola.Resultado):  # propio
        """Cada comando, al historial de Red (se ve como los comandos guardados)."""
        c = ComandoResultado(servidor=self.equipo.nombre, nombre="Consola", comando=r.comando,
                             codigo=r.codigo, salida=r.salida, tiempo_ms=r.tiempo_ms,
                             error=r.error or ("cortado con Ctrl+C" if r.cancelado else None))
        try:
            historial.record("ssh", f"{self.equipo.nombre}: $ {r.comando}", c)
        except Exception:  # noqa: BLE001  (el historial nunca debe tumbar la consola)
            pass

    async def tab(self):  # propio
        if self.consola is None or self.corriendo:
            return
        linea = self.txt.value or ""
        opciones = await asyncio.to_thread(self.consola.complete, linea)
        palabras = linea.split(" ")
        if not opciones:
            self.sugerencias.visible = False
        elif len(opciones) == 1:
            palabras[-1] = opciones[0] + ("" if opciones[0].endswith("/") else " ")
            self.txt.value = " ".join(palabras)
            self.sugerencias.visible = False
        else:
            comun = consola.common_prefix(opciones)
            if len(comun) > len(palabras[-1]):
                palabras[-1] = comun
                self.txt.value = " ".join(palabras)
            self.sugerencias.controls = [
                ft.Chip(label=ft.Text(o, size=11, font_family=MONO),
                        on_click=lambda e, x=o: self._pick(x)) for o in opciones[:40]]
            self.sugerencias.visible = True
        self._paint()
        self.page.run_task(self.txt.focus)

    def _pick(self, opcion: str):  # propio
        palabras = (self.txt.value or "").split(" ")
        palabras[-1] = opcion + ("" if opcion.endswith("/") else " ")
        self.txt.value = " ".join(palabras)
        self.sugerencias.visible = False
        self._paint()
        self.page.run_task(self.txt.focus)

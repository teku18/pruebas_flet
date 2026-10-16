"""
Panel de un servidor (/kraken/ssh/panel): se actualiza cada 5 s MIENTRAS lo ves.

  ← Cliente ACME                         ● En vivo · cada 5 s   [⋮]
  Ubuntu 24.04 · encendido 3 días · carga 0.3 0.4 0.8 (8 núcleos)
  ┌ CPU 12% ─────┐ ┌ RAM 77% ─────────┐
  │ ▓▓░░░░░░░░   │ │ ▓▓▓▓▓▓▓▓░░ 24/31 GB│
  └──────────────┘ └──────────────────┘
  [gráfica CPU y RAM de los últimos 5 min]
  Discos   /  ▓▓▓▓▓▓▓▓░░ 702 / 928 GB (80%)
  Red      bajada 1.2 MB/s · subida 80 KB/s
  Servicios (odoo: activo) (postgresql: activo) (nginx: apagado)
  Procesos que más consumen…
  [▶ Comandos]  [Consola]  [📄 Logs]

"Mientras lo ves" de verdad:
  - al salir de la pantalla, el ciclo se detiene y se cierra la conexión
  - si abres Consola o Logs encima, también se pausa (no se ve: no se lee)
  - si la app pasa a segundo plano (otra app, pantalla apagada), se pausa
    (page.on_app_lifecycle_state_change) y al volver lee al instante

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
import time

import flet as ft
import flet_charts as fch

from core.ui import notify
from modulos.kraken import routes
from modulos.kraken.comun import MONO
from modulos.kraken.models import Equipo
from modulos.kraken.red import historial
from modulos.kraken.ssh import metricas
from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly
from modulos.kraken.ssh.views.comandos import commands_sheet

CADA = 5            # segundos entre lecturas
PUNTOS = 60         # 60 lecturas = 5 minutos en la gráfica
COLOR_CPU = ft.Colors.BLUE
COLOR_RAM = ft.Colors.PURPLE


def level_color(pct: float):  # propio
    """Verde < 70 % · naranja < 90 % · rojo."""
    if pct >= 90:
        return ft.Colors.RED
    if pct >= 70:
        return ft.Colors.ORANGE
    return ft.Colors.GREEN


def rate_text(bps: float | None) -> str:  # propio
    if bps is None:
        return "…"
    for unidad in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024 or unidad == "GB/s":
            return f"{bps:.0f} {unidad}" if unidad == "B/s" else f"{bps:.1f} {unidad}"
        bps /= 1024
    return ""


class _Vistazo:
    """Para el historial: 'CPU 12% · RAM 77% · disco 80%'."""

    def __init__(self, m: metricas.Muestra, servidor: str):
        self.m, self.servidor = m, servidor

    def summary(self) -> tuple[str, bool]:  # propio
        caidos = [s for s, e in self.m.servicios.items() if e not in ("active",)]
        texto = self.m.summary() + (f" · apagado: {', '.join(caidos)}" if caidos else "")
        return texto[:255], self.m.disco_max < 90 and not caidos

    def to_dict(self) -> dict:  # propio
        return {"tipo": "panel", "servidor": self.servidor, **self.m.to_dict()}


class PanelView:
    def __init__(self, page: ft.Page, on_logs, on_console):
        """on_logs(equipo) / on_console(equipo): abren Logs y Consola encima del panel."""
        self.page = page
        self.on_logs = on_logs
        self.on_console = on_console
        self.equipo: Equipo | None = None
        self.sesion: Sesion | None = None
        self.muestras: list[metricas.Muestra] = []
        self.activo = False      # la pantalla está abierta
        self.pausado = False     # la app está en segundo plano
        self.error: str | None = None
        self._tarea: asyncio.Task | None = None
        self._despertar = asyncio.Event()
        self._lifecycle_anterior = None
        self._anotado = False    # un "vistazo" al historial por visita

        self.titulo = ft.Text()
        self.lbl_estado = ft.Text(size=12)
        self.punto = ft.Icon(ft.Icons.CIRCLE, size=10)
        self.cuerpo = ft.Column(spacing=12)
        self.vista = ft.View(
            route=routes.SSH_PANEL,
            appbar=ft.AppBar(title=self.titulo, actions=[
                ft.Container(margin=ft.Margin.only(right=12), content=ft.Row(
                    tight=True, spacing=4, controls=[self.punto, self.lbl_estado]))]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=12, controls=[
                self.cuerpo, ft.Container(height=30)]))],
        )

    # ==================================================================
    # Abrir / cerrar / pausar
    # ==================================================================
    def open(self, equipo: Equipo):  # propio
        self.close()
        self.equipo = Equipo.get(equipo.id)
        self.muestras, self.error, self._anotado = [], None, False
        self.titulo.value = self.equipo.nombre
        self.activo, self.pausado = True, False
        self._lifecycle_anterior = self.page.on_app_lifecycle_state_change
        self.page.on_app_lifecycle_state_change = self._on_lifecycle
        self._render()
        self.page.navigate(routes.SSH_PANEL)
        self.page.run_task(self._loop)

    def close(self):  # propio
        """Al salir: se detiene el ciclo y se cierra la conexión."""
        if not self.activo:
            return
        self.activo = False
        self._despertar.set()
        self.page.on_app_lifecycle_state_change = self._lifecycle_anterior
        if self.sesion is not None:
            sesion, self.sesion = self.sesion, None
            self.page.run_thread(sesion.close)

    def _on_lifecycle(self, e):  # propio
        if e.state in (ft.AppLifecycleState.PAUSE, ft.AppLifecycleState.HIDE,
                       ft.AppLifecycleState.INACTIVE):
            self.pausado = True
        elif e.state in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            if self.pausado:
                self.pausado = False
                self._despertar.set()  # al volver: leer ya
        if callable(self._lifecycle_anterior):
            self._lifecycle_anterior(e)

    def wake(self):  # propio
        """Volviste al panel (desde Consola o Logs): leer ya."""
        self._despertar.set()

    def retry(self, e=None):  # propio
        self.error = None
        self._render()
        self.page.update()
        if self._tarea is None or self._tarea.done():
            self.page.run_task(self._loop)

    # ==================================================================
    # El ciclo: leer, pintar, esperar 5 s
    # ==================================================================
    async def _loop(self):  # propio
        self._tarea = asyncio.current_task()
        while self.activo and self.error is None:
            if self.pausado or self.page.route != routes.SSH_PANEL:
                await self._wait(3600)   # wake() al volver al panel
                continue
            await self._read_once()
            if self.activo and self.error is None:
                await self._wait(CADA)

    async def _wait(self, segundos: float):  # propio
        self._despertar.clear()
        try:
            await asyncio.wait_for(self._despertar.wait(), segundos)
        except asyncio.TimeoutError:
            pass

    async def _read_once(self, aceptar_huella: str | None = None):  # propio
        try:
            if self.sesion is None or not self.sesion.abierta:
                self.sesion = Sesion(self.equipo)
                await asyncio.to_thread(self.sesion.open, aceptar_huella)
                self.equipo = Equipo.get(self.equipo.id)
            salida = await asyncio.to_thread(self.sesion.run,
                                             metricas.script(self.equipo.servicios), 20)
            anterior = self.muestras[-1] if self.muestras else None
            m = metricas.parse(salida.texto, time.monotonic(), anterior)
        except HuellaCambio as ex:
            self.sesion = None
            self.error = "huella"
            self._fingerprint_dialog(ex)
        except Exception as ex:  # noqa: BLE001  (red, contraseña, servidor raro)
            if self.sesion is not None:
                self.page.run_thread(self.sesion.close)
            self.sesion = None
            self.error = friendly(ex, self.equipo) if not isinstance(ex, ValueError) else str(ex)
        else:
            self.muestras = (self.muestras + [m])[-PUNTOS:]
            if not self._anotado and m.cpu is not None:
                historial.record("ssh", self.equipo.nombre, _Vistazo(m, self.equipo.nombre))
                self._anotado = True
        if self.activo:
            self._render()
            self.page.update()

    def _fingerprint_dialog(self, ex: HuellaCambio):  # propio
        def trust(e):  # propio
            self.page.pop_dialog()
            self.error = None
            self.page.run_task(self._trust_and_loop, ex.nueva)

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("La huella del servidor cambió"),
            content=ft.Column(tight=True, spacing=8, controls=[
                ft.Text("El servidor se presentó distinto a la última vez. Pasa cuando lo "
                        "reinstalan o cambian de máquina… o si alguien se hace pasar por él. "
                        "Si no esperabas un cambio, NO confíes y pregunta al cliente."),
                ft.Text(f"Antes: {ex.guardada}", font_family=MONO, size=11, selectable=True),
                ft.Text(f"Ahora: {ex.nueva}", font_family=MONO, size=11, selectable=True,
                        color=ft.Colors.ORANGE)]),
            actions=[ft.TextButton("No conectar", on_click=lambda e: self.page.pop_dialog()),
                     ft.TextButton("Confío en la nueva", on_click=trust,
                                   style=ft.ButtonStyle(color=ft.Colors.ORANGE))],
        ))

    async def _trust_and_loop(self, huella: str):  # propio
        await self._read_once(aceptar_huella=huella)
        if self.error is None:
            notify(self.page, "Huella nueva guardada")
            await self._wait(CADA)
            await self._loop()

    # ==================================================================
    # Pintar
    # ==================================================================
    def _render(self):  # propio
        e = self.equipo
        if self.error and self.error != "huella":
            self.punto.color, self.lbl_estado.value = ft.Colors.RED, "Sin conexión"
        elif self.pausado:
            self.punto.color, self.lbl_estado.value = ft.Colors.OUTLINE, "En pausa"
        elif self.muestras:
            self.punto.color, self.lbl_estado.value = ft.Colors.GREEN, f"En vivo · cada {CADA} s"
        else:
            self.punto.color, self.lbl_estado.value = ft.Colors.ORANGE, "Conectando…"
        controles: list[ft.Control] = []
        if self.error and self.error != "huella":
            controles.append(ft.Container(
                padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.RED),
                content=ft.Column(spacing=6, controls=[
                    ft.Text(self.error, color=ft.Colors.RED, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{e.ssh_usuario}@{e.host}:{e.ssh_puerto or 22}", size=12,
                            font_family=MONO),
                    ft.Row([ft.FilledButton("Reintentar", icon=ft.Icons.REFRESH,
                                            on_click=self.retry)])])))
        if not self.muestras:
            if not self.error:
                controles.append(ft.Row([ft.ProgressRing(width=20, height=20),
                                         ft.Text(f"Conectando a {e.host}…")]))
            self.cuerpo.controls = controles + [self._actions()]
            return
        m = self.muestras[-1]
        controles += [self._header(m), self._gauges(m), self._chart(), self._disks(m),
                      self._network(m), self._services(m), self._processes(m), self._actions()]
        self.cuerpo.controls = controles

    def _header(self, m: metricas.Muestra) -> ft.Control:  # propio
        carga = " ".join(f"{c:.2f}" for c in m.carga)
        return ft.Column(spacing=2, controls=[
            ft.Text(f"{m.sistema} · {m.nombre}", weight=ft.FontWeight.W_500),
            ft.Text(f"Encendido {metricas.uptime_text(m.encendido_s)} · carga {carga} "
                    f"({m.nucleos} núcleo{'s' if m.nucleos != 1 else ''})", size=12,
                    color=ft.Colors.OUTLINE),
        ])

    def _gauge(self, titulo: str, pct: float | None, detalle: str, color_linea) -> ft.Control:  # propio
        valor = "…" if pct is None else f"{pct:.0f}%"
        color = ft.Colors.OUTLINE if pct is None else level_color(pct)
        return ft.Card(col={"xs": 6}, content=ft.Container(padding=12, content=ft.Column(
            spacing=6, controls=[
                ft.Row(controls=[ft.Icon(ft.Icons.CIRCLE, size=10, color=color_linea),
                                 ft.Text(titulo, size=12, color=ft.Colors.OUTLINE)]),
                ft.Text(valor, size=28, weight=ft.FontWeight.BOLD, color=color),
                ft.ProgressBar(value=(pct or 0) / 100, color=color, bar_height=6,
                               border_radius=3),
                ft.Text(detalle, size=11, color=ft.Colors.OUTLINE)])))

    def _gauges(self, m: metricas.Muestra) -> ft.Control:  # propio
        ram = (f"{metricas.kb_text(m.ram_usada)} de {metricas.kb_text(m.ram_total)}"
               + (f" · swap {m.swap_pct:.0f}%" if m.swap_total else ""))
        cpu = "Midiendo…" if m.cpu is None else f"{m.nucleos} núcleo{'s' if m.nucleos != 1 else ''}"
        return ft.ResponsiveRow(spacing=8, controls=[
            self._gauge("CPU", m.cpu, cpu, COLOR_CPU),
            self._gauge("RAM", m.ram_pct, ram, COLOR_RAM)])

    def _chart(self) -> ft.Control:  # propio
        cpu = [(k, x.cpu) for k, x in enumerate(self.muestras) if x.cpu is not None]
        ram = [(k, x.ram_pct) for k, x in enumerate(self.muestras)]
        if len(ram) < 2:
            return ft.Text("La gráfica aparece con la segunda lectura…", size=12,
                           color=ft.Colors.OUTLINE)

        def serie(puntos, color):  # propio
            return fch.LineChartData(
                points=[fch.LineChartDataPoint(x=k, y=v, show_tooltip=False) for k, v in puntos],
                color=color, stroke_width=2, curved=True,
                below_line_bgcolor=ft.Colors.with_opacity(0.10, color))

        segundos = (len(self.muestras) - 1) * CADA
        lapso = f"{segundos} s" if segundos < 60 else f"{segundos / 60:.1f} min".replace(".0 ", " ")
        return ft.Column(spacing=4, controls=[
            ft.Row(controls=[
                ft.Text(f"Últimos {lapso}", size=12, color=ft.Colors.OUTLINE, expand=True),
                ft.Icon(ft.Icons.CIRCLE, size=8, color=COLOR_CPU), ft.Text("CPU", size=11),
                ft.Icon(ft.Icons.CIRCLE, size=8, color=COLOR_RAM), ft.Text("RAM", size=11)]),
            fch.LineChart(
                # el eje crece con las lecturas (hasta 5 min) para no apretar las líneas
                height=150, min_y=0, max_y=100, min_x=0, max_x=max(11, len(ram) - 1),
                data_series=[serie(cpu, COLOR_CPU), serie(ram, COLOR_RAM)],
                left_axis=fch.ChartAxis(label_size=34, label_spacing=50, labels=[
                    fch.ChartAxisLabel(value=v, label=ft.Text(f"{v}%", size=10))
                    for v in (0, 50, 100)]),
                horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.OUTLINE_VARIANT,
                                                         interval=25),
                interactive=False,
            ),
        ])

    def _disks(self, m: metricas.Muestra) -> ft.Control:  # propio
        filas: list[ft.Control] = [ft.Text("Discos", weight=ft.FontWeight.BOLD)]
        for d in m.discos[:6]:
            color = level_color(d["pct"])
            filas.append(ft.Column(spacing=2, controls=[
                ft.Row(controls=[
                    ft.Text(d["montaje"], font_family=MONO, size=12, expand=True, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{metricas.kb_text(d['usado'])} / {metricas.kb_text(d['total'])} "
                            f"({d['pct']:.0f}%)", size=12, color=color,
                            weight=ft.FontWeight.BOLD if d["pct"] >= 90 else None)]),
                ft.ProgressBar(value=d["pct"] / 100, color=color, bar_height=6,
                               border_radius=3)]))
        if any(d["pct"] >= 90 for d in m.discos):
            filas.append(ft.Text("Un disco lleno puede tumbar Odoo y PostgreSQL: libera espacio "
                                 "(comando «¿Qué ocupa el disco?»).", size=11,
                                 color=ft.Colors.RED))
        return ft.Column(spacing=6, controls=filas)

    def _network(self, m: metricas.Muestra) -> ft.Control:  # propio
        return ft.Row(spacing=16, controls=[
            ft.Text("Red", weight=ft.FontWeight.BOLD),
            ft.Row(tight=True, spacing=2, controls=[
                ft.Icon(ft.Icons.ARROW_DOWNWARD, size=14, color=ft.Colors.GREEN),
                ft.Text(rate_text(m.rx_s), size=12)]),
            ft.Row(tight=True, spacing=2, controls=[
                ft.Icon(ft.Icons.ARROW_UPWARD, size=14, color=ft.Colors.BLUE),
                ft.Text(rate_text(m.tx_s), size=12)]),
        ])

    def _services(self, m: metricas.Muestra) -> ft.Control:  # propio
        def chip(nombre: str, estado: str) -> ft.Control:  # propio
            texto, color = {"active": ("activo", ft.Colors.GREEN),
                            "inactive": ("apagado", ft.Colors.OUTLINE),
                            "failed": ("falló", ft.Colors.RED),
                            "activating": ("arrancando", ft.Colors.ORANGE)}.get(
                estado, (estado or "no existe", ft.Colors.OUTLINE))
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.15, color),
                content=ft.Text(f"{nombre}: {texto}", size=12, color=color,
                                weight=ft.FontWeight.W_500))

        return ft.Column(spacing=6, controls=[
            ft.Text("Servicios", weight=ft.FontWeight.BOLD),
            ft.Row(wrap=True, spacing=6, run_spacing=6,
                   controls=[chip(n, e) for n, e in m.servicios.items()] or
                   [ft.Text("(ninguno configurado)", size=12, italic=True)])])

    def _processes(self, m: metricas.Muestra) -> ft.Control:  # propio
        filas: list[ft.Control] = [ft.Row(controls=[
            ft.Text("Procesos que más consumen", weight=ft.FontWeight.BOLD, expand=True),
            ft.Text("CPU", size=11, width=48, color=ft.Colors.OUTLINE),
            ft.Text("RAM", size=11, width=70, color=ft.Colors.OUTLINE)])]
        for p in m.procesos[:6]:
            filas.append(ft.Row(controls=[
                ft.Text(p["nombre"], font_family=MONO, size=12, expand=True, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(f"{p['cpu']:.0f}%", size=12, width=48),
                ft.Text(metricas.kb_text(p["rss"]), size=12, width=70)]))
        return ft.Column(spacing=4, controls=filas)

    def _actions(self) -> ft.Control:  # propio
        return ft.Row(wrap=True, spacing=8, controls=[
            ft.FilledButton("Comandos", icon=ft.Icons.PLAY_ARROW, on_click=self.open_commands),
            ft.FilledTonalButton("Consola", icon=ft.Icons.TERMINAL,
                                 on_click=lambda e: self.on_console(self.equipo)),
            ft.OutlinedButton("Logs", icon=ft.Icons.ARTICLE,
                              on_click=lambda e: self.on_logs(self.equipo)),
        ])

    def open_commands(self, e=None):  # propio
        if self.sesion is None or not self.sesion.abierta:
            notify(self.page, "Espera a que se conecte (o toca Reintentar)")
            return
        commands_sheet(self.page, self.sesion, self.equipo)


def show_snapshot(page: ft.Page, d: dict):  # propio
    """Un vistazo guardado en el historial (cómo estaba el servidor)."""
    m = metricas.Muestra(**{k: v for k, v in d.items() if k in metricas.Muestra.__dataclass_fields__})
    discos = "\n".join(f"{x['montaje']}: {x['pct']:.0f}%" for x in m.discos) or "—"
    servicios = ", ".join(f"{n}: {e}" for n, e in m.servicios.items()) or "—"
    page.show_dialog(ft.AlertDialog(
        title=ft.Text(d.get("servidor", "Servidor")),
        content=ft.Container(width=460, content=ft.Column(tight=True, spacing=6, controls=[
            ft.Text(f"{m.sistema} · encendido {metricas.uptime_text(m.encendido_s)}"),
            ft.Text(m.summary(), weight=ft.FontWeight.BOLD),
            ft.Text(f"RAM {metricas.kb_text(m.ram_usada)} de {metricas.kb_text(m.ram_total)}"),
            ft.Text(f"Discos:\n{discos}", font_family=MONO, size=12),
            ft.Text(f"Servicios: {servicios}", size=12)])),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))

"""
Herramienta de captura: un botón flotante que está en TODAS las pantallas,
a la misma altura que el botón "+" de cada módulo (lado izquierdo).

  (📷)  tocar -> menú flotante (encima de la barra del celular):
          ✏️ Marcar y capturar
          🎥 Grabar pantalla
          🖼 Mis capturas

  Marcar y capturar:
    [●●●●] [↶] [🗑]  [Cancelar] [📷 Capturar]   ← barra; dibujas con el dedo
    Capturar -> se esconde la barra, se toma la foto CON tus trazos.

  Grabando:
    [■ 0:12] [✏️]                ← ✏️ enciende el pincel (la app no responde
    [■ 0:12] [✏️] [●●●●] [🗑]      mientras está encendido); apágalo para
                                   seguir usando la app. ■ = detener.

Cómo funciona:
  - Todo vive en page.overlay: una capa que Flet pinta ENCIMA de todas las
    vistas, por eso aparece en cualquier módulo sin tocar sus pantallas.
  - page.media.padding.bottom = alto de la barra de botones del celular
    (0 en la compu). Con eso se acomoda todo para que nada quede tapado.
  - Captura  = page.take_screenshot() (PNG de la app completa, con el overlay:
    por eso salen los trazos del pincel).
  - Grabación = una captura cada ~0.4 s; al detener se arman como GIF animado.
  - Al terminar sale un aviso con [Reportar]: pendiente nuevo con la captura
    adjunta y el módulo donde la tomaste ya elegido.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
import time

import flet as ft

from core.ui import notify
from modulos.desarrollo.capturas import Captura, save_recording, save_screenshot
from modulos.desarrollo.views.pincel import DrawLayer

INTERVALO = 0.4        # segundos entre cuadros de la grabación (~2.5 por segundo)
MAX_SEGUNDOS = 90      # la grabación se detiene sola al llegar aquí
TAMANO = 44            # diámetro del botón flotante

# Posiciones (se suman a la barra de botones del celular):
MARGEN_IZQ = 12
ALTURA_BOTON = 18      # = altura del "+" de los módulos (16 de margen + centrado)
ALTURA_MENU = 8        # el menú queda un poquito más abajo que el "+"

FONDO_BARRA = ft.Colors.with_opacity(0.92, ft.Colors.SURFACE_CONTAINER_HIGHEST)
SOMBRA = ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.35, ft.Colors.BLACK))


class CaptureTool:
    def __init__(self, page: ft.Page, on_report, on_open_inbox):
        """
        on_report(capturas): abrir un pendiente nuevo con esas capturas adjuntas
        on_open_inbox():     ir a la pantalla "Mis capturas"
        """
        self.page = page
        self.on_report = on_report
        self.on_open_inbox = on_open_inbox
        self.grabando = False
        self.pincel = DrawLayer(page)

        # --- Botón flotante (reposo) -------------------------------------
        self.burbuja = ft.Container(
            left=MARGEN_IZQ,
            height=TAMANO,
            width=TAMANO,
            border_radius=TAMANO / 2,
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.PRIMARY),
            shadow=SOMBRA,
            alignment=ft.Alignment.CENTER,
            tooltip="Capturar / grabar pantalla",
            on_click=self.open_menu,
            content=ft.Icon(ft.Icons.PHOTO_CAMERA, size=22, color=ft.Colors.ON_PRIMARY),
        )

        # --- Menú flotante -------------------------------------------------
        # "velo": tocar fuera del menú lo cierra
        self.velo = ft.Container(left=0, top=0, right=0, bottom=0,
                                 bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
                                 on_click=lambda e: self.close_menu())
        self.menu = ft.Container(
            left=MARGEN_IZQ,
            width=250,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            shadow=SOMBRA,
            padding=ft.Padding.symmetric(vertical=6),
            content=ft.Column(
                tight=True,
                spacing=0,
                controls=[
                    self._option(ft.Icons.EDIT, "Marcar y capturar", self.start_marking),
                    self._option(ft.Icons.FIBER_MANUAL_RECORD, "Grabar pantalla",
                                 lambda: self.page.run_task(self.record), ft.Colors.RED),
                    self._option(ft.Icons.PHOTO_LIBRARY, "Mis capturas", self.on_open_inbox),
                ],
            ),
        )

        # --- Barra de "Marcar y capturar" ----------------------------------
        self.barra_marcar = ft.Container(
            left=MARGEN_IZQ,
            right=MARGEN_IZQ,
            border_radius=16,
            bgcolor=FONDO_BARRA,
            shadow=SOMBRA,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            content=ft.Row(
                wrap=True,
                spacing=6,
                run_spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    *self.pincel.color_buttons(),
                    ft.IconButton(ft.Icons.UNDO, tooltip="Deshacer",
                                  on_click=lambda e: self.pincel.undo()),
                    ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Borrar trazos",
                                  on_click=lambda e: self.pincel.clear()),
                    ft.TextButton("Cancelar", on_click=lambda e: self.stop_marking()),
                    ft.FilledButton("Capturar", icon=ft.Icons.PHOTO_CAMERA,
                                    on_click=lambda e: self.page.run_task(self.screenshot)),
                ],
            ),
        )

        # --- Barra de grabación ---------------------------------------------
        self.lbl_tiempo = ft.Text("0:00", size=13, weight=ft.FontWeight.BOLD,
                                  color=ft.Colors.WHITE)
        self.btn_pincel = ft.IconButton(ft.Icons.EDIT, tooltip="Pincel (marcar)",
                                        on_click=lambda e: self.toggle_pen())
        self.herr_pincel = ft.Row(
            visible=False,
            spacing=6,
            tight=True,
            controls=[
                *self.pincel.color_buttons(),
                ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Borrar trazos",
                              on_click=lambda e: self.pincel.clear()),
            ],
        )
        self.barra_grabar = ft.Container(
            left=MARGEN_IZQ,
            border_radius=TAMANO / 2,
            bgcolor=FONDO_BARRA,
            shadow=SOMBRA,
            padding=ft.Padding.only(left=4, right=6),
            content=ft.Row(
                tight=True,
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(  # ■ 0:12  (tocar = detener)
                        height=TAMANO - 8,
                        border_radius=(TAMANO - 8) / 2,
                        bgcolor=ft.Colors.RED,
                        padding=ft.Padding.symmetric(horizontal=12),
                        on_click=lambda e: self.stop_recording(),
                        tooltip="Detener grabación",
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[ft.Icon(ft.Icons.STOP, size=18, color=ft.Colors.WHITE),
                                      self.lbl_tiempo],
                        ),
                    ),
                    self.btn_pincel,
                    self.herr_pincel,
                ],
            ),
        )

    def _option(self, icono, texto: str, accion, color=None) -> ft.Control:  # propio
        def on_click(e):  # propio
            self.close_menu()
            accion()

        return ft.ListTile(leading=ft.Icon(icono, color=color), title=ft.Text(texto),
                           dense=True, on_click=on_click)

    # ==================================================================
    # Instalar y acomodar
    # ==================================================================
    def install(self):  # propio
        """Se llama una vez al abrir la app (DesarrolloModule.on_start)."""
        # OJO: enable_screenshots NO se activa aquí (al arrancar). En el celular
        # hace que se reconstruya la pantalla justo cuando otros módulos piden
        # sus datos guardados, y esas respuestas se pierden. Se activa al
        # capturar por primera vez (_ensure_screenshots).
        self._place()
        self.page.overlay.append(self.burbuja)
        # Si gira el celular o cambia la barra de botones, se vuelve a acomodar
        if self.page.on_media_change is None:
            self.page.on_media_change = lambda e: (self._place(), self.page.update())
        self.page.update()

    async def _ensure_screenshots(self):  # propio
        """Activa las capturas la primera vez que se usan (requisito de take_screenshot)."""
        if not self.page.enable_screenshots:
            self.page.enable_screenshots = True
            self.page.update()
            await asyncio.sleep(0.3)  # que el celular termine de reconstruir la pantalla

    def _inset(self) -> float:  # propio
        """Alto de la barra de botones del celular (0 en la compu)."""
        try:
            return float(self.page.media.padding.bottom or 0)
        except Exception:  # noqa: BLE001 (todavía sin datos de pantalla)
            return 0.0

    def _place(self):  # propio
        abajo = self._inset()
        self.burbuja.bottom = abajo + ALTURA_BOTON
        self.barra_grabar.bottom = abajo + ALTURA_BOTON
        self.menu.bottom = abajo + ALTURA_MENU
        self.barra_marcar.bottom = abajo + ALTURA_MENU

    def _show(self, *controles):  # propio
        for c in controles:
            if c not in self.page.overlay:
                self.page.overlay.append(c)

    def _hide(self, *controles):  # propio
        for c in controles:
            if c in self.page.overlay:
                self.page.overlay.remove(c)

    # ==================================================================
    # Menú
    # ==================================================================
    def open_menu(self, e=None):  # propio
        self._place()
        self._hide(self.burbuja)
        self._show(self.velo, self.menu)
        self.page.update()

    def close_menu(self):  # propio
        self._hide(self.velo, self.menu)
        self._show(self.burbuja)
        self.page.update()

    # ==================================================================
    # Marcar y capturar
    # ==================================================================
    def start_marking(self):  # propio
        """Pincel encendido + barra; la foto se toma con el botón Capturar."""
        self._hide(self.burbuja)
        self._show(self.barra_marcar)
        self.pincel.show(debajo_de=self.barra_marcar)
        self.page.update()

    def stop_marking(self):  # propio
        self.pincel.hide()
        self._hide(self.barra_marcar)
        self._show(self.burbuja)
        self.page.update()

    def _current_module(self) -> str | None:  # propio
        """Nombre del módulo de la pantalla actual ('/agenda/tarea' -> 'Agenda')."""
        from modulos import MODULES  # aquí adentro: modulos/__init__ importa este módulo

        ruta = self.page.route or "/"
        for m in MODULES:
            if m.route and (ruta == m.route or ruta.startswith(m.route + "/")):
                return m.nombre
        return None

    async def screenshot(self):  # propio
        """Foto de la app con los trazos del pincel (sin la barra ni el botón)."""
        origen = self._current_module()
        await self._ensure_screenshots()
        self._hide(self.barra_marcar, self.burbuja)
        self.page.update()
        await asyncio.sleep(0.1)  # que se pinte sin la barra
        try:
            png = await self.page.take_screenshot()
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo capturar: {ex}")
            return
        finally:
            self.stop_marking()  # quita el pincel y regresa el botón
        self._done(save_screenshot(png, origen), "📷 Captura guardada")

    # ==================================================================
    # Grabación
    # ==================================================================
    def toggle_pen(self):  # propio
        """✏️ durante la grabación: encender (dibujar) / apagar (usar la app)."""
        if self.pincel.activo:
            self.pincel.hide()
        else:
            self.pincel.show(debajo_de=self.barra_grabar)
        activo = self.pincel.activo
        self.herr_pincel.visible = activo
        self.btn_pincel.icon = ft.Icons.EDIT_OFF if activo else ft.Icons.EDIT
        self.btn_pincel.tooltip = "Apagar pincel (usar la app)" if activo else "Pincel (marcar)"
        self.page.update()

    def stop_recording(self):  # propio
        self.grabando = False  # el ciclo de grabación lo nota y termina

    async def record(self):  # propio
        await asyncio.sleep(0.2)  # que termine de cerrarse el menú
        origen = self._current_module()
        await self._ensure_screenshots()
        self.grabando = True
        self.lbl_tiempo.value = "0:00"
        self._hide(self.burbuja)
        self._show(self.barra_grabar)
        self.page.update()

        cuadros: list[bytes] = []
        momentos: list[float] = []
        inicio = time.monotonic()
        try:
            while self.grabando and time.monotonic() - inicio < MAX_SEGUNDOS:
                t0 = time.monotonic()
                # pixel_ratio=1: tamaño "lógico" (412 px de ancho), no el del celular x3
                cuadros.append(await self.page.take_screenshot(pixel_ratio=1))
                momentos.append(t0)
                transcurrido = int(t0 - inicio)
                self.lbl_tiempo.value = f"{transcurrido // 60}:{transcurrido % 60:02d}"
                self.page.update()
                await asyncio.sleep(max(0.0, INTERVALO - (time.monotonic() - t0)))
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Se detuvo la grabación: {ex}")
        finally:
            self.grabando = False
            self.pincel.hide()
            self.herr_pincel.visible = False
            self.btn_pincel.icon = ft.Icons.EDIT
            self._hide(self.barra_grabar)
            self._show(self.burbuja)
            self.page.update()

        if not cuadros:
            return
        # Cada cuadro dura lo que tardó en llegar el siguiente (el último, medio segundo)
        tiempos = [int((b - a) * 1000) for a, b in zip(momentos, momentos[1:])] + [500]
        notify(self.page, "Armando la grabación…")
        try:
            # Pillow trabaja fuera del hilo de la app para que no se congele
            captura = await asyncio.to_thread(save_recording, cuadros, tiempos, origen)
        except ImportError:
            notify(self.page, "Falta Pillow para grabar: pip install -r requirements.txt")
            return
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo guardar la grabación: {ex}")
            return
        self._done(captura, f"🎥 Grabación guardada ({len(cuadros)} cuadros)")

    # ==================================================================
    def _done(self, captura: Captura, texto: str):  # propio
        """Aviso con botón para reportarla de una vez (o queda en Mis capturas)."""
        self.page.show_dialog(
            ft.SnackBar(
                ft.Text(texto),
                action="Reportar",
                on_action=lambda e: self.on_report([captura]),
                duration=6000,
            )
        )

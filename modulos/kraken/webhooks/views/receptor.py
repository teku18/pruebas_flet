"""
Un receptor (/kraken/webhooks/receptor): su URL y lo que le llega.

  ← Stripe pruebas                                   ● Escuchando        [⋮]
  http://201.1.2.3:9555/kq3…Xb                                   [copiar]
  [Detener] [Probar]
  POST  /pagos?x=1          14:32:05 · 1.2 KB · 54.187.1.2     (●  = nuevo)
  POST  /                   14:30:11 · 312 B  · 54.187.1.2
                                         (tocar: headers, body, reenviar)

Mientras ves la pantalla, cada 5 s pregunta al servidor si llegó algo (como
el panel de SSH: se pausa si la app se va a segundo plano y se detiene al
salir). El receptor sigue guardando aunque no estés aquí.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
import json
from datetime import date

import flet as ft

from core.storage import human_size
from core.ui import confirm, notify
from modulos.kraken import routes
from modulos.kraken.comun import MONO, copy_text, method_badge
from modulos.kraken.models import Equipo, Receptor, WebhookRecibido
from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly
from modulos.kraken.webhooks import servicio
from modulos.kraken.webhooks.views.lista import receiver_dialog

CADA = 5


class ReceiverView:
    def __init__(self, page: ft.Page, on_to_http, on_deleted):
        """on_to_http(borrador): abrir en el Cliente HTTP · on_deleted(): volver a la lista."""
        self.page = page
        self.on_to_http = on_to_http
        self.on_deleted = on_deleted
        self.r: Receptor | None = None
        self.sesion: Sesion | None = None
        self.estado: servicio.Estado | None = None
        self.error: str | None = None
        self.activo = False
        self.pausado = False
        self.ocupado = False
        self.vistos_al_abrir: set[int] = set()
        self._despertar = asyncio.Event()
        self._lifecycle_anterior = None

        self.titulo = ft.Text()
        self.lbl_estado = ft.Text(size=12)
        self.punto = ft.Icon(ft.Icons.CIRCLE, size=10)
        self.menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT)
        self.cabecera = ft.Column(spacing=8)
        self.lista = ft.Column(spacing=2)
        self.vista = ft.View(
            route=routes.WEBHOOK,
            appbar=ft.AppBar(title=self.titulo, actions=[
                ft.Container(content=ft.Row(tight=True, spacing=4,
                                            controls=[self.punto, self.lbl_estado])),
                self.menu]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=12, controls=[
                self.cabecera, ft.Divider(height=1), self.lista, ft.Container(height=30)]))],
        )

    # ==================================================================
    # Abrir / cerrar / pausar
    # ==================================================================
    def open(self, r: Receptor):  # propio
        self.close()
        self.r = Receptor.get(r.id)
        self.estado, self.error = None, None
        self.activo, self.pausado = True, False
        self.vistos_al_abrir = {w.id for w in WebhookRecibido.of(self.r.id) if w.visto}
        self._lifecycle_anterior = self.page.on_app_lifecycle_state_change
        self.page.on_app_lifecycle_state_change = self._on_lifecycle
        self._render()
        self.page.navigate(routes.WEBHOOK)
        self.page.run_task(self._loop)

    def close(self):  # propio
        if not self.activo:
            return
        self.activo = False
        self._despertar.set()
        self.page.on_app_lifecycle_state_change = self._lifecycle_anterior
        if self.r is not None and Receptor.get(self.r.id):
            servicio.mark_seen(self.r)
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
                self._despertar.set()
        if callable(self._lifecycle_anterior):
            self._lifecycle_anterior(e)

    async def _loop(self):  # propio
        while self.activo:
            if self.pausado or self.page.route != routes.WEBHOOK:
                await self._wait(3600)
                continue
            await self._cycle()
            await self._wait(CADA if self.error is None else 30)

    async def _wait(self, segundos: float):  # propio
        self._despertar.clear()
        try:
            await asyncio.wait_for(self._despertar.wait(), segundos)
        except asyncio.TimeoutError:
            pass

    def wake(self):  # propio
        self._despertar.set()

    def _connected(self) -> Sesion:  # propio
        """(en un hilo) la sesión SSH, abriéndola si hace falta."""
        if self.sesion is None or not self.sesion.abierta:
            self.sesion = Sesion(Equipo.get(self.r.equipo_id))
            self.sesion.open()
        return self.sesion

    async def _cycle(self):  # propio
        if self.ocupado or self.r is None:
            return
        if not self.r.equipo_id or Equipo.get(self.r.equipo_id) is None:
            self.error = "El servidor de este receptor ya no existe en tus equipos."
            self._paint()
            return
        try:
            def leer():  # propio
                sesion = self._connected()
                estado = servicio.status(sesion, self.r)
                nuevos = servicio.fetch(sesion, self.r) if estado.instalado else 0
                return estado, nuevos
            self.estado, nuevos = await asyncio.to_thread(leer)
            self.error = None
        except HuellaCambio:
            self.error = "La huella del servidor cambió: ábrelo en SSH para revisarla."
            self.sesion, nuevos = None, 0
        except Exception as ex:  # noqa: BLE001
            self.error = friendly(ex, Equipo.get(self.r.equipo_id))
            self.sesion, nuevos = None, 0
        if self.r is not None:
            self.r = Receptor.get(self.r.id) or self.r
        self._paint(lista=bool(nuevos) or not self.lista.controls)

    def _paint(self, lista: bool = True):  # propio
        if not self.activo:
            return
        self._render(lista)
        try:
            self.page.update()
        except RuntimeError:
            pass

    # ==================================================================
    # Pintar
    # ==================================================================
    def _render(self, lista: bool = True):  # propio
        r = self.r
        self.titulo.value = r.nombre
        host = servicio.host_of(r) or "?"
        if self.error:
            color, texto = ft.Colors.RED, "Sin conexión"
        elif self.estado is None:
            color, texto = ft.Colors.GREY, "Conectando…"
        elif self.estado.activo:
            color, texto = ft.Colors.GREEN, "Escuchando"
        else:
            color, texto = (ft.Colors.ORANGE, self.estado.texto)
        self.punto.color = color
        self.lbl_estado.value = texto
        self.menu.items = [
            ft.PopupMenuItem(content=ft.Text("Editar"), icon=ft.Icons.EDIT,
                             on_click=lambda e: self.edit()),
            ft.PopupMenuItem(content=ft.Text("Abrir el puerto (ufw)"), icon=ft.Icons.SHIELD,
                             on_click=lambda e: self.page.run_task(self.open_port)),
            ft.PopupMenuItem(content=ft.Text("Limpiar lo recibido"),
                             icon=ft.Icons.CLEANING_SERVICES, on_click=lambda e: self.clear()),
            ft.PopupMenuItem(content=ft.Text("Desinstalar del servidor"),
                             icon=ft.Icons.REMOVE_CIRCLE_OUTLINE,
                             on_click=lambda e: self.confirm_uninstall()),
            ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                             on_click=lambda e: self.confirm_delete()),
        ]
        url = r.url(host)
        botones: list[ft.Control] = []
        instalado = self.estado.instalado if self.estado else r.instalado
        if self.estado is not None and not instalado:
            botones.append(ft.FilledButton("Instalar en el servidor", icon=ft.Icons.DOWNLOAD,
                                           disabled=self.ocupado,
                                           on_click=lambda e: self.page.run_task(self.install)))
        elif self.estado is not None and self.estado.activo:
            botones.append(ft.OutlinedButton("Detener", icon=ft.Icons.STOP, disabled=self.ocupado,
                                             on_click=lambda e: self.page.run_task(self.stop)))
        elif self.estado is not None:
            botones.append(ft.FilledButton("Iniciar", icon=ft.Icons.PLAY_ARROW,
                                           disabled=self.ocupado,
                                           on_click=lambda e: self.page.run_task(self.start)))
        botones.append(ft.OutlinedButton("Probar", icon=ft.Icons.SEND, disabled=self.ocupado,
                                         on_click=lambda e: self.page.run_task(self.test)))
        controles: list[ft.Control] = [
            ft.Container(
                padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                content=ft.Row(spacing=4, controls=[
                    ft.Text(url, font_family=MONO, size=12, selectable=True, expand=True),
                    ft.IconButton(ft.Icons.COPY, tooltip="Copiar URL",
                                  on_click=lambda e: self.page.run_task(copy_text, self.page, url,
                                                                        "URL copiada"))])),
            ft.Row(wrap=True, spacing=8, controls=botones),
        ]
        if self.ocupado:
            controles.append(ft.ProgressBar())
        if self.error:
            controles.append(ft.Text(self.error, color=ft.Colors.RED, size=12))
        elif self.estado and self.estado.detalle:
            controles.append(ft.Text(self.estado.detalle, color=ft.Colors.ORANGE, size=12))
        if self.estado is not None and not instalado:
            controles.append(ft.Text(
                f"Al instalar, Kraken copia un receptor pequeño (Python, sin dependencias) a "
                f"~/{r.carpeta} y lo deja escuchando en el puerto {r.puerto}. Vuelve solo si "
                "el servidor se reinicia.", size=12, color=ft.Colors.OUTLINE))
        self.cabecera.controls = controles
        if lista:
            self._render_list()

    def _render_list(self):  # propio
        recibidos = WebhookRecibido.of(self.r.id, 300)
        if not recibidos:
            self.lista.controls = [ft.Text(
                "Aún no llega nada. Pega la URL en el servicio que manda webhooks (o toca "
                "Probar).", italic=True, size=12, color=ft.Colors.OUTLINE)]
            return
        self.lista.controls = [
            ft.Text(f"{len(recibidos)} recibido{'s' if len(recibidos) != 1 else ''}",
                    size=12, color=ft.Colors.OUTLINE),
            *[self._row(w) for w in recibidos]]

    def _row(self, w: WebhookRecibido) -> ft.Control:  # propio
        nuevo = w.id not in self.vistos_al_abrir
        cuando = (f"{w.recibido_en:%H:%M:%S}" if w.recibido_en.date() == date.today()
                  else f"{w.recibido_en:%d/%m/%y %H:%M}")
        ruta = w.ruta + (f"?{w.query}" if w.query else "")
        return ft.Container(
            ink=True, border_radius=8, padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            on_click=lambda e: self.detail(w),
            content=ft.Row(spacing=8, controls=[
                method_badge(w.metodo),
                ft.Column(spacing=1, expand=True, controls=[
                    ft.Text(ruta, font_family=MONO, size=13, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            weight=ft.FontWeight.BOLD if nuevo else None),
                    ft.Text(f"{cuando} · {human_size(w.tamano)} · {w.ip or '?'}", size=11,
                            color=ft.Colors.OUTLINE)]),
                *([ft.Icon(ft.Icons.CIRCLE, size=8, color=ft.Colors.PINK)] if nuevo else []),
            ]))

    # ==================================================================
    # Acciones
    # ==================================================================
    async def _action(self, funcion, aviso: str | None = None):  # propio
        """Corre algo en el servidor (instalar, iniciar…) mostrando la barra."""
        if self.ocupado:
            return
        self.ocupado = True
        self._paint(lista=False)
        try:
            def correr():  # propio
                return funcion(self._connected(), self.r)
            resultado = await asyncio.to_thread(correr)
            if isinstance(resultado, servicio.Estado):
                self.estado = resultado
            self.error = None
            if aviso:
                notify(self.page, aviso if not isinstance(resultado, str) else resultado)
        except HuellaCambio:
            self.error = "La huella del servidor cambió: ábrelo en SSH para revisarla."
        except ValueError as ex:
            self.error = str(ex)
        except Exception as ex:  # noqa: BLE001
            self.error = friendly(ex, Equipo.get(self.r.equipo_id))
            self.sesion = None
        finally:
            self.ocupado = False
        self.r = Receptor.get(self.r.id) or self.r
        self._paint(lista=False)

    async def install(self):  # propio
        await self._action(servicio.install, "Receptor instalado y escuchando. Toca Probar.")

    async def start(self):  # propio
        await self._action(servicio.start, "Escuchando")

    async def stop(self):  # propio
        await self._action(servicio.stop, "Detenido: lo que llegue se pierde (el servicio que "
                                          "manda verá error)")

    async def open_port(self):  # propio
        await self._action(servicio.open_port, "ok")

    async def test(self):  # propio
        host = servicio.host_of(self.r)
        if not host:
            return
        self.ocupado = True
        self._paint(lista=False)
        ok, texto = await asyncio.to_thread(servicio.test_send, self.r, host)
        self.ocupado = False
        notify(self.page, texto)
        if ok:
            await self._cycle()       # que aparezca ya
        else:
            self._paint(lista=False)

    def edit(self):  # propio
        anterior = (self.r.puerto, self.r.status, self.r.respuesta, self.r.max_guardados)

        def guardado(r: Receptor):  # propio
            self.r = r
            cambio = (r.puerto, r.status, r.respuesta, r.max_guardados) != anterior
            if cambio and r.instalado:
                self.page.run_task(self._action, servicio.apply, "Receptor actualizado")
            else:
                self._paint()
        receiver_dialog(self.page, self.r, guardado)

    def clear(self):  # propio
        def ok():  # propio
            servicio.clear(self.r)
            self._paint()
        confirm(self.page, "Limpiar lo recibido",
                "Se borra la lista en la app (el servidor conserva su archivo, pero no se "
                "vuelve a traer).", ok, boton="Limpiar")

    def confirm_uninstall(self):  # propio
        def ok():  # propio
            self.page.run_task(self._action, servicio.uninstall, "Desinstalado del servidor")
        confirm(self.page, "Desinstalar del servidor",
                f"Se detiene el receptor y se borra ~/{self.r.carpeta} del servidor. Lo que ya "
                "tienes en la app se queda.", ok, boton="Desinstalar")

    def confirm_delete(self):  # propio
        def ok():  # propio
            async def borrar():  # propio
                if self.r.instalado:
                    await self._action(servicio.uninstall)
                    if self.error:
                        notify(self.page, f"No se pudo desinstalar del servidor: {self.error}")
                        return
                Receptor.delete(self.r.id)
                notify(self.page, "Receptor eliminado")
                self.close()
                self.on_deleted()
            self.page.run_task(borrar)
        confirm(self.page, "Eliminar receptor",
                f"¿Eliminar «{self.r.nombre}» y lo recibido? Si está instalado, también se "
                "desinstala del servidor.", ok)

    # ==================================================================
    # Un webhook
    # ==================================================================
    def detail(self, w: WebhookRecibido):  # propio
        cuerpo = servicio.body_text(w)
        if "json" in servicio.content_type(w).lower() or cuerpo.lstrip()[:1] in "{[":
            try:
                cuerpo = json.dumps(json.loads(cuerpo), ensure_ascii=False, indent=2)
            except ValueError:
                pass
        headers = "\n".join(f"{k}: {v}" for k, v in w.headers or [])
        seccion = lambda titulo, texto: [  # noqa: E731
            ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13),
            ft.Container(padding=8, border_radius=6, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                         content=ft.Text(texto or "(vacío)", font_family=MONO, size=12,
                                         selectable=True))]

        def a_http(e):  # propio
            self.page.pop_dialog()
            self.close()
            self.on_to_http(servicio.to_draft(w))

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Row(spacing=8, controls=[method_badge(w.metodo), ft.Text(
                w.ruta, font_family=MONO, size=15, expand=True, max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS)]),
            content=ft.Container(width=520, content=ft.Column(
                tight=True, scroll=ft.ScrollMode.AUTO, spacing=6, controls=[
                    ft.Text(f"{w.recibido_en:%d/%m/%Y %H:%M:%S} · {human_size(w.tamano)} · "
                            f"desde {w.ip or '?'}", size=12, color=ft.Colors.OUTLINE),
                    *(seccion("Query", w.query) if w.query else []),
                    *seccion("Body", cuerpo),
                    *seccion(f"Headers ({len(w.headers or [])})", headers)])),
            actions=[
                ft.TextButton("Copiar body", on_click=lambda e: self.page.run_task(
                    copy_text, self.page, servicio.body_text(w))),
                ft.TextButton("Abrir en Cliente HTTP", on_click=a_http),
                ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())],
        ))


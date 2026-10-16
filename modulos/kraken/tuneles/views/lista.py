"""
Exponer un puerto (/kraken/ssh/tuneles): URLs https://… hacia puertos de tus equipos.

  🌐 Odoo dev       Mi PC :8069 · ngrok          ● Abierto
     https://a1b2.ngrok-free.app          [copiar] [compartir] [cerrar]
  🌐 Webhooks · Stripe   Cliente ACME :9555 · Cloudflare   (del receptor)
                                                  [+ Exponer puerto]

Es `ngrok http 8069` sin ir a la terminal: la app lo corre por SSH en el equipo
y te da la URL para mandársela al consultor. Sigue abierto aunque cierres la
app; aquí lo cierras cuando termines.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.ui import add_button, confirm, icon_box, notify, service
from modulos.kraken import routes
from modulos.kraken.comun import MONO, copy_text, empty_state
from modulos.kraken.models import Ajustes, Equipo, TunelPublico
from modulos.kraken.models.tuneles import SERVICIOS
from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly
from modulos.kraken.tuneles import servicio


# ============================================================================
# Lo que falta antes de abrir: authtoken o el programa
# ============================================================================
def ask_ngrok_token(page: ft.Page, on_saved):  # propio
    """Pide el authtoken de ngrok (se guarda en la app, en texto normal)."""
    campo = ft.TextField(label="Authtoken de ngrok", value=Ajustes.current().ngrok_token or "",
                         autofocus=True, text_style=ft.TextStyle(font_family=MONO, size=12))

    def guardar(e):  # propio
        token = (campo.value or "").strip()
        if not token:
            return
        Ajustes.change(ngrok_token=token)
        page.pop_dialog()
        on_saved()

    async def abrir_panel(e):  # propio
        await service(page, ft.UrlLauncher).launch_url(servicio.TOKEN_AYUDA)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Tu authtoken de ngrok"),
        content=ft.Container(width=440, content=ft.Column(tight=True, spacing=10, controls=[
            ft.Text("Este equipo no tiene ngrok configurado. Copia tu authtoken de tu cuenta "
                    "de ngrok (gratis) y pégalo aquí: se guarda en la app y se le pone al "
                    "equipo.", size=13),
            ft.TextButton("Abrir mi cuenta de ngrok", icon=ft.Icons.OPEN_IN_NEW,
                          on_click=abrir_panel),
            campo])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar y abrir", on_click=guardar)],
    ))


async def ensure_ready(page: ft.Page, accion, equipo: Equipo, servicio_: str, reintentar):  # propio
    """
    Corre `accion()` (en un hilo). Si falta el authtoken o el programa, lo pide /
    instala y llama a `reintentar()`. Devuelve el resultado, o None si hubo que preguntar.
    """
    try:
        return await asyncio.to_thread(accion)
    except servicio.FaltaToken:
        ask_ngrok_token(page, reintentar)
    except servicio.FaltaPrograma as ex:
        falta = ex.servicio    # (ex deja de existir al salir del except)
        nombre = "ngrok" if falta == "ngrok" else "cloudflared (Cloudflare)"

        def instalar():  # propio
            async def bajar():  # propio
                notify(page, f"Bajando {nombre} a {equipo.nombre}…")
                try:
                    def correr():  # propio
                        with Sesion(equipo) as s:
                            return servicio.install(s, falta)
                    await asyncio.to_thread(correr)
                except Exception as err:  # noqa: BLE001
                    notify(page, f"No se pudo instalar: {err}")
                    return
                reintentar()
            page.run_task(bajar)

        confirm(page, f"Instalar {nombre}",
                f"{equipo.nombre} no tiene {nombre}. ¿Lo bajo de su sitio oficial a "
                "~/.controlkraken/bin? (sin sudo; necesita internet en el equipo)", instalar,
                boton="Instalar")
    return None


# ============================================================================
# La pantalla
# ============================================================================
class TunnelsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.estados: dict[int, servicio.Estado | str] = {}   # id -> Estado | "…" | error
        self.ocupados: set[int] = set()
        self.lista = ft.Column(spacing=6)
        self.vista = ft.View(
            route=routes.SSH_TUNELES,
            appbar=ft.AppBar(title=ft.Text("Exponer puertos"), actions=[
                ft.IconButton(ft.Icons.REFRESH, tooltip="Actualizar",
                              on_click=lambda e: self.page.run_task(self.check_all)),
                ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
                    ft.PopupMenuItem(content=ft.Text("Authtoken de ngrok"), icon=ft.Icons.KEY,
                                     on_click=lambda e: ask_ngrok_token(page, self.refresh))])]),
            scroll=ft.ScrollMode.AUTO,
            floating_action_button=add_button("Exponer puerto", lambda e: self.new()),
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                ft.Text("Una URL https:// hacia un puerto de tu PC o servidor (como ngrok http "
                        "8069), para compartir tu Odoo de desarrollo o recibir webhooks.",
                        size=12, color=ft.Colors.OUTLINE),
                self.lista, ft.Container(height=80)]))],
        )

    def open(self, equipo: Equipo | None = None):  # propio
        self.page.navigate(routes.SSH_TUNELES)
        if equipo is not None:
            self.new(equipo)

    def load(self):  # propio
        tuneles = TunelPublico.search_all()
        self.lista.controls = [self._row(t) for t in tuneles] or [empty_state(
            ft.Icons.PUBLIC, "Nada expuesto",
            "Toca «Exponer puerto», elige tu PC y el puerto (8069 para Odoo) y te da una URL "
            "https para el consultor. Usa ngrok (tu cuenta) o Cloudflare (sin cuenta).")]
        if tuneles and not self.estados:
            self.page.run_task(self.check_all)

    def refresh(self):  # propio
        self.load()
        try:
            self.page.update()
        except RuntimeError:
            pass

    def _row(self, t: TunelPublico) -> ft.Control:  # propio
        e = Equipo.get(t.equipo_id) if t.equipo_id else None
        estado = self.estados.get(t.id)
        if t.id in self.ocupados or estado == "…":
            chip, color = "…", ft.Colors.GREY
        elif isinstance(estado, servicio.Estado):
            chip, color = estado.texto, ft.Colors.GREEN if estado.activo else ft.Colors.GREY
        elif isinstance(estado, str):
            chip, color = "Sin conexión", ft.Colors.RED
        else:
            chip, color = "?", ft.Colors.GREY
        abierto = isinstance(estado, servicio.Estado) and estado.activo
        url = (estado.url if isinstance(estado, servicio.Estado) and estado.url else t.url)
        donde = f"{e.nombre if e else '(equipo borrado)'} :{t.puerto} · {SERVICIOS[t.servicio]}"
        if t.receptor_id:
            donde += " · de un receptor de webhooks"
        botones: list[ft.Control] = []
        if url and abierto:
            botones += [
                ft.IconButton(ft.Icons.COPY, tooltip="Copiar URL", on_click=lambda ev: self.page.run_task(
                    copy_text, self.page, url, "URL copiada")),
                ft.IconButton(ft.Icons.SHARE, tooltip="Compartir",
                              on_click=lambda ev: self.page.run_task(self.share, url))]
        if not t.receptor_id:
            botones.append(
                ft.OutlinedButton("Cerrar", icon=ft.Icons.STOP, disabled=t.id in self.ocupados,
                                  on_click=lambda ev: self.page.run_task(self.stop, t))
                if abierto else
                ft.FilledButton("Abrir", icon=ft.Icons.PLAY_ARROW, disabled=t.id in self.ocupados,
                                on_click=lambda ev: self.page.run_task(self.start, t)))
        detalle = [ft.Text(donde, size=12, color=ft.Colors.OUTLINE)]
        if url:
            detalle.append(ft.Text(url, font_family=MONO, size=12, selectable=True,
                                   color=None if abierto else ft.Colors.OUTLINE))
        if isinstance(estado, str) and estado != "…":
            detalle.append(ft.Text(estado, size=12, color=ft.Colors.RED))
        elif isinstance(estado, servicio.Estado) and estado.error:
            detalle.append(ft.Text(estado.error, size=12, color=ft.Colors.ORANGE))
        menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT, items=[
            ft.PopupMenuItem(content=ft.Text("Editar"), icon=ft.Icons.EDIT,
                             on_click=lambda ev: self.edit(t)),
            ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                             on_click=lambda ev: self.confirm_delete(t)),
        ]) if not t.receptor_id else None
        return ft.Card(content=ft.Container(padding=12, content=ft.Column(spacing=6, controls=[
            ft.Row(spacing=12, controls=[
                icon_box(ft.Icons.PUBLIC, ft.Colors.GREEN if abierto else ft.Colors.GREY),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Row([ft.Text(t.nombre, weight=ft.FontWeight.BOLD, expand=True),
                            ft.Text(chip, size=12, color=color)]),
                    *detalle]),
                *([menu] if menu else [])]),
            ft.Row(alignment=ft.MainAxisAlignment.END, spacing=4, controls=botones),
        ])))

    # ==================================================================
    async def check_all(self):  # propio
        """Pregunta a cada equipo (una conexión por equipo) cómo están sus túneles."""
        tuneles = TunelPublico.search_all()
        for t in tuneles:
            self.estados[t.id] = "…"
        self.refresh()
        por_equipo: dict[int, list[TunelPublico]] = {}
        for t in tuneles:
            por_equipo.setdefault(t.equipo_id or 0, []).append(t)

        def revisar(equipo_id, lista):  # propio
            e = Equipo.get(equipo_id) if equipo_id else None
            if e is None:
                return {t.id: "El equipo ya no existe" for t in lista}
            try:
                with Sesion(e) as s:
                    return {t.id: servicio.status(s, t) for t in lista}
            except HuellaCambio:
                return {t.id: "La huella del equipo cambió: ábrelo en SSH" for t in lista}
            except Exception as ex:  # noqa: BLE001
                return {t.id: friendly(ex, e) for t in lista}

        resultados = await asyncio.gather(*[asyncio.to_thread(revisar, k, v)
                                            for k, v in por_equipo.items()])
        for r in resultados:
            self.estados.update(r)
        self.refresh()

    async def start(self, t: TunelPublico):  # propio
        e = Equipo.get(t.equipo_id)
        if e is None:
            return
        self.ocupados.add(t.id)
        self.refresh()

        def abrir():  # propio
            with Sesion(e) as s:
                return servicio.start(s, TunelPublico.get(t.id))
        try:
            estado = await ensure_ready(self.page, abrir, e, t.servicio,
                                        lambda: self.page.run_task(self.start, t))
            if estado is not None:
                self.estados[t.id] = estado
                notify(self.page, "Abierto: copia o comparte la URL")
        except Exception as ex:  # noqa: BLE001
            self.estados[t.id] = str(ex) if isinstance(ex, ValueError) else friendly(ex, e)
        finally:
            self.ocupados.discard(t.id)
        self.refresh()

    async def stop(self, t: TunelPublico):  # propio
        e = Equipo.get(t.equipo_id)
        self.ocupados.add(t.id)
        self.refresh()
        try:
            def cerrar():  # propio
                with Sesion(e) as s:
                    return servicio.stop(s, t)
            self.estados[t.id] = await asyncio.to_thread(cerrar)
            notify(self.page, "Cerrado: esa URL ya no responde")
        except Exception as ex:  # noqa: BLE001
            self.estados[t.id] = friendly(ex, e)
        finally:
            self.ocupados.discard(t.id)
        self.refresh()

    async def share(self, url: str):  # propio
        try:
            await service(self.page, ft.Share).share_text(url)
        except Exception:  # noqa: BLE001  (en la compu no hay "compartir")
            await copy_text(self.page, url, "URL copiada")

    def confirm_delete(self, t: TunelPublico):  # propio
        def ok():  # propio
            async def borrar():  # propio
                e = Equipo.get(t.equipo_id) if t.equipo_id else None

                def correr():  # propio
                    if e is None:
                        servicio.remove(None, t)
                        return
                    with Sesion(e) as s:
                        servicio.remove(s, t)
                try:
                    await asyncio.to_thread(correr)
                except Exception as ex:  # noqa: BLE001
                    notify(self.page, f"No se pudo cerrar en el equipo ({friendly(ex, e)}); "
                                      "se quita de la app")
                    TunelPublico.delete(t.id)
                self.estados.pop(t.id, None)
                self.refresh()
            self.page.run_task(borrar)
        confirm(self.page, "Eliminar", f"¿Cerrar y quitar «{t.nombre}»?", ok)

    def new(self, equipo: Equipo | None = None):  # propio
        tunnel_dialog(self.page, None, lambda t: (self.refresh(),
                                                  self.page.run_task(self.start, t)), equipo)

    def edit(self, t: TunelPublico):  # propio
        def guardado(nuevo: TunelPublico):  # propio
            self.estados.pop(nuevo.id, None)
            self.refresh()
            notify(self.page, "Guardado: ciérralo y ábrelo para usar los cambios")
        tunnel_dialog(self.page, t, guardado)


def tunnel_dialog(page: ft.Page, t: TunelPublico | None, on_saved,  # propio
                  equipo: Equipo | None = None):
    servidores = [e for e in Equipo.search_all() if e.tiene_ssh]
    if not servidores:
        notify(page, "Primero agrega tu PC o servidor en Kraken > SSH")
        return
    elegido = (t.equipo_id if t else (equipo.id if equipo else servidores[0].id))
    txt_nombre = ft.TextField(label="Nombre", value=t.nombre if t else "Odoo dev", dense=True)
    dd_equipo = ft.Dropdown(label="Equipo", dense=True, expand=True, value=str(elegido),
                            options=[ft.DropdownOption(key=str(e.id), text=f"{e.nombre} · {e.host}")
                                     for e in servidores])
    txt_puerto = ft.TextField(label="Puerto", value=str(t.puerto if t else 8069), width=110,
                              dense=True, keyboard_type=ft.KeyboardType.NUMBER)
    seleccion = {"servicio": t.servicio if t else "ngrok"}
    txt_dominio = ft.TextField(label="Dominio fijo de ngrok (opcional)",
                               value=(t.dominio or "") if t else "", dense=True,
                               hint_text="mi-nombre.ngrok-free.app")
    fila_servicio = ft.Container()
    lbl_ayuda = ft.Text(size=12, color=ft.Colors.OUTLINE)
    lbl_error = ft.Text(size=12, color=ft.Colors.RED)

    def pintar():  # propio
        s = seleccion["servicio"]
        fila_servicio.content = ft.Row(spacing=6, controls=[
            ft.Chip(label=ft.Text(nombre), selected=s == clave, show_checkmark=False,
                    on_select=lambda e, c=clave: elegir(c)) for clave, nombre in SERVICIOS.items()])
        txt_dominio.visible = s == "ngrok"
        lbl_ayuda.value = ("ngrok: con tu cuenta (authtoken). La gratis permite un túnel a la vez y "
                           "te da un dominio fijo que no cambia." if s == "ngrok" else
                           "Cloudflare: sin cuenta, pero la URL cambia cada vez que lo abres.")

    def elegir(clave):  # propio
        seleccion["servicio"] = clave
        pintar()
        page.update()

    pintar()

    def guardar(e):  # propio
        try:
            valores = dict(nombre=(txt_nombre.value or "").strip(), equipo_id=int(dd_equipo.value),
                           puerto=int(txt_puerto.value or 0), servicio=seleccion["servicio"],
                           dominio=(txt_dominio.value or "").strip() or None)
            nuevo = TunelPublico.update(t.id, **valores) if t else TunelPublico.create(**valores)
        except ValueError as ex:
            lbl_error.value = ("El puerto debe ser un número" if "invalid literal" in str(ex)
                               else str(ex))
            page.update()
            return
        page.pop_dialog()
        on_saved(nuevo)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar" if t else "Exponer puerto"),
        content=ft.Container(width=440, content=ft.Column(tight=True, spacing=10, controls=[
            txt_nombre, ft.Row([dd_equipo, txt_puerto]), fila_servicio, lbl_ayuda, txt_dominio,
            lbl_error])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar" if t else "Abrir", on_click=guardar)],
    ))

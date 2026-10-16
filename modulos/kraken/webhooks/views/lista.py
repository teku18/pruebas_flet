"""
Webhooks (/kraken/webhooks): tus receptores.

  🪝 Stripe pruebas     Cliente ACME :9555            (3 nuevos)
  🪝 GitHub deploys     Mi VPS :9556
                                              [+ Nuevo receptor]

Un receptor vive en uno de tus servidores SSH: escucha en un puerto y guarda
lo que le llega aunque el cel esté apagado. Tocar uno: su URL y lo recibido.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, icon_box, notify
from modulos.kraken import routes
from modulos.kraken.comun import empty_state
from modulos.kraken.models import Equipo, Receptor, WebhookRecibido
from modulos.kraken.models.webhooks import PUERTO_POR_DEFECTO, RESPUESTA_POR_DEFECTO


class ReceiversView:
    def __init__(self, page: ft.Page, on_open):
        """on_open(receptor): abre su pantalla."""
        self.page = page
        self.on_open = on_open
        self.lista = ft.Column(spacing=6)
        self.vista = ft.View(
            route=routes.WEBHOOKS,
            appbar=ft.AppBar(title=ft.Text("Webhooks")),
            scroll=ft.ScrollMode.AUTO,
            floating_action_button=add_button("Nuevo receptor", lambda e: self.new()),
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                ft.Text("Un receptor escucha en uno de tus servidores y guarda lo que le "
                        "llega, aunque el cel esté apagado.", size=12, color=ft.Colors.OUTLINE),
                self.lista, ft.Container(height=80)]))],
        )

    def load(self):  # propio
        receptores = Receptor.search_all()
        self.lista.controls = [self._row(r) for r in receptores] or [empty_state(
            ft.Icons.WEBHOOK, "Tu primer receptor",
            "Elige uno de tus servidores SSH y un puerto: Kraken instala ahí un receptor y te "
            "da una URL para pegar en Stripe, GitHub, Odoo, Mercado Pago… Lo que llegue lo ves "
            "aquí, con headers y body.")]

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _row(self, r: Receptor) -> ft.Control:  # propio
        e = Equipo.get(r.equipo_id) if r.equipo_id else None
        nuevos = WebhookRecibido.unseen(r.id)
        donde = f"{e.nombre} · {e.host}:{r.puerto}" if e else "(servidor borrado)"
        if not r.instalado:
            donde += " · sin instalar"
        return ft.Card(content=ft.Container(
            padding=12, ink=True, border_radius=12, on_click=lambda ev: self.on_open(r),
            content=ft.Row(spacing=12, controls=[
                icon_box(ft.Icons.WEBHOOK, ft.Colors.PINK if r.instalado else ft.Colors.GREY),
                ft.Column(spacing=2, expand=True, controls=[
                    ft.Text(r.nombre, weight=ft.FontWeight.BOLD),
                    ft.Text(donde, size=12, color=ft.Colors.OUTLINE)]),
                *([ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=10,
                    bgcolor=ft.Colors.PINK,
                    content=ft.Text(f"{nuevos} nuevo{'s' if nuevos != 1 else ''}", size=11,
                                    color=ft.Colors.WHITE))] if nuevos else []),
            ]),
        ))

    def new(self):  # propio
        receiver_dialog(self.page, None, lambda r: (self.refresh(), self.on_open(r)))


def receiver_dialog(page: ft.Page, r: Receptor | None, on_saved):  # propio
    """Alta o edición. on_saved(receptor)."""
    servidores = [e for e in Equipo.search_all() if e.tiene_ssh]
    if not servidores and r is None:
        notify(page, "Primero agrega un servidor en Kraken > SSH")
        return

    def campo(label, valor, **kw):  # propio
        return ft.TextField(label=label, value="" if valor is None else str(valor), dense=True,
                            **kw)

    txt_nombre = campo("Nombre", r.nombre if r else "", hint_text="Stripe pruebas")
    dd_servidor = ft.Dropdown(
        label="Servidor", dense=True, expand=True, disabled=bool(r and r.instalado),
        value=str(r.equipo_id) if r and r.equipo_id else (str(servidores[0].id) if servidores
                                                          else None),
        options=[ft.DropdownOption(key=str(e.id), text=f"{e.nombre} · {e.host}")
                 for e in servidores])
    txt_puerto = campo("Puerto", r.puerto if r else PUERTO_POR_DEFECTO, width=110,
                       keyboard_type=ft.KeyboardType.NUMBER)
    txt_max = campo("Guardar los últimos", r.max_guardados if r else 500, width=170,
                    keyboard_type=ft.KeyboardType.NUMBER)
    txt_status = campo("Responder con", r.status if r else 200, width=130,
                       keyboard_type=ft.KeyboardType.NUMBER)
    txt_resp = campo("Cuerpo de la respuesta", r.respuesta if r else RESPUESTA_POR_DEFECTO,
                     multiline=True, min_lines=1, max_lines=4,
                     text_style=ft.TextStyle(font_family="monospace"))
    lbl_error = ft.Text(color=ft.Colors.RED, size=12)

    def guardar(e):  # propio
        try:
            valores = dict(nombre=(txt_nombre.value or "").strip(),
                           equipo_id=int(dd_servidor.value) if dd_servidor.value else None,
                           puerto=int(txt_puerto.value or 0),
                           max_guardados=int(txt_max.value or 0),
                           status=int(txt_status.value or 0), respuesta=txt_resp.value or "")
            for otro in Receptor.search_all():
                if (otro.equipo_id == valores["equipo_id"] and otro.puerto == valores["puerto"]
                        and (r is None or otro.id != r.id)):
                    raise ValueError(f"«{otro.nombre}» ya usa ese puerto en ese servidor")
            guardado = Receptor.update(r.id, **valores) if r else Receptor.create(**valores)
        except ValueError as ex:
            lbl_error.value = str(ex) if "invalid literal" not in str(ex) else \
                "Puerto, cantidad y código deben ser números"
            page.update()
            return
        page.pop_dialog()
        on_saved(guardado)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar receptor" if r else "Nuevo receptor"),
        content=ft.Container(width=440, content=ft.Column(tight=True, spacing=10, controls=[
            txt_nombre, ft.Row([dd_servidor]),
            ft.Row([txt_puerto, txt_max], wrap=True),
            ft.Text("El puerto debe estar libre y abierto en el firewall del servidor (mayor a "
                    "1024).", size=12, color=ft.Colors.OUTLINE),
            ft.Row([txt_status]), txt_resp, lbl_error])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar", on_click=guardar)],
    ))

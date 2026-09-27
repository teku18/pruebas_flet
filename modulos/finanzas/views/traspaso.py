"""
Herramienta de Traspaso (/finanzas/traspaso), desde el ícono ⇄ de los movimientos.

Capturas UNA vez: monto, de dónde sale (concepto + plataforma), a dónde
entra (concepto + plataforma) y la fecha. La app crea los DOS movimientos
(salida y entrada) ligados entre sí.
  Entre plataformas: Reto ahorro · Nu   -> Reto ahorro · Finsus
  Entre conceptos:   Vacaciones · Nu    -> Mio · Nu
  (el concepto destino se copia del origen hasta que lo cambies)
"""
from datetime import date

import flet as ft

from core.ui import DateField, notify, short_date
from modulos.finanzas import routes
from modulos.finanzas.models import Inversion, Movimiento, Plataforma
from modulos.finanzas.views.movimientos import NUEVO, catalog_dropdown


class TransferView:
    def __init__(self, page: ft.Page, get_period):
        """get_period: función que regresa el periodo abierto (lo tiene Movimientos)."""
        self.page = page
        self.get_period = get_period

        self.fila_origen = ft.Row()
        self.fila_destino = ft.Row()
        self.txt_monto = ft.TextField(
            label="Monto",
            prefix="$ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
        )
        self.campo_fecha = DateField(page, "Fecha")
        self.txt_comentarios = ft.TextField(label="Comentarios", max_length=255)

        self.vista = ft.View(
            route=routes.TRASPASO,
            appbar=ft.AppBar(title=ft.Text("Traspaso")),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Text(
                                "Mueve dinero entre plataformas o entre conceptos. "
                                "No cuenta como ingreso ni gasto del periodo.",
                                size=12,
                                color=ft.Colors.OUTLINE,
                            ),
                            self.txt_monto,
                            ft.Text("Sale de", weight=ft.FontWeight.W_500),
                            self.fila_origen,
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                controls=[ft.Icon(ft.Icons.ARROW_DOWNWARD,
                                                  color=ft.Colors.PRIMARY)],
                            ),
                            ft.Text("Entra a", weight=ft.FontWeight.W_500),
                            self.fila_destino,
                            self.campo_fecha.fila,
                            self.txt_comentarios,
                            ft.Row([
                                ft.Button("Traspasar", icon=ft.Icons.SWAP_HORIZ,
                                          on_click=self.save),
                                ft.TextButton("Cancelar", icon=ft.Icons.CLOSE,
                                              on_click=lambda e: self.page.navigate(
                                                  routes.MOVIMIENTOS)),
                            ]),
                        ],
                    )
                )
            ],
        )

    def clear_form(self):  # propio
        """Dropdowns nuevos (con + Nueva…) y fecha dentro del periodo."""
        self.dd_inv_origen = catalog_dropdown(self.page, Inversion)
        self.dd_origen = catalog_dropdown(self.page, Plataforma)
        self.dd_inv_destino = catalog_dropdown(self.page, Inversion)
        self.dd_destino = catalog_dropdown(self.page, Plataforma)
        self.destino_tocado = False  # mientras no lo toques, copia el concepto origen

        seleccion_origen = self.dd_inv_origen.on_select
        seleccion_destino = self.dd_inv_destino.on_select

        def on_origin(e):  # propio
            seleccion_origen(e)
            if not self.destino_tocado and self.dd_inv_origen.data:
                self.dd_inv_destino.value = self.dd_inv_destino.data = self.dd_inv_origen.data
                self.page.update()

        def on_destination(e):  # propio
            seleccion_destino(e)
            self.destino_tocado = True

        self.dd_inv_origen.on_select = on_origin
        self.dd_inv_destino.on_select = on_destination
        self.fila_origen.controls = [self.dd_inv_origen, self.dd_origen]
        self.fila_destino.controls = [self.dd_inv_destino, self.dd_destino]
        self.txt_monto.value = ""
        self.txt_monto.error_text = None
        self.txt_comentarios.value = ""
        self.campo_fecha.txt.error_text = None

        periodo = self.get_period()
        self.campo_fecha.set_range(periodo.fecha_inicio, periodo.fecha_fin)
        hoy = date.today()
        self.campo_fecha.set_value(min(max(hoy, periodo.fecha_inicio), periodo.fecha_fin))

    def open(self, e=None):  # propio
        self.clear_form()
        self.page.navigate(routes.TRASPASO)

    def save(self, e=None):  # propio
        faltantes = False
        dds = (self.dd_inv_origen, self.dd_origen, self.dd_inv_destino, self.dd_destino)
        for dd in dds:
            dd.error_text = None
            if not dd.value or dd.value == NUEVO:
                dd.error_text = "Requerido"
                faltantes = True
        if not faltantes and (self.dd_inv_origen.value, self.dd_origen.value) == \
                (self.dd_inv_destino.value, self.dd_destino.value):
            self.dd_destino.error_text = "Cambia el concepto o la plataforma"
            faltantes = True
        try:
            monto = float(self.txt_monto.value)
            if monto <= 0:
                raise ValueError
            self.txt_monto.error_text = None
        except (TypeError, ValueError):
            self.txt_monto.error_text = "Monto inválido"
            faltantes = True
        periodo = self.get_period()
        if not (periodo.fecha_inicio <= self.campo_fecha.valor <= periodo.fecha_fin):
            self.campo_fecha.txt.error_text = (
                f"Debe estar entre {short_date(periodo.fecha_inicio)} "
                f"y {short_date(periodo.fecha_fin)}"
            )
            faltantes = True
        if faltantes:
            self.page.update()
            return

        try:
            Movimiento.create_transfer(
                periodo_id=periodo.id,
                monto=monto,
                fecha=self.campo_fecha.valor,
                origen_inversion_id=int(self.dd_inv_origen.value),
                origen_plataforma_id=int(self.dd_origen.value),
                destino_inversion_id=int(self.dd_inv_destino.value),
                destino_plataforma_id=int(self.dd_destino.value),
                comentarios=(self.txt_comentarios.value or "").strip() or None,
            )
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return
        notify(self.page, "Traspaso registrado")
        self.page.navigate(routes.MOVIMIENTOS)

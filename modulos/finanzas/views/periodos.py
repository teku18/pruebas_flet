"""
Pantallas de Periodos (cabecera de los movimientos):
  /finanzas                      -> lista de periodos
  /finanzas/periodo              -> nuevo periodo (desde el botón +)
  /finanzas/movimientos/periodo  -> datos del periodo abierto (desde el engrane)

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
              abajo: [Cerrar periodo] (o [Reabrir] si ya está cerrado)
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]
  "cerrar" -> datos del periodo SIGUIENTE (propuestos) + saldos con que abrirá,
              [Cerrar y abrir] [Cancelar]

[Cerrar periodo] pregunta cómo:
  Solo cerrar             -> queda 🔒 y sale del global; tú abres otro con + y
                             capturas los saldos iniciales (se muestran sus
                             "Saldos al cierre" para copiarlos)
  Cerrar y abrir siguiente -> modo "cerrar" (arriba)

Circuito de un periodo:
  creado con + -> abre en $0 ... movimientos ... Cerrar -> 🔒 solo lectura
                                                        -> el siguiente abre con
                                                           sus saldos finales

Los métodos marcados con  # propio  son nuestros; lo demás (page.update,
page.navigate, controles ft.*) viene de Flet.
"""
import calendar
from datetime import date

import flet as ft

from core.ui import (
    DateField,
    confirm,
    delete_button,
    edit_button,
    icon_box,
    notify,
    add_button,
    short_date,
    swipe_to_delete,
)
from modulos.finanzas import routes
from modulos.finanzas.models import Periodo
from modulos.finanzas.services import (
    balance_by_platform,
    close_only,
    close_period,
    closing_balances,
    global_balance,
    money,
    period_summary,
    reopen_period,
    suggest_next,
)


class PeriodsView:
    def __init__(self, page: ft.Page, on_open_period, on_reports):
        """
        on_open_period: función que se llama al tocar un periodo
        (la pantalla de movimientos se encarga de mostrarlo).
        """
        self.page = page
        self.on_open_period = on_open_period
        self.on_reports = on_reports  # 📊: reportes de todos los periodos
        self.registro: Periodo | None = None  # periodo mostrado en el formulario
        self.modo = "nuevo"                   # "nuevo" | "ver" | "editar"

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista
    # ==================================================================
    def _build_list(self):  # propio
        self.lista = ft.ListView(
            expand=True,
            spacing=4,
            padding=ft.Padding.only(bottom=90),  # espacio para el botón +
        )
        self.lbl_vacio = ft.Text(
            "Aún no hay periodos. Crea uno con el botón + o importa tu Excel "
            "desde el engrane.", italic=True
        )
        self.tarjeta_global = ft.Container()

        self.vista_lista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(
                title=ft.Text("Finanzas · Periodos"),
                actions=[
                    # Reportes: pastel por plataforma y ahorro mensual
                    ft.IconButton(ft.Icons.INSIGHTS, tooltip="Reportes",
                                  on_click=lambda e: self.on_reports()),
                    # Engrane: catálogos e importación
                    ft.IconButton(ft.Icons.SETTINGS, tooltip="Ajustes de Finanzas",
                                  on_click=lambda e: self.page.navigate(routes.AJUSTES)),
                ],
            ),
            floating_action_button=add_button("Nuevo periodo", self.new),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(
                        expand=True, controls=[self.tarjeta_global, self.lbl_vacio, self.lista]
                    ),
                )
            ],
        )

    def _global_card(self) -> ft.Control:  # propio
        """Acumulado global, y al desplegar: cuánto hay en cada plataforma."""
        return ft.Container(
            border_radius=12,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            content=ft.ExpansionTile(
                title=ft.Text(money(global_balance()), size=22, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text("Acumulado global (periodos abiertos) · toca para ver "
                                 "por plataforma", size=12),
                controls=[
                    ft.ListTile(dense=True, title=ft.Text(nombre), trailing=ft.Text(money(saldo)))
                    for nombre, saldo in balance_by_platform()
                ],
            ),
        )

    def load(self):  # propio
        periodos = Periodo.search_all()
        cantidades = Periodo.count_movements()
        self.lista.controls = [self._row(p, cantidades.get(p.id, 0)) for p in periodos]
        self.lbl_vacio.visible = not periodos
        self.tarjeta_global.content = self._global_card() if periodos else None

    def _row(self, per: Periodo, cantidad: int) -> ft.Control:  # propio
        """Una línea de la lista de periodos. Al tocarla se abre el periodo."""
        texto_cantidad = "1 movimiento" if cantidad == 1 else f"{cantidad} movimientos"
        resumen = period_summary(per)
        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,  # efecto al tocar
            on_click=lambda e, p=per: self.on_open_period(p),
            content=ft.Row(
                spacing=10,
                controls=[
                    # PRIMARY: toma el color del tema elegido en Configuración
                    # 🔒 si está cerrado (gris), si no el color del tema
                    icon_box(ft.Icons.LOCK, ft.Colors.OUTLINE) if per.cerrado
                    else icon_box(ft.Icons.CALENDAR_MONTH, ft.Colors.PRIMARY),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(per.nombre, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{short_date(per.fecha_inicio)} – {short_date(per.fecha_fin)}",
                                size=12,
                            ),
                            ft.Text(texto_cantidad + (" · cerrado" if per.cerrado else ""),
                                    size=12, color=ft.Colors.OUTLINE),
                        ],
                    ),
                    # A la derecha: neto del periodo (ingresos - gastos) y con cuánto cierra
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Text(money(resumen.neto, signo=True), size=15,
                                    color=ft.Colors.GREEN if resumen.neto >= 0
                                    else ft.Colors.ORANGE),
                            ft.Text(f"cierra {money(resumen.saldo_cierre)}", size=11,
                                    color=ft.Colors.OUTLINE),
                        ],
                    ),
                ],
            ),
        )
        # ◄── deslizar a la izquierda: eliminar (con confirmación), igual que movimientos
        return swipe_to_delete(
            self.page,
            key=f"periodo-{per.id}",
            contenido=linea,
            titulo="Eliminar periodo",
            mensaje=self._delete_message(per, cantidad),
            on_delete=lambda p=per: self._delete(p),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        self.txt_nombre = ft.TextField(label="Nombre", max_length=100)
        self.campo_inicio = DateField(self.page, "Fecha inicio")
        self.campo_fin = DateField(self.page, "Fecha fin")

        self.lbl_titulo_form = ft.Text("Nuevo periodo")  # va en la barra superior
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        # Cierre: botón en modo "ver" y vista previa de saldos en modo "cerrar"
        self.lbl_estado = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.btn_cerrar = ft.OutlinedButton("Cerrar periodo", icon=ft.Icons.LOCK,
                                            on_click=self.choose_close)
        self.btn_reabrir = ft.OutlinedButton("Reabrir periodo", icon=ft.Icons.LOCK_OPEN,
                                             on_click=self.confirm_reopen)
        self.saldos_cierre = ft.Column(spacing=0)

        # Lápiz y bote en la barra superior (solo en modo "ver")
        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.PERIODO,  # el módulo la ajusta: PERIODO o MOVIMIENTOS_PERIODO
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.txt_nombre,
                            self.campo_inicio.fila,
                            self.campo_fin.fila,
                            self.fila_botones,
                            self.lbl_estado,
                            ft.Row([self.btn_cerrar, self.btn_reabrir]),
                            self.saldos_cierre,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _apply_mode(self):  # propio
        """Ajusta campos, botones y título según self.modo."""
        lectura = self.modo == "ver"
        cerrado = bool(self.registro and self.registro.cerrado)

        self.txt_nombre.read_only = lectura
        self.campo_inicio.set_enabled(not lectura)
        self.campo_fin.set_enabled(not lectura)

        self.btn_barra_editar.visible = lectura and not cerrado  # cerrado = solo lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura
        self.btn_cerrar.visible = lectura and not cerrado
        self.btn_reabrir.visible = lectura and cerrado
        # Saldos: vista previa al cerrar, o de consulta en un periodo ya cerrado
        self.saldos_cierre.visible = self.modo == "cerrar" or (lectura and cerrado)
        if lectura and cerrado:
            self._fill_balances(titulo="Saldos al cierre")
        self.lbl_estado.visible = lectura or self.modo == "cerrar"
        if lectura:
            self.lbl_estado.value = self._status_text()
        elif self.modo == "cerrar":
            self.lbl_estado.value = (
                f"Se cerrará «{self.registro.nombre}» (quedará en solo lectura) y se "
                "abrirá este periodo nuevo con estos saldos iniciales:"
            )

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo periodo"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Periodo"
        elif self.modo == "cerrar":
            self.lbl_titulo_form.value = "Cerrar y abrir siguiente"
            self.btn_guardar.content = "Cerrar y abrir"
        else:
            self.lbl_titulo_form.value = "Editar periodo"
            self.btn_guardar.content = "Actualizar"

    def _status_text(self) -> str:  # propio
        """'Abrió en $0' / 'Viene del cierre de …' / '🔒 Cerrado: sus saldos pasaron a …'."""
        per = self.registro
        if per is None:
            return ""
        origen = Periodo.get(per.origen_id) if per.origen_id else None
        apertura = period_summary(per).saldo_apertura
        if origen:
            partes = [f"Viene del cierre de «{origen.nombre}» (abrió con {money(apertura)})."]
        elif apertura:
            partes = [f"Abrió con {money(apertura)} de saldos iniciales."]
        else:
            partes = ["Abrió en $0."]
        if per.cerrado:
            hijos = Periodo.children(per.id)
            if hijos:
                partes.append(f"Cerrado: sus saldos pasaron a «{hijos[0].nombre}».")
            else:
                partes.append("Cerrado sin abrir otro: ya no suma al acumulado global.")
        return " ".join(partes)

    def _fill(self, per: Periodo):  # propio
        """Pasa los datos del registro a los campos."""
        self.txt_nombre.value = per.nombre
        self.campo_inicio.set_value(per.fecha_inicio)
        self.campo_fin.set_value(per.fecha_fin)

    def clear_errors(self):  # propio
        self.txt_nombre.error_text = None
        self.campo_fin.txt.error_text = None

    def clear_form(self):  # propio
        """Por defecto propone el mes actual completo."""
        self.clear_errors()
        hoy = date.today()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        self.txt_nombre.value = ""
        self.campo_inicio.set_value(hoy.replace(day=1))
        self.campo_fin.set_value(hoy.replace(day=ultimo_dia))
        self.registro = None
        self.modo = "nuevo"
        self._apply_mode()

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        """Botón +: abre el formulario de periodo vacío."""
        self.clear_form()
        self.page.navigate(routes.PERIODO)

    def show(self, per: Periodo):  # propio
        """Engrane (desde movimientos): muestra el periodo en solo lectura."""
        self.clear_errors()
        self.registro = Periodo.get(per.id)  # datos frescos de la BD
        self._fill(self.registro)
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.MOVIMIENTOS_PERIODO)

    def edit(self, e=None):  # propio
        """Lápiz: habilita los campos del periodo mostrado."""
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo in ("editar", "cerrar"):
            # Descarta los cambios: vuelve a leer el registro y regresa a "ver"
            self.clear_errors()
            self.registro = Periodo.get(self.registro.id)
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(routes.BASE)

    def save(self, e=None):  # propio
        self.clear_errors()
        nombre = (self.txt_nombre.value or "").strip()
        faltantes = False
        if not nombre:
            self.txt_nombre.error_text = "Requerido"
            faltantes = True
        if self.campo_fin.valor < self.campo_inicio.valor:
            self.campo_fin.txt.error_text = "No puede ser anterior a la fecha inicio"
            faltantes = True
        if faltantes:
            self.page.update()
            return

        valores = dict(
            nombre=nombre,
            fecha_inicio=self.campo_inicio.valor,
            fecha_fin=self.campo_fin.valor,
        )
        try:
            if self.modo == "nuevo":
                Periodo.create(**valores)
            elif self.modo == "cerrar":
                nuevo = close_period(self.registro, nombre, valores["fecha_inicio"],
                                     valores["fecha_fin"])
            else:
                self.registro = Periodo.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "cerrar":
            self.clear_form()
            notify(self.page, f"Periodo cerrado. «{nuevo.nombre}» abierto con sus saldos")
            self.on_open_period(nuevo)  # directo a los movimientos del nuevo
        elif self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Periodo guardado")
            self.page.navigate(routes.BASE)  # regresa a la lista de periodos
        else:
            # Se queda en el registro, ahora en solo lectura
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Periodo actualizado")
            self.page.update()

    # ==================================================================
    # Cerrar / reabrir
    # ==================================================================
    def start_close(self, e=None):  # propio
        """[Cerrar periodo]: propone el siguiente y muestra con qué saldos abrirá."""
        nombre, inicio, fin = suggest_next(self.registro)
        self.txt_nombre.value = nombre
        self.campo_inicio.set_value(inicio)
        self.campo_fin.set_value(fin)

        self._fill_balances()
        self.modo = "cerrar"
        self._apply_mode()
        self.page.update()

    def _fill_balances(self, titulo: str | None = None):  # propio
        """Lista concepto/plataforma/saldo final del periodo mostrado + total."""
        saldos = closing_balances(self.registro)
        filas = [ft.Text(titulo, weight=ft.FontWeight.W_500)] if titulo else []
        filas += [
            ft.ListTile(dense=True, title=ft.Text(s.concepto), subtitle=ft.Text(s.plataforma),
                        trailing=ft.Text(money(s.saldo)))
            for s in saldos
        ]
        total = sum(s.saldo for s in saldos)
        filas.append(ft.ListTile(dense=True, title=ft.Text("Total", weight=ft.FontWeight.BOLD),
                                 trailing=ft.Text(money(total), weight=ft.FontWeight.BOLD)))
        if not saldos:
            filas.append(ft.Text("Sin saldos.", italic=True))
        self.saldos_cierre.controls = filas

    def choose_close(self, e=None):  # propio
        """[Cerrar periodo]: ¿solo cerrar, o cerrar y abrir el siguiente?"""
        per = self.registro
        total = sum(s.saldo for s in closing_balances(per))

        def close_and_open(e):  # propio
            self.page.pop_dialog()
            self.start_close()

        def only_close(e):  # propio
            self.page.pop_dialog()
            try:
                close_only(per)
            except Exception as ex:  # noqa: BLE001
                notify(self.page, str(ex))
                return
            self.registro = Periodo.get(per.id)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Periodo cerrado")
            self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Cerrar «{per.nombre}»"),
            content=ft.Text(
                f"Cierra con {money(total)}.\n\n"
                "• Cerrar y abrir siguiente: el nuevo periodo abre con estos saldos.\n"
                "• Solo cerrar: queda en solo lectura y sale del acumulado global. "
                "Luego abres tú el que quieras con + y capturas sus saldos iniciales."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                ft.TextButton("Solo cerrar", on_click=only_close),
                ft.TextButton("Cerrar y abrir siguiente", on_click=close_and_open),
            ],
        ))

    def confirm_reopen(self, e=None):  # propio
        per = self.registro

        def reopen():  # propio
            try:
                reopen_period(per)
            except Exception as ex:  # noqa: BLE001
                notify(self.page, str(ex))
                return
            self.registro = Periodo.get(per.id)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Periodo reabierto")
            self.page.update()

        confirm(self.page, "Reabrir periodo",
                f"«{per.nombre}» se podrá editar otra vez y volverá a sumar en el "
                "acumulado global.", reopen)

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, per: Periodo, cantidad: int) -> str:  # propio
        mensaje = f"¿Seguro que deseas eliminar el periodo «{per.nombre}»?"
        if cantidad:
            mensaje += f"\n\nTambién se eliminarán sus {cantidad} movimiento(s)."
        if per.origen_id:
            mensaje += "\n\nEl periodo del que viene seguirá cerrado; puedes reabrirlo."
        return mensaje

    def confirm_delete(self, e=None):  # propio
        """Bote de la barra: elimina el periodo mostrado, con confirmación."""
        per = self.registro
        cantidad = Periodo.count_movements().get(per.id, 0)

        def delete():  # propio
            if self._delete(per):
                self.clear_form()
                self.page.navigate(routes.BASE)  # el periodo ya no existe: a la lista

        confirm(self.page, "Eliminar periodo", self._delete_message(per, cantidad), delete)

    def _delete(self, per: Periodo) -> bool:  # propio
        """Borra el periodo (y sus movimientos) y refresca la lista."""
        try:
            Periodo.delete(per.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Periodo eliminado")
        self.page.update()
        return True

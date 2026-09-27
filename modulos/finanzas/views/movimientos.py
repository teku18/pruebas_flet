"""
Pantallas de Movimientos (detalle de un periodo):
  /finanzas/movimientos -> resumen del periodo + lista de movimientos
  /finanzas/movimiento  -> un movimiento: nuevo, ver (solo lectura) o editar

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]

Concepto (modelo Inversion) y Plataforma salen de sus catálogos. La última
opción de cada desplegable es "+ Nuevo…": abre un diálogo, lo crea y lo deja
seleccionado (como el "Crear y editar…" de un Many2one en Odoo).

Arriba de la lista hay chips para filtrar por concepto: el resumen y la
lista muestran solo ese concepto (p. ej. cuánto llevas en "Casa").

Los traspasos se ven como UNA línea ("Nu → Finsus" entre plataformas,
"Vacaciones → Mio" entre conceptos) y se crean con la herramienta ⇄
(views/traspaso.py). Para corregir uno: se borra y se recrea.

Periodo cerrado = solo lectura: sin ➕, sin ⇄, sin editar ni borrar.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft

from core.ui import (
    MESES,
    DateField,
    add_button,
    confirm,
    delete_button,
    edit_button,
    icon_box,
    notify,
    short_date,
    swipe_to_delete,
)
from modulos.finanzas import routes
from modulos.finanzas.models import (
    TIPO_SELECTION,
    TIPOS_MANUALES,
    Inversion,
    Movimiento,
    Periodo,
    Plataforma,
)
from modulos.finanzas.services import money, period_summary
from modulos.finanzas.views.catalogos import catalog_dialog, labels

NUEVO = "__nuevo__"  # clave de la opción "+ Nueva…" en los desplegables

# Ícono y color de cada tipo (fijos a propósito: significan algo)
ESTILO_TIPO = {
    "saldo_inicial": (ft.Icons.FLAG, ft.Colors.BLUE_GREY),
    "deposito": (ft.Icons.SAVINGS, ft.Colors.GREEN),
    "rendimiento": (ft.Icons.TRENDING_UP, ft.Colors.TEAL),
    "retiro": (ft.Icons.ARROW_OUTWARD, ft.Colors.ORANGE),
    "traspaso": (ft.Icons.SWAP_HORIZ, ft.Colors.INDIGO),
}


def catalog_dropdown(page: ft.Page, modelo, etiqueta: str | None = None,  # propio
                     incluir_id: int | None = None) -> ft.Dropdown:
    """
    Dropdown de un catálogo con la opción "+ Nuevo…/Nueva…" al final.
    etiqueta: texto del campo; si no se da, el nombre del catálogo ("Concepto").
    Guarda en dd.data el último valor real elegido, para regresar a él
    si el usuario abre "+ Nueva…" y cancela.
    """
    t = labels(modelo)
    dd = ft.Dropdown(label=etiqueta or t.singular, expand=True)

    def fill_options(incluir=None):  # propio
        dd.options = [
            ft.DropdownOption(key=str(r.id), text=r.nombre)
            for r in modelo.search_for_dropdown(incluir)
        ] + [ft.DropdownOption(key=NUEVO, text=f"+ {t.nuevo} {t.singular.lower()}…")]

    def on_new_saved(registro):  # propio
        fill_options(registro.id)
        dd.value = dd.data = str(registro.id)
        dd.error_text = None
        page.update()

    def on_select(e):  # propio
        if dd.value == NUEVO:
            dd.value = dd.data  # regresa al valor anterior mientras se captura
            page.update()
            catalog_dialog(page, modelo, on_new_saved)
        else:
            dd.data = dd.value

    fill_options(incluir_id)
    dd.on_select = on_select
    return dd


def transfer_title(salida: Movimiento, entrada: Movimiento | None) -> tuple[str, str]:  # propio
    """
    Título y subtítulo de un traspaso según qué cambia:
      entre plataformas -> "Nu → Finsus"            · Reto ahorro
      entre conceptos   -> "Vacaciones → Mio"       · Nu
      ambos             -> "Mio · Nu → Reto · GBM"
    """
    if entrada is None:
        return f"{salida.plataforma_label} → ?", salida.inversion_label
    mismo_concepto = salida.inversion_id == entrada.inversion_id
    misma_plataforma = salida.plataforma_id == entrada.plataforma_id
    if mismo_concepto:
        return f"{salida.plataforma_label} → {entrada.plataforma_label}", salida.inversion_label
    if misma_plataforma:
        return f"{salida.inversion_label} → {entrada.inversion_label}", salida.plataforma_label
    return (f"{salida.inversion_label} · {salida.plataforma_label} → "
            f"{entrada.inversion_label} · {entrada.plataforma_label}", "")


class MovementsView:
    def __init__(self, page: ft.Page, on_show_period, on_transfer, on_reports):
        """
        on_show_period: engrane -> la pantalla de periodos muestra su detalle.
        on_transfer: ícono ⇄ -> abre la herramienta de traspaso.
        on_reports: ícono 📊 -> reportes de este periodo (y del concepto filtrado).
        """
        self.page = page
        self.on_show_period = on_show_period
        self.on_transfer = on_transfer
        self.on_reports = on_reports
        self.periodo: Periodo | None = None      # periodo abierto
        self.filtro_inversion: int | None = None # concepto elegido en los chips (None = todos)
        self.registro: Movimiento | None = None  # movimiento mostrado en el formulario
        self.modo = "nuevo"                      # "nuevo" | "ver" | "editar"

        self._build_form()
        self._build_list()

    # ==================================================================
    # Lista + resumen
    # ==================================================================
    def _build_list(self):  # propio
        self.lista = ft.ListView(expand=True, spacing=4, padding=ft.Padding.only(bottom=90))
        self.lbl_vacio = ft.Text("Este periodo aún no tiene movimientos", italic=True)
        self.lbl_titulo_lista = ft.Text("Movimientos")  # nombre del periodo
        self.resumen = ft.Container()
        self.fila_filtros = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        self.btn_traspaso = ft.IconButton(ft.Icons.SWAP_HORIZ, tooltip="Traspaso",
                                          on_click=lambda e: self.on_transfer())
        self.btn_nuevo = add_button("Nuevo movimiento", self.new)
        self.aviso_cerrado = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=8,
            bgcolor=ft.Colors.SECONDARY_CONTAINER,
            content=ft.Row(spacing=6, controls=[
                ft.Icon(ft.Icons.LOCK, size=16),
                ft.Text("Periodo cerrado: solo lectura. Se reabre desde ⚙.", size=12),
            ]),
        )

        self.vista_lista = ft.View(
            route=routes.MOVIMIENTOS,
            appbar=ft.AppBar(
                title=self.lbl_titulo_lista,
                actions=[
                    ft.IconButton(ft.Icons.INSIGHTS, tooltip="Reportes del periodo",
                                  on_click=lambda e: self.on_reports(
                                      self.periodo, self.filtro_inversion)),
                    self.btn_traspaso,
                    ft.IconButton(ft.Icons.SETTINGS, tooltip="Datos del periodo",
                                  on_click=lambda e: self.on_show_period(self.periodo)),
                ],
            ),
            floating_action_button=self.btn_nuevo,
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(
                        expand=True,
                        controls=[self.aviso_cerrado, self.resumen, self.fila_filtros,
                                  self.lbl_vacio, self.lista],
                    ),
                )
            ],
        )

    def open_period(self, periodo: Periodo):  # propio
        """Lo llama la pantalla de Periodos al tocar una línea."""
        self.periodo = periodo
        self.filtro_inversion = None  # cada periodo abre con "Todos"
        self.page.navigate(routes.MOVIMIENTOS)

    def load(self):  # propio
        # Se relee el periodo por si se editó (nombre o fechas) desde su detalle
        self.periodo = Periodo.get(self.periodo.id)
        if self.periodo is None:  # se eliminó
            return
        cerrado = self.periodo.cerrado
        self.lbl_titulo_lista.value = self.periodo.nombre
        self.aviso_cerrado.visible = cerrado
        self.btn_nuevo.visible = self.btn_traspaso.visible = not cerrado
        self.resumen.content = self._summary_card()

        todos = Movimiento.search_by_period(self.periodo.id)
        self._build_filters(todos)
        en_vista = lambda m: self.filtro_inversion in (None, m.inversion_id)  # noqa: E731
        # Un traspaso = una sola línea (la salida, con su entrada al lado).
        # Con filtro se muestra si CUALQUIERA de sus mitades es del concepto.
        pareja = {}
        for m in todos:
            if m.traspaso_grupo:
                pareja.setdefault(m.traspaso_grupo, {})[m.tipo] = m
        lineas = []
        for m in todos:
            if m.tipo == "traspaso_entrada" and m.traspaso_grupo:
                continue  # va junto con su salida
            if m.es_traspaso:
                entrada = pareja[m.traspaso_grupo].get("traspaso_entrada")
                if en_vista(m) or (entrada and en_vista(entrada)):
                    lineas.append(self._row(m, entrada, en_vista))
            elif en_vista(m):
                lineas.append(self._row(m, None, en_vista))
        self.lista.controls = lineas
        self.lbl_vacio.visible = not lineas

    def _build_filters(self, movimientos: list[Movimiento]):  # propio
        """Chips [Todos] [Casa] [Reto Ahorro]… con los conceptos que hay en el periodo."""
        conceptos = {m.inversion_id: m.inversion_label for m in movimientos}
        if self.filtro_inversion not in conceptos:
            self.filtro_inversion = None  # el concepto elegido ya no está en el periodo
        opciones = [(None, "Todos")] + sorted(conceptos.items(), key=lambda c: c[1])
        self.fila_filtros.controls = [
            ft.Chip(
                label=ft.Text(nombre),
                selected=self.filtro_inversion == clave,
                on_select=lambda e, c=clave: self.set_filter(c),
            )
            for clave, nombre in opciones
        ]
        self.fila_filtros.visible = len(conceptos) > 1  # con un solo concepto no hace falta

    def set_filter(self, inversion_id: int | None):  # propio
        self.filtro_inversion = inversion_id
        self.load()
        self.page.update()

    def _summary_card(self) -> ft.Control:  # propio
        """Abre con · ingresos · gastos · cierra con."""
        r = period_summary(self.periodo, self.filtro_inversion)

        def dato(titulo, valor, color=None):  # propio
            return ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    ft.Text(titulo, size=11, color=ft.Colors.OUTLINE),
                    ft.Text(valor, size=14, weight=ft.FontWeight.W_500, color=color),
                ],
            )

        return ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row([dato("Abre con", money(r.saldo_apertura)),
                            dato("Cierra con", money(r.saldo_cierre))]),
                    ft.Row([dato("Ingresos", money(r.ingresos, signo=True), ft.Colors.GREEN),
                            dato("Gastos", money(-r.gastos), ft.Colors.ORANGE),
                            dato("Neto", money(r.neto, signo=True))]),
                ],
            ),
        )

    def _row(self, m: Movimiento, pareja: Movimiento | None, en_vista) -> ft.Control:  # propio
        """Una línea: fecha, ícono, plataforma(s), tipo y monto con signo."""
        if m.es_traspaso:
            icono, color = ESTILO_TIPO["traspaso"]
            titulo, subtitulo = transfer_title(m, pareja)
            tipo_texto, monto_texto = "traspaso", money(m.monto)
            # Con filtro, si solo una mitad es del concepto, para él sí entra/sale dinero
            if pareja and en_vista(m) != en_vista(pareja):
                monto_texto = money(m.monto if en_vista(pareja) else -m.monto, signo=True)
            al_tocar = lambda e, mov=m, t=titulo: self._transfer_dialog(mov, t)  # noqa: E731
        else:
            icono, color = ESTILO_TIPO.get(m.tipo, (ft.Icons.RECEIPT_LONG, ft.Colors.GREY))
            titulo, subtitulo = m.plataforma_label, m.inversion_label
            tipo_texto, monto_texto = m.tipo_label.lower(), money(m.monto_con_signo, signo=True)
            al_tocar = lambda e, mov=m: self.show(mov)  # noqa: E731

        if m.comentarios:
            subtitulo = " · ".join(filter(None, [subtitulo, m.comentarios]))

        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,
            on_click=al_tocar,
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Column(
                        width=36,
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(MESES[m.fecha.month - 1], size=12),
                            ft.Text(str(m.fecha.day), size=16),
                        ],
                    ),
                    icon_box(icono, color),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(titulo, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(subtitulo, size=12, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Text(tipo_texto, size=12, color=color),
                            ft.Text(monto_texto, size=15, color=color),
                        ],
                    ),
                ],
            ),
        )
        if self.periodo.cerrado:
            return linea  # solo lectura: sin deslizar para borrar
        return swipe_to_delete(
            self.page,
            key=f"movimiento-{m.id}",
            contenido=linea,
            titulo="Eliminar traspaso" if m.es_traspaso else "Eliminar movimiento",
            mensaje=self._delete_message(m),
            on_delete=lambda mov=m: self._delete(mov),
        )

    def _transfer_dialog(self, mov: Movimiento, titulo: str):  # propio
        """Tocar un traspaso: su detalle, con opción de eliminarlo (las dos mitades)."""
        def delete(e):  # propio
            self.page.pop_dialog()
            self._delete(mov)

        cerrado = self.periodo.cerrado
        texto = f"{money(mov.monto)} · {short_date(mov.fecha)}\n{mov.inversion_label}"
        if mov.comentarios:
            texto += f"\n{mov.comentarios}"
        if not cerrado:
            texto += "\n\nPara corregirlo, elimínalo y regístralo de nuevo."
        acciones = [ft.TextButton("Cerrar", on_click=lambda e: self.page.pop_dialog())]
        if not cerrado:
            acciones.append(ft.TextButton("Eliminar", style=ft.ButtonStyle(color=ft.Colors.RED),
                                          on_click=delete))
        self.page.show_dialog(
            ft.AlertDialog(title=ft.Text(f"Traspaso {titulo}"), content=ft.Text(texto),
                           actions=acciones)
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _build_form(self):  # propio
        # Filas que contienen los desplegables (se rellenan en _new_dropdowns)
        self.fila_inversion = ft.Row()
        self.fila_plataforma = ft.Row()
        self.fila_tipo = ft.Row()
        self._new_dropdowns()

        self.txt_monto = ft.TextField(
            label="Monto",
            prefix="$ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
        )
        self.campo_fecha = DateField(self.page, "Fecha")
        self.txt_comentarios = ft.TextField(label="Comentarios", max_length=255)

        self.lbl_titulo_form = ft.Text("Nuevo movimiento")
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        self.btn_barra_editar = edit_button(self.edit)
        self.btn_barra_eliminar = delete_button(self.confirm_delete)

        self.vista_form = ft.View(
            route=routes.MOVIMIENTO,
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
                            self.fila_tipo,
                            self.fila_inversion,
                            self.txt_monto,
                            self.fila_plataforma,
                            self.campo_fecha.fila,
                            self.txt_comentarios,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._apply_mode()

    def _new_dropdowns(self, mov: Movimiento | None = None):  # propio
        """
        Crea los Dropdown desde cero (un Dropdown nuevo siempre se ve vacío;
        regresarle value=None no borra el texto mostrado en Flet).
        Si se pasa un movimiento, incluye su plataforma/concepto aunque esté archivado.
        """
        self.dd_inversion = catalog_dropdown(
            self.page, Inversion, incluir_id=mov.inversion_id if mov else None
        )
        self.dd_plataforma = catalog_dropdown(
            self.page, Plataforma, incluir_id=mov.plataforma_id if mov else None
        )
        self.dd_tipo = ft.Dropdown(
            label="Tipo",
            expand=True,
            options=[ft.DropdownOption(key=t, text=TIPO_SELECTION[t]) for t in TIPOS_MANUALES],
        )
        self.fila_inversion.controls = [self.dd_inversion]
        self.fila_plataforma.controls = [self.dd_plataforma]
        self.fila_tipo.controls = [self.dd_tipo]

    def _apply_mode(self):  # propio
        lectura = self.modo == "ver"

        for dd in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            dd.disabled = lectura
        for txt in (self.txt_monto, self.txt_comentarios):
            txt.read_only = lectura
        self.campo_fecha.set_enabled(not lectura)

        # En un periodo cerrado no se edita ni se borra
        editable = lectura and not (self.periodo and self.periodo.cerrado)
        self.btn_barra_editar.visible = editable
        self.btn_barra_eliminar.visible = editable
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo movimiento"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Movimiento"
        else:
            self.lbl_titulo_form.value = "Editar movimiento"
            self.btn_guardar.content = "Actualizar"

    def _default_date(self) -> date:  # propio
        """Hoy, pero ajustado para que quede dentro del periodo abierto."""
        hoy = date.today()
        if self.periodo is None:
            return hoy
        return min(max(hoy, self.periodo.fecha_inicio), self.periodo.fecha_fin)

    def _fill(self, mov: Movimiento):  # propio
        """Pasa los datos del registro a los campos."""
        self._new_dropdowns(mov)
        self.dd_inversion.value = self.dd_inversion.data = str(mov.inversion_id)
        self.dd_plataforma.value = self.dd_plataforma.data = str(mov.plataforma_id)
        self.dd_tipo.value = mov.tipo
        self.txt_monto.value = f"{mov.monto:.2f}"
        self.txt_comentarios.value = mov.comentarios or ""
        self.campo_fecha.set_value(mov.fecha)

    def clear_errors(self):  # propio
        for campo in (self.dd_inversion, self.txt_monto, self.dd_plataforma,
                      self.dd_tipo, self.campo_fecha.txt):
            campo.error_text = None

    def clear_form(self):  # propio
        self._new_dropdowns()
        self.clear_errors()
        self.txt_monto.value = ""
        self.txt_comentarios.value = ""
        self.campo_fecha.set_value(self._default_date())
        self.registro = None
        self.modo = "nuevo"
        self._apply_mode()

    def _prepare_calendar(self):  # propio
        self.campo_fecha.set_range(self.periodo.fecha_inicio, self.periodo.fecha_fin)

    # --- Acciones -------------------------------------------------------
    def new(self, e=None):  # propio
        self.clear_form()
        self._prepare_calendar()
        self.page.navigate(routes.MOVIMIENTO)

    def show(self, mov: Movimiento):  # propio
        """Tocar una línea: muestra el movimiento en solo lectura."""
        self.registro = Movimiento.get(mov.id)
        self._fill(self.registro)
        self.clear_errors()
        self._prepare_calendar()
        self.modo = "ver"
        self._apply_mode()
        self.page.navigate(routes.MOVIMIENTO)

    def edit(self, e=None):  # propio
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            self.registro = Movimiento.get(self.registro.id)
            self._fill(self.registro)
            self.clear_errors()
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.clear_form()
            self.page.navigate(routes.MOVIMIENTOS)

    def save(self, e=None):  # propio
        self.clear_errors()
        faltantes = False
        for campo in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            if not campo.value or campo.value == NUEVO:
                campo.error_text = "Requerido"
                faltantes = True
        try:
            monto = float(self.txt_monto.value)
            if monto <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.txt_monto.error_text = "Monto inválido"
            faltantes = True

        periodo = self.periodo
        if not (periodo.fecha_inicio <= self.campo_fecha.valor <= periodo.fecha_fin):
            self.campo_fecha.txt.error_text = (
                f"Debe estar entre {short_date(periodo.fecha_inicio)} "
                f"y {short_date(periodo.fecha_fin)}"
            )
            faltantes = True

        if faltantes:
            self.page.update()
            return

        valores = dict(
            inversion_id=int(self.dd_inversion.value),
            plataforma_id=int(self.dd_plataforma.value),
            monto=monto,
            fecha=self.campo_fecha.valor,
            tipo=self.dd_tipo.value,
            comentarios=(self.txt_comentarios.value or "").strip() or None,
            periodo_id=periodo.id,
        )
        try:
            if self.modo == "nuevo":
                Movimiento.create(**valores)
            else:
                self.registro = Movimiento.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.clear_form()
            notify(self.page, "Movimiento guardado")
            self.page.navigate(routes.MOVIMIENTOS)
        else:
            self.registro = Movimiento.get(self.registro.id)  # con sus catálogos cargados
            self._fill(self.registro)
            self.modo = "ver"
            self._apply_mode()
            notify(self.page, "Movimiento actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _delete_message(self, mov: Movimiento) -> str:  # propio
        if mov.es_traspaso:
            return (f"¿Eliminar el traspaso de {money(mov.monto)} del "
                    f"{short_date(mov.fecha)}? Se borran la salida y la entrada.")
        return (
            f"¿Seguro que deseas eliminar el {mov.tipo_label.lower()} de "
            f"{money(mov.monto)} en {mov.plataforma_label} ({short_date(mov.fecha)})?"
        )

    def confirm_delete(self, e=None):  # propio
        mov = self.registro

        def delete():  # propio
            if self._delete(mov):
                self.clear_form()
                self.page.navigate(routes.MOVIMIENTOS)

        confirm(self.page, "Eliminar movimiento", self._delete_message(mov), delete)

    def _delete(self, mov: Movimiento) -> bool:  # propio
        try:
            Movimiento.delete(mov.id)  # si es traspaso, borra también su pareja
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
            return False
        self.load()
        notify(self.page, "Traspaso eliminado" if mov.es_traspaso else "Movimiento eliminado")
        self.page.update()
        return True

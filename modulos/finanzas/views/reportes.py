"""
Reportes de Finanzas (/finanzas/reportes), desde el ícono 📊 de la lista de periodos.

  1. Total del concepto al cierre, con su meta y cuánto falta
  2. ¿Dónde está el dinero?  -> pastel + tabla por plataforma (monto y %)
  3. Ahorro mensual          -> línea del acumulado + tabla mes a mes

Se filtra por periodo (desplegable) y por concepto (chips), igual que en tu Excel:
primero el concepto, después cómo se reparte entre plataformas.

Colores (guía de visualización, en colores.py):
  - Cada plataforma tiene SIEMPRE el mismo color (se asigna por su id, no por
    su tamaño), así "Nu" no cambia de color al cambiar de filtro.
  - El pastel muestra TODAS las plataformas (sin agrupar en "Otras").

Exportar (⬇ en la barra): el periodo y concepto que estás viendo, a Excel,
con las mismas gráficas (exportador.py).
"""
import math

import flet as ft
import flet_charts as fch

from core.ui import MESES, notify
from modulos.finanzas import routes
from modulos.finanzas.colores import (
    AZUL,
    GRIS_OTRAS,
    PALETA_CLARO,
    PALETA_OSCURO,
    platform_colors,
)
from modulos.finanzas.exportador import export_file_name, export_period
from modulos.finanzas.models import Inversion, Movimiento, Periodo
from modulos.finanzas.services import (
    distribution_by_platform,
    money,
    monthly_savings,
    period_summary,
)


def short_money(valor: float) -> str:  # propio
    """93568 -> '$94k', 850 -> '$850' (para ejes y cuadros chicos)."""
    signo = "-" if valor < 0 else ""
    if abs(valor) >= 1000:
        return f"{signo}${abs(valor) / 1000:,.0f}k"
    return f"{signo}${abs(valor):,.0f}"


def nice_step(rango: float, partes: int = 4) -> float:  # propio
    """Paso "redondo" para el eje: 1, 2, 2.5 o 5 × 10^n (p. ej. 25,000: $0, $25k, $50k…)."""
    crudo = max(rango / partes, 1)
    potencia = 10 ** math.floor(math.log10(crudo))
    for factor in (1, 2, 2.5, 5, 10):
        if crudo <= factor * potencia:
            return factor * potencia
    return 10 * potencia


class ReportsView:
    def __init__(self, page: ft.Page):
        self.page = page
        self.periodo_id: int | None = None
        self.inversion_id: int | None = None
        # True = abierto desde un periodo: se queda en ese periodo (sin selector)
        self.fijo = False
        self.picker = ft.FilePicker()  # para "Guardar como…" del Excel

        self.dd_periodo = ft.Dropdown(label="Periodo", expand=True, on_select=self._on_period)
        self.fila_periodo = ft.Row([self.dd_periodo])
        self.fila_filtros = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        # STRETCH: las tarjetas ocupan todo el ancho
        self.contenido = ft.Column(spacing=16,
                                   horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        self.vista = ft.View(
            route=routes.REPORTES,
            appbar=ft.AppBar(
                title=ft.Text("Reportes"),
                actions=[
                    # ⬇ Excel del periodo (y concepto) que estás viendo, con gráficas
                    ft.IconButton(ft.Icons.DOWNLOAD, tooltip="Exportar a Excel",
                                  on_click=self.export_excel),
                ],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=12,
                        controls=[self.fila_periodo, self.fila_filtros, self.contenido],
                    )
                )
            ],
        )

    # ==================================================================
    # Carga y filtros
    # ==================================================================
    def open_general(self):  # propio
        """Desde la lista de periodos: se puede elegir cualquier periodo."""
        self.fijo = False
        self.page.navigate(routes.REPORTES)

    def open_for_period(self, periodo: Periodo, inversion_id: int | None = None):  # propio
        """Desde dentro de un periodo: solo ese periodo, con el concepto que ya filtrabas."""
        self.fijo = True
        self.periodo_id = periodo.id
        self.inversion_id = inversion_id
        self.page.navigate(routes.MOVIMIENTOS_REPORTES)

    def load(self):  # propio
        # Fijo: sin selector de periodo (el nombre ya sale en la tarjeta del total)
        self.fila_periodo.visible = not self.fijo
        self.vista.route = routes.MOVIMIENTOS_REPORTES if self.fijo else routes.REPORTES
        periodos = Periodo.search_all()  # del más reciente al más antiguo
        self.dd_periodo.options = [ft.DropdownOption(key=str(p.id), text=p.nombre)
                                   for p in periodos]
        if not periodos:
            self.contenido.controls = [ft.Text("Aún no hay periodos.", italic=True)]
            self.fila_filtros.controls = []
            return
        if self.periodo_id not in {p.id for p in periodos}:
            self.periodo_id = periodos[0].id
        self.dd_periodo.value = str(self.periodo_id)
        self._build_filters()
        self._build_content()

    def _on_period(self, e):  # propio
        self.periodo_id = int(self.dd_periodo.value)
        self.load()
        self.page.update()

    def _build_filters(self):  # propio
        # Solo los conceptos que tiene el periodo (Inversiones no muestra "Renta")
        usados = {m.inversion_id for m in Movimiento.search_by_period(self.periodo_id)}
        conceptos = [i for i in Inversion.search_all() if i.id in usados]
        if self.inversion_id not in {c.id for c in conceptos}:
            self.inversion_id = None
        opciones = [(None, "Todos")] + [(c.id, c.nombre) for c in conceptos]
        self.fila_filtros.controls = [
            ft.Chip(
                label=ft.Text(nombre),
                selected=self.inversion_id == clave,
                on_select=lambda e, c=clave: self.set_concept(c),
            )
            for clave, nombre in opciones
        ]

    # ==================================================================
    # Exportar a Excel
    # ==================================================================
    async def export_excel(self, e=None):  # propio
        """
        Excel del periodo y concepto que estás viendo: hoja de movimientos
        (se puede reimportar) + hoja "Reporte" con el pastel y la línea.
        El archivo se arma en memoria y Flet lo escribe donde elijas.
        """
        if self.periodo_id is None:
            return
        periodo = Periodo.get(self.periodo_id)
        concepto = Inversion.get(self.inversion_id) if self.inversion_id else None
        try:
            contenido = export_period(periodo, self.inversion_id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo generar el Excel: {ex}")
            return
        ruta = await self.picker.save_file(
            dialog_title="Guardar reporte en Excel",
            file_name=export_file_name(periodo, concepto),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
            src_bytes=contenido,  # Flet escribe el archivo (escritorio, web y celular)
        )
        if ruta or self.page.web:  # en web se descarga directo, sin ruta
            notify(self.page, "Excel exportado")

    def set_concept(self, inversion_id: int | None):  # propio
        self.inversion_id = inversion_id
        self._build_filters()
        self._build_content()
        self.page.update()

    # ==================================================================
    # Secciones
    # ==================================================================
    def _build_content(self):  # propio
        periodo = Periodo.get(self.periodo_id)
        concepto = Inversion.get(self.inversion_id) if self.inversion_id else None
        self.contenido.controls = [
            self._total_card(periodo, concepto),
            self._distribution_section(periodo),
            self._monthly_section(periodo),
        ]

    def _card(self, titulo: str, subtitulo: str, *controles, on_click=None) -> ft.Control:  # propio
        """Sección con fondo. on_click: tocar cualquier parte que no sea la gráfica."""
        return ft.Container(
            on_click=on_click,
            padding=14,
            border_radius=12,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Column(spacing=0, controls=[
                        ft.Text(titulo, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(subtitulo, size=12, color=ft.Colors.OUTLINE),
                    ]),
                    *controles,
                ],
            ),
        )

    # --- 1. Total y meta --------------------------------------------------
    def _total_card(self, periodo: Periodo, concepto: Inversion | None) -> ft.Control:  # propio
        r = period_summary(periodo, self.inversion_id)
        nombre = concepto.nombre if concepto else "Todos los conceptos"
        controles = [ft.Text(money(r.saldo_cierre), size=28, weight=ft.FontWeight.BOLD)]
        if concepto and concepto.meta:
            falta = max(concepto.meta - r.saldo_cierre, 0)
            avance = min(r.saldo_cierre / concepto.meta, 1) if concepto.meta else 0
            controles += [
                ft.ProgressBar(value=avance, bar_height=8, border_radius=4),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(f"Meta {money(concepto.meta)}", size=13),
                        ft.Text("¡Meta cumplida!" if falta == 0 else f"Falta {money(falta)}",
                                size=13, weight=ft.FontWeight.W_500),
                    ],
                ),
                ft.Text(f"{avance * 100:.1f}% de la meta", size=12, color=ft.Colors.OUTLINE),
            ]
        elif concepto:
            controles.append(ft.Text("Tip: ponle una meta en Ajustes → Conceptos.",
                                     size=12, color=ft.Colors.OUTLINE))
        return self._card(nombre, f"Total al cierre de {periodo.nombre}", *controles)

    # --- 2. Distribución por plataforma -----------------------------------
    def _palette(self) -> list[str]:  # propio
        oscuro = self.page.theme_mode == ft.ThemeMode.DARK or (
            self.page.theme_mode == ft.ThemeMode.SYSTEM
            and self.page.platform_brightness == ft.Brightness.DARK
        )
        return PALETA_OSCURO if oscuro else PALETA_CLARO

    def _platform_colors(self) -> dict[int, str]:  # propio
        """Color fijo por plataforma (ver colores.py), con la paleta del modo actual."""
        return platform_colors(self._palette())

    def _distribution_section(self, periodo: Periodo) -> ft.Control:  # propio
        reparto = distribution_by_platform(periodo, self.inversion_id)
        if not reparto:
            return self._card("¿Dónde está el dinero?", "Sin saldo en plataformas",
                              ft.Text("No hay datos para este filtro.", italic=True))
        colores = self._platform_colors()
        total = sum(p.monto for p in reparto)

        # Pastel: TODAS las plataformas, de la más grande a la más chica
        orden = sorted(reparto, key=lambda p: p.monto, reverse=True)
        secciones = [
            fch.PieChartSection(
                value=p.monto, color=colores.get(p.plataforma_id, GRIS_OTRAS), radius=70,
                # % con 2 decimales, por FUERA de la rebanada (1.0 = borde exterior)
                # para que quepa aunque la rebanada sea delgada
                title=f"{p.porcentaje:.2f}%",
                title_position=1.32,
                title_style=ft.TextStyle(size=11, color=ft.Colors.ON_SURFACE,
                                         weight=ft.FontWeight.BOLD),
            )
            for p in orden
        ]
        pastel = fch.PieChart(sections=secciones, sections_space=2,
                              center_space_radius=40, height=300)

        # Tarjeta que aparece al tocar una rebanada (como el tooltip de la línea):
        # nombre, monto y % de la plataforma. Fondo blanco, texto negro.
        lbl_nombre = ft.Text(size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK)
        lbl_monto = ft.Text(size=13, color=ft.Colors.BLACK)
        lbl_pct = ft.Text(size=12, color="#52514e")
        punto = ft.Container(width=10, height=10, border_radius=5)
        tarjeta = ft.Container(
            visible=False,
            top=0,
            left=0,
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=8,
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK)),
            content=ft.Column(spacing=2, tight=True, controls=[
                ft.Row([punto, lbl_nombre], spacing=6, tight=True),
                lbl_monto,
                lbl_pct,
            ]),
        )

        def select(indice: int | None):  # propio
            """Resalta la rebanada tocada (más grande) y muestra su tarjeta."""
            for i, seccion in enumerate(secciones):
                seccion.radius = 80 if i == indice else 70
            if indice is None:
                tarjeta.visible = False
            else:
                p = orden[indice]
                punto.bgcolor = colores.get(p.plataforma_id, GRIS_OTRAS)
                lbl_nombre.value = p.nombre
                lbl_monto.value = money(p.monto)
                lbl_pct.value = f"{p.porcentaje:.2f}% del total"
                tarjeta.visible = True
            zona.update()

        def on_pie_event(e):  # propio
            # section_index: la rebanada bajo el dedo (-1 o None = fuera de las rebanadas).
            # La tarjeta se queda hasta tocar otra rebanada o fuera del pastel.
            if e.section_index is not None and e.section_index >= 0:
                select(e.section_index)
            elif e.type in (fch.ChartEventType.TAP_UP, fch.ChartEventType.TAP_DOWN):
                select(None)

        pastel.on_event = on_pie_event
        # Stack: la tarjeta flota encima del pastel (esquina superior izquierda)
        zona = ft.Stack(height=300, controls=[pastel, tarjeta])

        # Tabla: todas, de menor a mayor (como tu Excel), con su color
        def fila(color, nombre, monto, pct, negrita=False):  # propio
            peso = ft.FontWeight.BOLD if negrita else None
            return ft.Row(controls=[
                ft.Container(width=12, height=12, border_radius=3, bgcolor=color),
                ft.Text(nombre, expand=True, weight=peso),
                ft.Text(money(monto), width=120, text_align=ft.TextAlign.RIGHT, weight=peso),
                ft.Text(f"{pct:.2f}%", width=72, text_align=ft.TextAlign.RIGHT, weight=peso,
                        no_wrap=True),
            ])

        tabla = ft.Column(spacing=6, controls=[
            ft.Row(controls=[
                ft.Container(width=12),
                ft.Text("Plataforma", expand=True, size=12, color=ft.Colors.OUTLINE),
                ft.Text("Monto", width=120, text_align=ft.TextAlign.RIGHT, size=12,
                        color=ft.Colors.OUTLINE),
                ft.Text("%", width=72, text_align=ft.TextAlign.RIGHT, size=12,
                        color=ft.Colors.OUTLINE),
            ]),
            # Tocar una fila de la tabla también resalta su rebanada
            *[ft.Container(
                content=fila(colores[p.plataforma_id], p.nombre, p.monto, p.porcentaje),
                ink=True,
                on_click=lambda e, i=orden.index(p): select(i),
            ) for p in reparto],
            ft.Divider(height=1),
            fila(ft.Colors.TRANSPARENT, "Total", total, 100, True),
        ])
        tarjeta.on_click = lambda e: select(None)  # tocar la tarjeta también la cierra
        return self._card("¿Dónde está el dinero?",
                          "Reparto por plataforma al cierre · toca una rebanada",
                          zona, tabla, on_click=lambda e: select(None))

    # --- 3. Ahorro mensual ------------------------------------------------
    def _monthly_section(self, periodo: Periodo) -> ft.Control:  # propio
        meses = monthly_savings(periodo, self.inversion_id)
        if not meses:
            return self._card("Ahorro mensual", "Sin movimientos en el periodo",
                              ft.Text("No hay datos para este filtro.", italic=True))
        encabezado, zona, select = self._cumulative_chart(meses)
        return self._card("Ahorro mensual",
                          "Depósitos + rendimientos − retiros (sin saldo inicial ni traspasos)",
                          encabezado, zona, self._monthly_table(meses, select),
                          on_click=lambda e: select(None))

    def _cumulative_chart(self, meses):  # propio
        """
        Línea del acumulado del periodo, con eje de 25 en 25 ($0, $25k, $50k…).
        Al tocar un punto aparece una tarjeta fija (mes, lo del mes y acumulado)
        que se queda hasta tocar otro punto o fuera de la gráfica.
        Regresa (texto de encabezado, zona con la gráfica, select(índice | None)).
        """
        acumulados = [m.acumulado for m in meses]
        lo, hi, paso = self._axis_range(acumulados)
        normal = fch.ChartCirclePoint(radius=4, color=AZUL)
        resaltado = fch.ChartCirclePoint(radius=7, color=AZUL, stroke_color=ft.Colors.WHITE,
                                         stroke_width=2)
        puntos = [
            fch.LineChartDataPoint(x=i, y=m.acumulado, point=normal,
                                   show_tooltip=False)  # usamos nuestra tarjeta, no la de Flet
            for i, m in enumerate(meses)
        ]
        linea = fch.LineChart(
            height=240,
            min_y=lo,
            max_y=hi,
            min_x=0,
            max_x=len(meses) - 1,
            data_series=[fch.LineChartData(
                points=puntos,
                color=AZUL,
                stroke_width=2,
                below_line_bgcolor=ft.Colors.with_opacity(0.18, AZUL),
            )],
            left_axis=self._left_axis(lo, hi, paso),
            bottom_axis=self._bottom_axis(meses),
            horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.OUTLINE_VARIANT,
                                                     interval=paso),
        )

        # Tarjeta fija (fondo blanco, texto negro):
        #   jun 2026 / Mes +$5,996.92 / Acumulado $50,846.46
        lbl_mes = ft.Text(size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK)
        lbl_mes_neto = ft.Text(size=12, color=ft.Colors.BLACK)
        lbl_acum = ft.Text(size=12, color=ft.Colors.BLACK)
        tarjeta = ft.Container(
            visible=False, top=0, left=50,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=6,
            bgcolor=ft.Colors.WHITE,
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK)),
            content=ft.Column(spacing=2, tight=True, controls=[lbl_mes, lbl_mes_neto, lbl_acum]),
        )

        def select(indice: int | None):  # propio
            for i, punto in enumerate(puntos):
                punto.point = resaltado if i == indice else normal
            if indice is None:
                tarjeta.visible = False
            else:
                m = meses[indice]
                lbl_mes.value = f"{MESES[m.mes - 1]} {m.año}"
                lbl_mes_neto.value = f"Mes {money(m.neto, signo=True)}"
                lbl_acum.value = f"Acumulado {money(m.acumulado)}"
                tarjeta.visible = True
            zona.update()

        def on_line_event(e):  # propio
            # Mientras el dedo toca, Flet manda el punto más cercano (spots).
            # Al soltar llega sin puntos: NO se oculta, así la tarjeta se queda.
            if e.spots:
                select(e.spots[0].spot_index)

        linea.on_event = on_line_event
        tarjeta.on_click = lambda e: select(None)
        zona = ft.Stack(height=240, controls=[linea, tarjeta])
        encabezado = ft.Text(f"Acumulado: {money(acumulados[-1])}",
                             size=12, color=ft.Colors.OUTLINE)
        return encabezado, zona, select

    def _bottom_axis(self, meses) -> fch.ChartAxis:  # propio
        return fch.ChartAxis(
            label_size=24,
            labels=[fch.ChartAxisLabel(value=i, label=ft.Text(MESES[m.mes - 1], size=10))
                    for i, m in enumerate(meses)],
        )

    def _axis_range(self, valores: list[float]) -> tuple[float, float, float]:  # propio
        """(mínimo, máximo, paso) redondos, incluyendo el cero."""
        bajo, alto = min(0, min(valores)), max(0, max(valores))
        paso = nice_step(alto - bajo)
        return math.floor(bajo / paso) * paso, math.ceil(alto / paso) * paso or paso, paso

    def _left_axis(self, minimo: float, maximo: float, paso: float) -> fch.ChartAxis:  # propio
        """Etiquetas en múltiplos del paso: $0, $10k, $20k…"""
        valores, v = [], minimo
        while v <= maximo + paso / 2:
            valores.append(v)
            v += paso
        return fch.ChartAxis(
            label_size=44,
            label_spacing=paso,  # sin esto, Flet solo dibuja la primera y la última
            labels=[fch.ChartAxisLabel(value=v, label=ft.Text(short_money(v), size=10))
                    for v in valores],
        )

    def _monthly_table(self, meses, select) -> ft.Control:  # propio
        """
        La tabla que acompaña a la gráfica. Tocar un mes resalta su punto y
        muestra su tarjeta, igual que tocar el punto (como la tabla del pastel).
        """
        def fila(a, b, c, encabezado=False):  # propio
            estilo = dict(size=12, color=ft.Colors.OUTLINE) if encabezado else {}
            return ft.Row(controls=[
                ft.Text(a, expand=True, **estilo),
                ft.Text(b, width=110, text_align=ft.TextAlign.RIGHT, **estilo),
                ft.Text(c, width=110, text_align=ft.TextAlign.RIGHT, **estilo),
            ])

        return ft.Column(spacing=4, controls=[
            fila("Mes", "Del mes", "Acumulado", True),
            *[ft.Container(
                content=fila(f"{MESES[m.mes - 1]} {m.año}", money(m.neto, signo=True),
                             money(m.acumulado)),
                ink=True,
                on_click=lambda e, i=i: select(i),
            ) for i, m in enumerate(meses)],
        ])

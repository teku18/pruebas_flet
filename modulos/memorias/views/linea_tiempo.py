"""
Pantalla principal de Memorias (/memorias):

  [🔍 Buscar en tus memorias…            ] [⚙ filtros (2)]
  (📜 Línea de tiempo) (🖼 Galería)
  ┌ ✨ Un día como hoy ───────────────────┐   <- solo si hay (y sin filtros)
  │ [▢] Cine en nuestro aniversario       │
  │     Hace 3 años · 🥰                  │
  └───────────────────────────────────────┘
  2026
    octubre
      14  🥰 Salí de la empresa X        [▢]
     oct  📍 CDMX · (Logro)
          Por fin…

  Galería: todas las fotos en cuadrícula (3 por fila); tocar abre su memoria.

Filtros (⚙): etiquetas (cualquiera de las elegidas) y rango de fechas.
Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date

import flet as ft

from core.ui import add_button
from modulos.memorias import routes, services
from modulos.memorias.models import EtiquetaMemoria, Memoria
from modulos.memorias.views.comun import tag_chip, thumb


class MemoriesView:
    def __init__(self, page: ft.Page, on_open, on_new):
        self.page = page
        self.on_open = on_open
        self.filtros = services.Filtros()
        self.pestana = "linea"  # "linea" | "galeria"

        self.txt_buscar = ft.TextField(
            hint_text="Buscar en tus memorias…", prefix_icon=ft.Icons.SEARCH, dense=True,
            border_radius=24, expand=True, on_change=self._on_search,
        )
        self.btn_filtros = ft.IconButton(ft.Icons.TUNE, tooltip="Filtros",
                                         on_click=self.open_filters)
        self.fila_pestanas = ft.Row(spacing=6)
        self.lbl_filtros = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.cuerpo = ft.ListView(expand=True, spacing=8, padding=ft.Padding.only(bottom=90))
        self.vista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(title=ft.Text("Memorias")),
            floating_action_button=add_button("Nueva memoria", lambda e: on_new()),
            controls=[ft.SafeArea(expand=True, content=ft.Column(expand=True, spacing=8, controls=[
                ft.Row([self.txt_buscar, self.btn_filtros]),
                self.fila_pestanas, self.lbl_filtros, self.cuerpo,
            ]))],
        )

    # ==================================================================
    # Cargar
    # ==================================================================
    def load(self):  # propio
        self._build_tabs()
        n = self.filtros.activos
        self.btn_filtros.badge = str(n) if n else None
        self.lbl_filtros.value = self._filters_text()
        self.lbl_filtros.visible = bool(self.lbl_filtros.value)
        memorias = services.search(self.filtros)
        if self.pestana == "galeria":
            self.cuerpo.controls = self._gallery(memorias)
        else:
            self.cuerpo.controls = self._timeline(memorias)

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _build_tabs(self):  # propio
        self.fila_pestanas.controls = [
            ft.Chip(label=ft.Text(texto), leading=ft.Icon(icono, size=16), show_checkmark=False,
                    selected=self.pestana == clave,
                    on_select=lambda e, c=clave: self.set_tab(c))
            for clave, texto, icono in (("linea", "Línea de tiempo", ft.Icons.TIMELINE),
                                        ("galeria", "Galería", ft.Icons.PHOTO_LIBRARY))
        ]

    def set_tab(self, pestana: str):  # propio
        self.pestana = pestana
        self.refresh()

    def _on_search(self, e):  # propio
        self.filtros.texto = self.txt_buscar.value or ""
        self.refresh()

    def _empty(self) -> ft.Control:  # propio
        hay_filtros = self.filtros.texto or self.filtros.activos
        titulo = "Nada coincide" if hay_filtros else "Tu primera memoria"
        texto = ("Prueba con otro texto o quita filtros." if hay_filtros else
                 "Guarda los momentos que no quieres olvidar: un viaje, un aniversario, "
                 "un logro. Puede ser de hace años.")
        return ft.Container(
            padding=ft.Padding.only(top=40, left=16, right=16), alignment=ft.Alignment.TOP_CENTER,
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.AUTO_STORIES, size=56, color=ft.Colors.OUTLINE),
                ft.Text(titulo, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(texto, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
            ]),
        )

    # ==================================================================
    # Línea de tiempo
    # ==================================================================
    def _timeline(self, memorias: list[Memoria]) -> list[ft.Control]:  # propio
        controles: list[ft.Control] = []
        sin_filtros = not (self.filtros.texto or self.filtros.activos)
        if sin_filtros:
            hoy = services.on_this_day()
            if hoy:
                controles.append(self._on_this_day(hoy))
        if not memorias:
            return controles + [self._empty()]
        for anio, meses in services.timeline(memorias).items():
            controles.append(ft.Container(
                padding=ft.Padding.only(top=8),
                content=ft.Text(str(anio), size=24, weight=ft.FontWeight.BOLD)))
            for mes, lista in meses.items():
                controles.append(ft.Text(services.MESES_LARGOS[mes - 1].capitalize(), size=13,
                                         weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE))
                controles += [self._card(m) for m in lista]
        return controles

    def _on_this_day(self, memorias: list[Memoria]) -> ft.Control:  # propio
        filas = [
            ft.Container(
                ink=True, border_radius=10, on_click=lambda e, x=m: self.on_open(x),
                content=ft.Row(spacing=10, controls=[
                    thumb(m.fotos[0] if m.fotos else None, 52, 52),
                    ft.Column(spacing=0, expand=True, controls=[
                        ft.Text(m.titulo, weight=ft.FontWeight.W_500, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{services.years_ago(m)}" + (f" · {m.animo}" if m.animo else ""),
                                size=12, color=ft.Colors.OUTLINE),
                    ]),
                ]),
            )
            for m in memorias
        ]
        return ft.Container(
            padding=12, border_radius=14,
            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.AMBER),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.AMBER)),
            content=ft.Column(spacing=8, controls=[
                ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER, size=18),
                    ft.Text("Un día como hoy", weight=ft.FontWeight.BOLD),
                ]),
                *filas,
            ]),
        )

    def _card(self, m: Memoria) -> ft.Control:  # propio
        detalle = []
        if m.lugar:
            detalle.append(ft.Text(f"📍 {m.lugar}", size=12, color=ft.Colors.OUTLINE,
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
        if m.etiquetas:
            detalle.append(ft.Row(wrap=True, spacing=4, controls=[tag_chip(e) for e in m.etiquetas]))
        if m.relato:
            detalle.append(ft.Text(m.relato, size=13, max_lines=2,
                                   overflow=ft.TextOverflow.ELLIPSIS))
        fotos = [a for a in m.fotos if (a.mimetype or "").startswith("image/")]
        lado = [thumb(fotos[0], 64, 64)] if fotos else []
        if len(fotos) > 1:
            lado = [ft.Stack(width=64, height=64, controls=[
                thumb(fotos[0], 64, 64),
                ft.Container(right=2, bottom=2, padding=ft.Padding.symmetric(horizontal=5),
                             border_radius=8, bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK),
                             content=ft.Text(f"+{len(fotos) - 1}", size=10,
                                             color=ft.Colors.WHITE)),
            ])]
        return ft.Container(
            padding=10, border_radius=12, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ink=True, on_click=lambda e, x=m: self.on_open(x),
            content=ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.START, controls=[
                ft.Column(width=36, spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                          controls=[
                              ft.Text(str(m.fecha.day), size=20, weight=ft.FontWeight.BOLD),
                              ft.Text(services.short_month(m.fecha.month), size=11,
                                      color=ft.Colors.OUTLINE),
                          ]),
                ft.Column(expand=True, spacing=3, controls=[
                    ft.Text((f"{m.animo} " if m.animo else "") + m.titulo, size=15,
                            weight=ft.FontWeight.W_500, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    *detalle,
                ]),
                *lado,
            ]),
        )

    # ==================================================================
    # Galería
    # ==================================================================
    def _gallery(self, memorias: list[Memoria]) -> list[ft.Control]:  # propio
        fotos = services.photos(memorias)
        if not fotos:
            if not memorias:
                return [self._empty()]
            return [ft.Container(padding=ft.Padding.only(top=40), alignment=ft.Alignment.TOP_CENTER,
                                 content=ft.Text("Tus memorias aún no tienen fotos.",
                                                 color=ft.Colors.OUTLINE))]
        cuadros = [
            ft.Container(col={"xs": 4, "md": 3},
                         content=thumb(f.adjunto, None, None, 8, cuadrado=True,
                                       on_click=lambda e, x=f.memoria: self.on_open(x)))
            for f in fotos
        ]
        return [ft.Text(f"{len(fotos)} foto(s)", size=12, color=ft.Colors.OUTLINE),
                ft.ResponsiveRow(spacing=4, run_spacing=4, controls=cuadros)]

    # ==================================================================
    # Filtros
    # ==================================================================
    def _filters_text(self) -> str:  # propio
        f, partes = self.filtros, []
        if f.etiqueta_ids:
            nombres = [e.nombre for e in EtiquetaMemoria.search_all() if e.id in f.etiqueta_ids]
            partes.append(", ".join(nombres))
        if f.desde or f.hasta:
            desde = f.desde.strftime("%d/%m/%Y") if f.desde else "…"
            hasta = f.hasta.strftime("%d/%m/%Y") if f.hasta else "hoy"
            partes.append(f"{desde} – {hasta}")
        return ("Filtrando: " + " · ".join(partes)) if partes else ""

    def open_filters(self, e=None):  # propio
        elegidas = set(self.filtros.etiqueta_ids)
        rango = {"desde": self.filtros.desde, "hasta": self.filtros.hasta}
        fila_tags = ft.Row(wrap=True, spacing=6, run_spacing=6)
        btn_desde, btn_hasta = ft.OutlinedButton(), ft.OutlinedButton()

        def render():  # propio
            fila_tags.controls = [
                ft.Chip(label=ft.Text(t.nombre), show_checkmark=False,
                        leading=ft.Container(width=10, height=10, border_radius=5, bgcolor=t.color),
                        selected=t.id in elegidas,
                        on_select=lambda ev, i=t.id: (elegidas.symmetric_difference_update({i}),
                                                      render(), self.page.update()))
                for t in EtiquetaMemoria.search_all()
            ]
            btn_desde.content = f"Desde: {rango['desde']:%d/%m/%Y}" if rango["desde"] else "Desde: —"
            btn_hasta.content = f"Hasta: {rango['hasta']:%d/%m/%Y}" if rango["hasta"] else "Hasta: —"

        def pick(clave):  # propio
            def changed(ev):  # propio
                valor = ev.control.value
                rango[clave] = valor.date() if hasattr(valor, "date") else valor
                render()
                self.page.update()

            self.page.show_dialog(ft.DatePicker(
                first_date=date(1900, 1, 1), last_date=date.today(),
                value=rango[clave] or date.today(), on_change=changed))

        def apply(ev=None, limpiar=False):  # propio
            self.page.pop_dialog()
            if limpiar:
                elegidas.clear()
                rango["desde"] = rango["hasta"] = None
            self.filtros.etiqueta_ids = set(elegidas)
            self.filtros.desde, self.filtros.hasta = rango["desde"], rango["hasta"]
            self.refresh()

        btn_desde.on_click = lambda ev: pick("desde")
        btn_hasta.on_click = lambda ev: pick("hasta")
        render()
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Filtros"),
            content=ft.Column(tight=True, spacing=10, controls=[
                ft.Text("Etiquetas (cualquiera)", size=12, color=ft.Colors.OUTLINE), fila_tags,
                ft.Text("Rango de fechas", size=12, color=ft.Colors.OUTLINE),
                ft.Row(wrap=True, controls=[btn_desde, btn_hasta]),
            ]),
            actions=[ft.TextButton("Limpiar", on_click=lambda ev: apply(limpiar=True)),
                     ft.TextButton("Aplicar", on_click=apply)],
        ))

"""
Tablero de Notas (/notas):

  [🔍 Buscar en tus notas…                    ]
  [✎ Nota rápida (Enter guarda)    ] [☑] [📝]     <- captura rápida
  (Todas) (● Súper) (● Ideas) (● Pendientes) (🗄 Archivadas 3)

  Fijadas
  ┌──────────┐ ┌──────────┐
  │ Súper    │ │ Llamar al│     tarjetas en 2 columnas
  │ ☐ Leche  │ │ dentista │     tocar = abrir · dejar presionado = menú
  │ ☑ Pan    │ └──────────┘     (en las listas, la casilla se palomea aquí mismo)
  └──────────┘
  Otras …

Captura rápida: escribes y Enter -> nota guardada, sin abrir nada (1 paso).
Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.ui import add_button, notify, service
from modulos.notas import routes, services
from modulos.notas.models import EtiquetaNota, Nota
from modulos.notas.views.comun import actions_sheet, note_bg

MAX_CASILLAS = 6        # casillas que se ven en la tarjeta (el resto: "+N más")
MAX_RENGLONES = 8       # renglones de texto que se ven en la tarjeta


class NotesBoard:
    def __init__(self, page: ft.Page, on_open):
        """on_open(nota): abre el editor."""
        self.page = page
        self.on_open = on_open
        self.texto = ""
        self.etiqueta_id: int | None = None
        self.archivadas = False

        self.txt_buscar = ft.TextField(
            hint_text="Buscar en tus notas…", prefix_icon=ft.Icons.SEARCH, dense=True,
            border_radius=24, on_change=self._on_search, expand=True,
        )
        self.txt_rapida = ft.TextField(
            hint_text="Nota rápida (Enter guarda)", prefix_icon=ft.Icons.EDIT, dense=True,
            expand=True, on_submit=self.quick_save,
        )
        self.fila_rapida = ft.Row(spacing=0, controls=[
            self.txt_rapida,
            ft.IconButton(ft.Icons.CHECK_BOX_OUTLINED, tooltip="Nueva lista",
                          on_click=lambda e: self.new("lista")),
            ft.IconButton(ft.Icons.NOTE_ADD_OUTLINED, tooltip="Nueva nota",
                          on_click=lambda e: self.new("texto")),
        ])
        self.fila_filtros = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)
        self.lista = ft.ListView(expand=True, spacing=8, padding=ft.Padding.only(bottom=90))

        self.vista = ft.View(
            route=routes.BASE,
            appbar=ft.AppBar(
                title=ft.Text("Notas"),
                actions=[ft.IconButton(ft.Icons.TABLE_VIEW, tooltip="Exportar a Excel",
                                       on_click=lambda e: self.page.run_task(self.export_excel))],
            ),
            floating_action_button=add_button("Nueva nota", lambda e: self.new("texto")),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, spacing=8, controls=[
                        ft.Row([self.txt_buscar]), self.fila_rapida, self.fila_filtros,
                        self.lista,
                    ]),
                )
            ],
        )

    # ==================================================================
    # Cargar
    # ==================================================================
    def load(self):  # propio
        self._build_filters()
        self.fila_rapida.visible = not self.archivadas
        notas = services.search(self.texto, self.etiqueta_id, self.archivadas)
        fijadas = [n for n in notas if n.fijada]
        otras = [n for n in notas if not n.fijada]
        controles: list[ft.Control] = []
        if fijadas:
            controles += [self._header("Fijadas", ft.Icons.PUSH_PIN), self._grid(fijadas)]
        if otras:
            if fijadas:
                controles.append(self._header("Otras"))
            controles.append(self._grid(otras))
        if not notas:
            controles.append(self._empty())
        self.lista.controls = controles

    def refresh(self):  # propio
        self.load()
        self.page.update()

    def _empty(self) -> ft.Control:  # propio
        if self.texto:
            texto, sub = "Nada coincide", f"No hay notas con «{self.texto}»."
        elif self.archivadas:
            texto, sub = "Sin archivadas", "Deja presionada una nota → Archivar."
        else:
            texto, sub = "Sin notas todavía", "Escribe arriba y presiona Enter, o usa ☑ para una lista."
        return ft.Container(
            padding=ft.Padding.only(top=40), alignment=ft.Alignment.TOP_CENTER,
            content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                ft.Icon(ft.Icons.STICKY_NOTE_2_OUTLINED, size=56, color=ft.Colors.OUTLINE),
                ft.Text(texto, size=16, weight=ft.FontWeight.BOLD),
                ft.Text(sub, color=ft.Colors.OUTLINE, text_align=ft.TextAlign.CENTER),
            ]),
        )

    @staticmethod
    def _header(texto: str, icono=None) -> ft.Control:  # propio
        return ft.Row(spacing=4, controls=[
            *([ft.Icon(icono, size=14, color=ft.Colors.OUTLINE)] if icono else []),
            ft.Text(texto, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
        ])

    def _grid(self, notas: list[Nota]) -> ft.Control:  # propio
        """2 columnas en el celular (col 6 de 12), 3 en pantallas anchas."""
        return ft.ResponsiveRow(
            spacing=8, run_spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[ft.Container(col={"xs": 6, "md": 4}, content=self._card(n))
                      for n in notas],
        )

    # ==================================================================
    # Filtros
    # ==================================================================
    def _build_filters(self):  # propio
        etiquetas = EtiquetaNota.search_all()
        if self.etiqueta_id not in {e.id for e in etiquetas}:
            self.etiqueta_id = None
        n_arch = services.count_archived()
        chips = [ft.Chip(label=ft.Text("Todas"),
                         selected=self.etiqueta_id is None and not self.archivadas,
                         on_select=lambda e: self.set_filter(None, False))]
        chips += [ft.Chip(label=ft.Text(e.nombre),
                          leading=ft.Container(width=10, height=10, border_radius=5,
                                               bgcolor=e.color),
                          show_checkmark=False,
                          selected=self.etiqueta_id == e.id and not self.archivadas,
                          on_select=lambda ev, i=e.id: self.set_filter(i, False))
                  for e in etiquetas]
        chips.append(ft.Chip(label=ft.Text(f"Archivadas ({n_arch})" if n_arch else "Archivadas"),
                             leading=ft.Icon(ft.Icons.ARCHIVE_OUTLINED, size=16),
                             show_checkmark=False, selected=self.archivadas,
                             on_select=lambda e: self.set_filter(None, not self.archivadas)))
        self.fila_filtros.controls = chips

    def set_filter(self, etiqueta_id: int | None, archivadas: bool):  # propio
        self.etiqueta_id, self.archivadas = etiqueta_id, archivadas
        self.refresh()

    def _on_search(self, e):  # propio
        self.texto = self.txt_buscar.value or ""
        self.refresh()

    # ==================================================================
    # Tarjeta
    # ==================================================================
    def _card(self, n: Nota) -> ft.Control:  # propio
        partes: list[ft.Control] = []
        if n.titulo:
            partes.append(ft.Text(n.titulo, weight=ft.FontWeight.BOLD, max_lines=2,
                                  overflow=ft.TextOverflow.ELLIPSIS))
        if n.es_lista:
            partes += self._card_items(n)
        elif n.cuerpo:
            partes.append(ft.Text(n.cuerpo, size=13, max_lines=MAX_RENGLONES,
                                  overflow=ft.TextOverflow.ELLIPSIS))
        pie = []
        if n.etiqueta:
            pie.append(ft.Container(
                padding=ft.Padding.symmetric(horizontal=6, vertical=1), border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.2, n.etiqueta.color),
                content=ft.Text(n.etiqueta.nombre, size=10)))
        if n.es_lista and n.items:
            hechas, total = n.avance
            pie.append(ft.Text(f"✓ {hechas}/{total}", size=10, color=ft.Colors.OUTLINE))
        if n.fijada:
            pie.append(ft.Icon(ft.Icons.PUSH_PIN, size=12, color=ft.Colors.OUTLINE))
        if pie:
            partes.append(ft.Row(pie, spacing=6, wrap=True))
        return ft.Container(
            padding=10, border_radius=12, bgcolor=note_bg(n.color),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
            ink=True,
            on_click=lambda e, x=n: self.on_open(x),
            on_long_press=lambda e, x=n: actions_sheet(self.page, x, self.refresh),
            content=ft.Column(spacing=4, tight=True, controls=partes or [
                ft.Text("(vacía)", italic=True, color=ft.Colors.OUTLINE)]),
        )

    def _card_items(self, n: Nota) -> list[ft.Control]:  # propio
        """Primero las pendientes; la casilla se palomea sin abrir la nota."""
        orden = sorted(n.items, key=lambda i: (i.hecho, i.secuencia))
        visibles = [i for i in orden if i.texto.strip()][:MAX_CASILLAS]
        filas = [
            ft.Row(spacing=4, controls=[
                ft.Container(
                    content=ft.Icon(ft.Icons.CHECK_BOX if i.hecho
                                    else ft.Icons.CHECK_BOX_OUTLINE_BLANK, size=18,
                                    color=ft.Colors.OUTLINE if i.hecho else None),
                    on_click=lambda e, iid=i.id: self.toggle_item(iid),
                ),
                ft.Text(i.texto, size=13, expand=True, max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        color=ft.Colors.OUTLINE if i.hecho else None,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
                        if i.hecho else None),
            ])
            for i in visibles
        ]
        resto = sum(1 for i in n.items if i.texto.strip()) - len(visibles)
        if resto > 0:
            filas.append(ft.Text(f"+{resto} más", size=11, color=ft.Colors.OUTLINE))
        return filas

    # ==================================================================
    # Acciones
    # ==================================================================
    def quick_save(self, e=None):  # propio
        """Enter en la captura rápida: guarda y deja el campo listo para otra."""
        texto = (self.txt_rapida.value or "").strip()
        if not texto:
            return
        services.quick_note(texto, self.etiqueta_id)
        self.txt_rapida.value = ""
        notify(self.page, "Nota guardada")
        self.refresh()
        self.page.run_task(self.txt_rapida.focus)  # listo para la siguiente

    def new(self, tipo: str):  # propio
        self.on_open(services.new_note(tipo, self.etiqueta_id))

    def toggle_item(self, item_id: int):  # propio
        services.toggle_item(item_id)
        self.refresh()

    async def export_excel(self):  # propio
        from modulos.notas.exportador import export_all, export_file_name

        try:
            contenido = export_all()
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo generar el Excel: {ex}")
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Guardar notas en Excel",
            file_name=export_file_name(),
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
            src_bytes=contenido,
        )
        if ruta or self.page.web:
            notify(self.page, "Excel exportado")

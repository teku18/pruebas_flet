"""
Caja de adjuntos del formulario de un pendiente:

  Adjuntos
  ┌──────────────────────────────────────┐
  │ [🖼] captura_2026-09-29.png  120 KB ✕ │  <- tocar: vista previa (imagen/GIF)
  │ [📄] requisitos.pdf          1.2 MB ✕ │           o abrir con su app
  └──────────────────────────────────────┘
  [📎 Adjuntar archivo]  [📷 De mis capturas]

Mismo esquema que la bitácora de Proyectos: mientras editas, lo que agregas o
quitas queda "pendiente" y se aplica con apply() al dar Guardar.
Cada elemento es un dict:
  {"id": int|None, "nombre", "tamano", "ruta": str|None (guardado),
   "origen": str|None (archivo elegido), "datos": bytes|None (web),
   "captura": str|None (viene de la bandeja; se quita de ella al guardar)}

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from pathlib import Path

import flet as ft

from core.storage import absolute_path, human_size, save_file
from core.ui import notify, service
from modulos.desarrollo.capturas import Captura, delete_capture, list_captures
from modulos.desarrollo.models import DEV_ADJUNTOS_DIR, DevAdjunto

EXT_IMAGEN = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_VISTA_PREVIA = 15 * 1024 * 1024  # no cargar en pantalla archivos gigantes


def local_path(ruta: str | None) -> str | None:  # propio
    """La ruta solo sirve si el archivo existe en ESTA máquina (no en el celular)."""
    return ruta if ruta and Path(ruta).exists() else None


def is_image(nombre: str) -> bool:  # propio
    return Path(nombre).suffix.lower() in EXT_IMAGEN


def file_icon(nombre: str):  # propio
    ext = Path(nombre).suffix.lower()
    if ext == ".gif":
        return ft.Icons.MOVIE
    if ext in EXT_IMAGEN:
        return ft.Icons.IMAGE
    if ext == ".pdf":
        return ft.Icons.PICTURE_AS_PDF
    return ft.Icons.INSERT_DRIVE_FILE


def read_bytes(adj: dict) -> bytes | None:  # propio
    """El contenido del adjunto (esté guardado, recién elegido o en la bandeja)."""
    if adj.get("datos"):
        return adj["datos"]
    ruta = adj.get("origen") or (str(absolute_path(adj["ruta"])) if adj.get("ruta") else None)
    if not ruta or not Path(ruta).exists() or Path(ruta).stat().st_size > MAX_VISTA_PREVIA:
        return None
    return Path(ruta).read_bytes()


def show_preview(page: ft.Page, titulo: str, contenido: bytes):  # propio
    """Imagen (o GIF animado) en grande, en un diálogo."""
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(titulo, size=14),
            content=ft.Container(
                width=360,
                height=560,
                content=ft.Image(src=contenido, fit=ft.BoxFit.CONTAIN),
            ),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
        )
    )


class AttachmentsBox:
    def __init__(self, page: ft.Page):
        self.page = page
        self.items: list[dict] = []
        self.borrar: list[int] = []  # ids de DevAdjunto a borrar al guardar

        self.col = ft.Column(spacing=6)
        self.lbl_vacio = ft.Text("Sin adjuntos", size=12, italic=True, color=ft.Colors.OUTLINE)
        self.control = ft.Column(
            spacing=6,
            controls=[
                ft.Text("Adjuntos", weight=ft.FontWeight.BOLD),
                self.lbl_vacio,
                self.col,
                ft.Row(
                    wrap=True,
                    controls=[
                        ft.OutlinedButton("Adjuntar archivo", icon=ft.Icons.ATTACH_FILE,
                                          on_click=self.pick_files),
                        ft.OutlinedButton("De mis capturas", icon=ft.Icons.PHOTO_CAMERA,
                                          on_click=self.pick_captures),
                    ],
                ),
            ],
        )

    # ==================================================================
    # Cargar / limpiar
    # ==================================================================
    def clear(self):  # propio
        self.items, self.borrar = [], []
        self.render()

    def load(self, adjuntos: list[DevAdjunto]):  # propio
        self.items = [
            {"id": a.id, "nombre": a.nombre, "tamano": a.tamano, "ruta": a.ruta,
             "origen": None, "datos": None, "captura": None}
            for a in adjuntos
        ]
        self.borrar = []
        self.render()

    def add_capture(self, c: Captura):  # propio
        """Una captura de la bandeja (pendiente de guardar)."""
        if any(x.get("captura") == str(c.ruta) for x in self.items):
            return  # ya estaba
        self.items.append({"id": None, "nombre": c.nombre, "tamano": c.tamano, "ruta": None,
                           "origen": str(c.ruta), "datos": None, "captura": str(c.ruta)})

    # ==================================================================
    # Pintar
    # ==================================================================
    def render(self):  # propio
        self.col.controls = [self._row(i, adj) for i, adj in enumerate(self.items)]
        self.lbl_vacio.visible = not self.items

    def _thumbnail(self, adj: dict) -> ft.Control:  # propio
        if is_image(adj["nombre"]):
            contenido = read_bytes(adj)
            if contenido:
                return ft.Image(src=contenido, width=44, height=44, fit=ft.BoxFit.COVER,
                                border_radius=6)
        return ft.Container(
            width=44, height=44, border_radius=6, alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            content=ft.Icon(file_icon(adj["nombre"]), color=ft.Colors.PRIMARY),
        )

    def _row(self, indice: int, adj: dict) -> ft.Control:  # propio
        detalle = human_size(adj["tamano"])
        if adj["id"] is None:
            detalle += " · se guarda al dar Guardar"
        return ft.Container(
            padding=ft.Padding.all(4),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda e, a=adj: self.page.run_task(self.open, a),
            content=ft.Row(
                controls=[
                    self._thumbnail(adj),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(adj["nombre"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(detalle, size=11, color=ft.Colors.OUTLINE),
                        ],
                    ),
                    ft.IconButton(ft.Icons.CLOSE, tooltip="Quitar",
                                  on_click=lambda e, i=indice: self.remove(i)),
                ],
            ),
        )

    # ==================================================================
    # Acciones
    # ==================================================================
    async def open(self, adj: dict):  # propio
        """Imagen/GIF -> vista previa; otro archivo -> su app predeterminada."""
        if is_image(adj["nombre"]):
            contenido = read_bytes(adj)
            if contenido:
                show_preview(self.page, adj["nombre"], contenido)
                return
        ruta = adj.get("origen") or (str(absolute_path(adj["ruta"])) if adj.get("ruta") else None)
        if not ruta or not Path(ruta).exists():
            notify(self.page, "El archivo se podrá abrir después de guardar")
            return
        await service(self.page, ft.UrlLauncher).launch_url(Path(ruta).as_uri())

    async def pick_files(self, e=None):  # propio
        """
        with_data=True: además de la ruta, trae el CONTENIDO del archivo. Desde el
        celular la ruta es del teléfono y Python (en tu compu) no la puede leer.
        """
        archivos = await service(self.page, ft.FilePicker).pick_files(
            dialog_title="Adjuntar", allow_multiple=True, with_data=True
        )
        for f in archivos or []:
            self.items.append({"id": None, "nombre": f.name, "tamano": f.size, "ruta": None,
                               "origen": local_path(f.path), "datos": f.bytes,
                               "captura": None})
        self.render()
        self.page.update()

    def remove(self, indice: int):  # propio
        adj = self.items.pop(indice)
        if adj["id"] is not None:
            self.borrar.append(adj["id"])  # se borra de verdad al guardar
        self.render()
        self.page.update()

    def pick_captures(self, e=None):  # propio
        """Diálogo con la bandeja de capturas: marca las que quieras adjuntar."""
        capturas = list_captures()
        if not capturas:
            notify(self.page, "No tienes capturas. Usa el botón 📷 flotante para tomar una.")
            return
        elegidas: set[str] = set()

        def toggle(ruta: str, valor: bool):  # propio
            (elegidas.add if valor else elegidas.discard)(ruta)

        def attach(e):  # propio
            self.page.pop_dialog()
            for c in capturas:
                if str(c.ruta) in elegidas:
                    self.add_capture(c)
            self.render()
            self.page.update()

        filas = [
            ft.Row(
                controls=[
                    ft.Checkbox(on_change=lambda e, r=str(c.ruta): toggle(r, e.control.value)),
                    ft.Image(src=c.ruta.read_bytes(), width=48, height=48,
                             fit=ft.BoxFit.COVER, border_radius=6),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text("Grabación" if c.es_grabacion else "Captura", size=13,
                                    weight=ft.FontWeight.W_500),
                            ft.Text(f"{c.fecha:%d/%m %H:%M} · {human_size(c.tamano)}",
                                    size=11, color=ft.Colors.OUTLINE),
                        ],
                    ),
                ]
            )
            for c in capturas
        ]
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Mis capturas"),
                content=ft.Container(width=340, content=ft.Column(filas, scroll=ft.ScrollMode.AUTO,
                                                                  tight=True)),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                    ft.TextButton("Adjuntar", on_click=attach),
                ],
            )
        )

    # ==================================================================
    # Guardar (lo llama el formulario después de crear/actualizar)
    # ==================================================================
    def apply(self, pendiente_id: int):  # propio
        for adjunto_id in self.borrar:
            DevAdjunto.delete(adjunto_id)
        self.borrar = []

        carpeta = DEV_ADJUNTOS_DIR / str(pendiente_id)
        for adj in self.items:
            if adj["id"] is not None:
                continue
            ruta = save_file(
                Path(adj["origen"]) if adj["origen"] else None,
                adj["datos"],
                carpeta,
                adj["nombre"],
            )
            nuevo = DevAdjunto.create(pendiente_id=pendiente_id, nombre=adj["nombre"],
                                      ruta=ruta.as_posix(), tamano=adj["tamano"])
            adj["id"], adj["ruta"] = nuevo.id, nuevo.ruta
            if adj.get("captura"):
                delete_capture(adj["captura"])  # ya está en el pendiente: sale de la bandeja

"""
Una memoria (/memorias/memoria): nueva, ver o editar (mismo patrón que Proyectos).

  Ver:                                   Editar / nueva:
  ┌──────────────────────────────┐       Fecha del suceso  [24/12/2019 📅]
  │  [foto] [foto] [foto]  ←→    │       Título
  └──────────────────────────────┘       ¿Cómo te sentiste?  🥰 😄 🤩 😌 …
  🥰 Cine en nuestro aniversario         📍 Lugar (opcional)
  24 de diciembre de 2019 · 📍 Perisur   Etiquetas  (Viaje)(Pareja)(+ Nueva)
  (Pareja)                               Relato
  Vimos una de terror y luego tacos…     Fotos  [▢][▢][+ Agregar fotos]

Fotos: se eligen de la galería del celular (pueden ser varias) y se COPIAN a la
app al guardar (reducidas sin perder calidad, ver imagenes.py). Si es una
memoria nueva y la primera foto trae fecha, se propone esa fecha.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date
from io import BytesIO

import flet as ft
from PIL import Image, ImageOps

from core.ui import DateField, confirm, delete_button, edit_button, notify, service
from modulos.memorias import imagenes, routes, services
from modulos.memorias.models import ANIMOS, EtiquetaMemoria, Memoria
from modulos.memorias.views.comun import show_photo, tag_chip, thumb


def preview_bytes(datos: bytes) -> bytes | None:  # propio
    """Miniatura en memoria de una foto aún no guardada (para verla en el formulario)."""
    try:
        img = ImageOps.exif_transpose(Image.open(BytesIO(datos))).convert("RGB")
        img.thumbnail((240, 240))
        salida = BytesIO()
        img.save(salida, "JPEG", quality=75)
        return salida.getvalue()
    except Exception:  # noqa: BLE001  (HEIC u otro formato: sin vista previa)
        return None


class MemoryView:
    def __init__(self, page: ft.Page, on_saved):
        """on_saved(): al guardar o borrar (la línea de tiempo se recarga)."""
        self.page = page
        self.on_saved = on_saved
        self.registro: Memoria | None = None
        self.modo = "nuevo"
        self.animo: str | None = None
        self.etiquetas: set[int] = set()
        self.fotos: list[dict] = []        # {"id", "nombre", "datos", "mini", "adjunto"}
        self.fotos_borrar: list[int] = []
        self.fecha_tocada = False          # ¿el usuario eligió la fecha a mano?
        self._build()

    # ==================================================================
    # Construcción
    # ==================================================================
    def _build(self):  # propio
        # --- Ver ---
        self.carrusel = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)
        self.lbl_titulo = ft.Text(size=22, weight=ft.FontWeight.BOLD)
        self.lbl_fecha = ft.Text(size=13, color=ft.Colors.OUTLINE)
        self.fila_tags_ver = ft.Row(wrap=True, spacing=6)
        self.lbl_relato = ft.Text(size=15, selectable=True)
        self.col_ver = ft.Column(spacing=10, controls=[
            self.carrusel, self.lbl_titulo, self.lbl_fecha, self.fila_tags_ver, self.lbl_relato,
        ])

        # --- Editar ---
        self.campo_fecha = DateField(self.page, "¿Cuándo pasó?")
        self.campo_fecha.picker.on_change = self._on_date
        self.txt_titulo = ft.TextField(label="Título", max_length=150, expand=True)
        self.fila_animos = ft.Row(wrap=True, spacing=4)
        self.txt_lugar = ft.TextField(label="Lugar (opcional)", prefix_icon=ft.Icons.PLACE,
                                      max_length=150, expand=True)
        self.fila_tags = ft.Row(wrap=True, spacing=6, run_spacing=6)
        self.txt_relato = ft.TextField(label="Relato", hint_text="¿Qué pasó? ¿Con quién?",
                                       multiline=True, min_lines=4, max_lines=14, expand=True)
        self.fila_fotos = ft.Row(wrap=True, spacing=8, run_spacing=8)
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.save)
        self.col_editar = ft.Column(spacing=10, controls=[
            self.campo_fecha.fila,
            ft.Row([self.txt_titulo]),
            ft.Text("¿Cómo te sentiste?", size=12, color=ft.Colors.OUTLINE),
            self.fila_animos,
            ft.Row([self.txt_lugar]),
            ft.Text("Etiquetas", size=12, color=ft.Colors.OUTLINE),
            self.fila_tags,
            ft.Row([self.txt_relato]),
            ft.Text("Fotos", size=12, color=ft.Colors.OUTLINE),
            self.fila_fotos,
            ft.Row([self.btn_guardar,
                    ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancel)]),
        ])

        self.lbl_barra = ft.Text("Nueva memoria")
        self.btn_editar = edit_button(self.edit)
        self.btn_eliminar = delete_button(self.confirm_delete)
        self.vista = ft.View(
            route=routes.MEMORIA,
            appbar=ft.AppBar(title=self.lbl_barra, actions=[self.btn_editar, self.btn_eliminar]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(controls=[self.col_ver, self.col_editar]))],
        )

    # ==================================================================
    # Abrir
    # ==================================================================
    def new(self):  # propio
        self.registro = None
        self.modo = "nuevo"
        self.campo_fecha.set_value(date.today())
        self.campo_fecha.set_range(date(1900, 1, 1), date.today())
        self.txt_titulo.value = self.txt_lugar.value = self.txt_relato.value = ""
        self.txt_titulo.error_text = None
        self.animo, self.etiquetas = None, set()
        self.fotos, self.fotos_borrar = [], []
        self.fecha_tocada = False
        self._apply_mode()
        self.page.navigate(routes.MEMORIA)

    def show(self, m: Memoria):  # propio
        self.registro = services.get(m.id)
        if self.registro is None:
            notify(self.page, "La memoria ya no existe")
            return
        self.modo = "ver"
        self._fill()
        self._apply_mode()
        self.page.navigate(routes.MEMORIA)

    def _fill(self):  # propio
        m = self.registro
        self.campo_fecha.set_value(m.fecha)
        self.campo_fecha.set_range(date(1900, 1, 1), date.today())
        self.txt_titulo.value = m.titulo
        self.txt_titulo.error_text = None
        self.txt_lugar.value = m.lugar or ""
        self.txt_relato.value = m.relato or ""
        self.animo = m.animo
        self.etiquetas = {e.id for e in m.etiquetas}
        self.fotos = [{"id": a.id, "nombre": a.nombre, "datos": None, "adjunto": a,
                       "mini": imagenes.read_thumbnail(a.ruta)} for a in m.fotos]
        self.fotos_borrar = []
        self.fecha_tocada = True

    def _apply_mode(self):  # propio
        ver = self.modo == "ver"
        self.col_ver.visible = ver
        self.col_editar.visible = not ver
        self.btn_editar.visible = self.btn_eliminar.visible = ver
        self.lbl_barra.value = {"nuevo": "Nueva memoria", "ver": "Memoria",
                                "editar": "Editar memoria"}[self.modo]
        if ver:
            self._render_view()
        else:
            self._render_moods()
            self._render_tags()
            self._render_photos()

    # ==================================================================
    # Ver
    # ==================================================================
    def _render_view(self):  # propio
        m = self.registro
        self.carrusel.controls = [
            thumb(a, 220, 220, 14,
                  on_click=lambda e, ad=a: show_photo(self.page, imagenes.read_photo(ad.ruta)))
            for a in m.fotos if (a.mimetype or "").startswith("image/")
        ]
        self.carrusel.visible = bool(self.carrusel.controls)
        self.lbl_titulo.value = f"{m.animo}  {m.titulo}" if m.animo else m.titulo
        partes = [services.long_date(m.fecha)]
        if m.lugar:
            partes.append(f"📍 {m.lugar}")
        self.lbl_fecha.value = " · ".join(partes)
        self.fila_tags_ver.controls = [tag_chip(e) for e in m.etiquetas]
        self.fila_tags_ver.visible = bool(m.etiquetas)
        self.lbl_relato.value = m.relato or ""
        self.lbl_relato.visible = bool(m.relato)

    # ==================================================================
    # Editar: ánimo, etiquetas, fotos
    # ==================================================================
    def _render_moods(self):  # propio
        def chip(emoji):  # propio
            elegido = emoji == self.animo
            return ft.Container(
                width=40, height=40, border_radius=20, alignment=ft.Alignment.CENTER,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if elegido else None,
                border=ft.Border.all(2, ft.Colors.PRIMARY) if elegido else None,
                content=ft.Text(emoji, size=22),
                on_click=lambda e, x=emoji: self._pick_mood(x),
            )

        self.fila_animos.controls = [chip(a) for a in ANIMOS]

    def _pick_mood(self, emoji: str):  # propio
        self.animo = None if self.animo == emoji else emoji  # tocar otra vez = quitar
        self._render_moods()
        self.page.update()

    def _render_tags(self):  # propio
        chips = [
            ft.Chip(label=ft.Text(e.nombre), show_checkmark=False,
                    leading=ft.Container(width=10, height=10, border_radius=5, bgcolor=e.color),
                    selected=e.id in self.etiquetas,
                    on_select=lambda ev, i=e.id: self._toggle_tag(i))
            for e in EtiquetaMemoria.search_all()
        ]
        chips.append(ft.Chip(label=ft.Text("Nueva"), leading=ft.Icon(ft.Icons.ADD, size=16),
                             on_click=self._new_tag))
        self.fila_tags.controls = chips

    def _toggle_tag(self, etiqueta_id: int):  # propio
        self.etiquetas ^= {etiqueta_id}
        self._render_tags()
        self.page.update()

    def _new_tag(self, e=None):  # propio
        txt = ft.TextField(label="Nombre", max_length=40, autofocus=True)

        def save(ev=None):  # propio
            try:
                nueva = services.create_label(txt.value or "")
            except ValueError as ex:
                txt.error_text = str(ex)
                self.page.update()
                return
            self.page.pop_dialog()
            self.etiquetas.add(nueva.id)
            self._render_tags()
            self.page.update()

        txt.on_submit = save
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Nueva etiqueta"), content=txt,
            actions=[ft.TextButton("Cancelar", on_click=lambda ev: self.page.pop_dialog()),
                     ft.TextButton("Crear", on_click=save)],
        ))

    def _render_photos(self):  # propio
        cuadros = []
        for k, f in enumerate(self.fotos):
            imagen = (ft.Image(src=f["mini"], fit=ft.BoxFit.COVER, width=96, height=96)
                      if f["mini"] else ft.Icon(ft.Icons.IMAGE_OUTLINED))
            cuadros.append(ft.Stack(width=96, height=96, controls=[
                ft.Container(width=96, height=96, border_radius=10, alignment=ft.Alignment.CENTER,
                             clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                             bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, content=imagen),
                ft.Container(right=2, top=2, width=26, height=26, border_radius=13,
                             bgcolor=ft.Colors.with_opacity(0.6, ft.Colors.BLACK),
                             alignment=ft.Alignment.CENTER,
                             content=ft.Icon(ft.Icons.CLOSE, size=16, color=ft.Colors.WHITE),
                             on_click=lambda e, kk=k: self._remove_photo(kk)),
            ]))
        cuadros.append(ft.Container(
            width=96, height=96, border_radius=10, alignment=ft.Alignment.CENTER,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            on_click=lambda e: self.page.run_task(self.pick_photos),
            content=ft.Column(spacing=2, tight=True,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER, controls=[
                                  ft.Icon(ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED),
                                  ft.Text("Agregar", size=11)]),
        ))
        self.fila_fotos.controls = cuadros

    async def pick_photos(self):  # propio
        archivos = await service(self.page, ft.FilePicker).pick_files(
            dialog_title="Elige las fotos", allow_multiple=True,
            file_type=ft.FilePickerFileType.IMAGE,
            with_data=True,  # en el celular llega el contenido, no una ruta útil
        )
        nuevas = 0
        for f in archivos or []:
            datos = f.bytes
            if datos is None and f.path:
                with open(f.path, "rb") as fh:
                    datos = fh.read()
            if not datos:
                continue
            # Memoria nueva: la fecha de la primera foto (EXIF) se propone sola
            if not self.fecha_tocada and self.registro is None:
                cuando = imagenes.photo_date(datos)
                if cuando and cuando <= date.today():
                    self.campo_fecha.set_value(cuando)
                    self.fecha_tocada = True
                    notify(self.page, f"Fecha tomada de la foto: {services.long_date(cuando)}")
            self.fotos.append({"id": None, "nombre": f.name, "datos": datos, "adjunto": None,
                               "mini": preview_bytes(datos)})
            nuevas += 1
        if nuevas:
            self._render_photos()
            self.page.update()

    def _remove_photo(self, k: int):  # propio
        foto = self.fotos.pop(k)
        if foto["id"] is not None:
            self.fotos_borrar.append(foto["id"])  # se borra de verdad al guardar
        self._render_photos()
        self.page.update()

    def _on_date(self, e):  # propio
        self.fecha_tocada = True
        self.campo_fecha._on_change(e)

    # ==================================================================
    # Acciones
    # ==================================================================
    def edit(self, e=None):  # propio
        self.modo = "editar"
        self._apply_mode()
        self.page.update()

    def cancel(self, e=None):  # propio
        if self.modo == "editar":
            self.registro = services.get(self.registro.id)
            self._fill()
            self.modo = "ver"
            self._apply_mode()
            self.page.update()
        else:
            self.page.navigate(routes.BASE)

    def save(self, e=None):  # propio
        self.txt_titulo.error_text = None
        if not (self.txt_titulo.value or "").strip():
            self.txt_titulo.error_text = "Ponle un título"
            self.page.update()
            return
        self.btn_guardar.disabled = True
        self.btn_guardar.content = "Guardando…"  # copiar y reducir fotos toma un momento
        self.page.update()
        try:
            self.registro = services.save(
                self.registro.id if self.registro else None,
                fecha=self.campo_fecha.valor, titulo=self.txt_titulo.value,
                relato=self.txt_relato.value, lugar=self.txt_lugar.value, animo=self.animo,
                etiqueta_ids=sorted(self.etiquetas),
                fotos_nuevas=[services.FotoNueva(f["nombre"], f["datos"])
                              for f in self.fotos if f["id"] is None],
                fotos_borrar=self.fotos_borrar,
            )
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo guardar: {ex}")
            return
        finally:
            self.btn_guardar.disabled = False
            self.btn_guardar.content = "Guardar"
        self._fill()
        self.modo = "ver"
        self._apply_mode()
        notify(self.page, "Memoria guardada")
        self.on_saved()
        self.page.update()

    def confirm_delete(self, e=None):  # propio
        m = self.registro

        def delete():  # propio
            Memoria.delete(m.id)
            notify(self.page, "Memoria eliminada")
            self.on_saved()
            self.page.navigate(routes.BASE)

        n = len(m.fotos)
        mensaje = f"¿Eliminar «{m.titulo}»?" + (f"\n\nTambién se borran sus {n} foto(s)."
                                                 if n else "")
        confirm(self.page, "Eliminar memoria", mensaje, delete)

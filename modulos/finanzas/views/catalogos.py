"""
Catálogos de Finanzas (Plataformas, Conceptos):
  /finanzas/ajustes/plataformas
  /finanzas/ajustes/inversiones   (en pantalla se llama "Conceptos")

Una sola clase sirve para los dos catálogos: recibe el modelo como parámetro.

catalog_dialog() es el diálogo de alta/edición. Lo usan esta pantalla Y el
"+ Nuevo…" del formulario de movimientos, para no repetir la lógica.

Nota: el modelo se sigue llamando Inversion (tabla "inversiones", campo
inversion_id). Solo cambió lo que se ve en pantalla: "Concepto". Renombrar
la tabla sería una migración; por un texto no vale la pena.
"""
from dataclasses import dataclass

import flet as ft

from core.ui import add_button, icon_box, notify, swipe_to_delete


@dataclass(frozen=True)
class Labels:
    """Textos de un catálogo (con su género: 'Nuevo concepto' / 'Nueva plataforma')."""
    singular: str   # "Concepto"
    plural: str     # "Conceptos"
    nuevo: str      # "Nuevo" / "Nueva"
    hecho: str      # terminación de "guardado"/"archivado": "o" / "a"


# Nombre del modelo -> textos que se ven en pantalla
CATALOG_LABELS = {
    "Inversion": Labels("Concepto", "Conceptos", "Nuevo", "o"),
    "Plataforma": Labels("Plataforma", "Plataformas", "Nueva", "a"),
}


def labels(modelo) -> Labels:  # propio
    return CATALOG_LABELS[modelo.__name__]


def catalog_dialog(page: ft.Page, modelo, on_saved, registro=None):  # propio
    """
    Diálogo para crear (registro=None) o editar un registro de catálogo.
    on_saved(registro_guardado) se llama al guardar.
    """
    t = labels(modelo)
    txt_nombre = ft.TextField(
        label="Nombre", value=registro.nombre if registro else "", autofocus=True
    )
    sw_activo = ft.Switch(
        label="Activo", value=registro.activo if registro else True, visible=registro is not None
    )
    # Solo los catálogos con meta (Concepto) muestran este campo
    tiene_meta = hasattr(modelo, "meta")
    meta_actual = getattr(registro, "meta", None) if registro else None
    txt_meta = ft.TextField(
        label="Meta (opcional)",
        prefix="$ ",
        value=f"{meta_actual:.2f}" if meta_actual else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
        visible=tiene_meta,
    )

    def save(e=None):  # propio
        nombre = (txt_nombre.value or "").strip()
        if not nombre:
            txt_nombre.error_text = "Requerido"
            page.update()
            return
        valores = {"nombre": nombre}
        if tiene_meta:
            valores["meta"] = float(txt_meta.value) if txt_meta.value else None
        try:
            modelo.check_unique(nombre, excluir_id=registro.id if registro else None)
            if registro is None:
                guardado = modelo.create(activo=True, **valores)
            else:
                guardado = modelo.update(registro.id, activo=sw_activo.value, **valores)
        except ValueError as ex:
            txt_nombre.error_text = str(ex)
            page.update()
            return
        page.pop_dialog()
        on_saved(guardado)

    txt_nombre.on_submit = save  # Enter también guarda
    titulo = f"Editar {t.singular.lower()}" if registro else f"{t.nuevo} {t.singular.lower()}"
    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Column(tight=True, controls=[txt_nombre, txt_meta, sw_activo]),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton("Guardar", on_click=save),
            ],
        )
    )


class CatalogView:
    def __init__(self, page: ft.Page, modelo, route: str, icono):
        self.page = page
        self.modelo = modelo
        self.t = labels(modelo)
        self.icono = icono

        self.lista = ft.ListView(expand=True, spacing=4, padding=ft.Padding.only(bottom=90))
        pronombre = "lo" if self.t.hecho == "o" else "la"  # archívalo / archívala
        self.lbl_ayuda = ft.Text(
            "Desliza a la izquierda para borrar (solo si no tiene movimientos). "
            f"Si ya tiene, archíva{pronombre}: deja de salir en el formulario.",
            size=12,
            color=ft.Colors.OUTLINE,
        )
        self.vista = ft.View(
            route=route,
            appbar=ft.AppBar(title=ft.Text(self.t.plural)),
            floating_action_button=add_button(
                f"{self.t.nuevo} {self.t.singular.lower()}", self.new
            ),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_ayuda, self.lista]),
                )
            ],
        )

    def load(self):  # propio
        usos = self.modelo.usage_count()
        self.lista.controls = [self._row(r, usos.get(r.id, 0)) for r in self.modelo.search_all()]

    def _row(self, registro, usos: int) -> ft.Control:  # propio
        color = ft.Colors.PRIMARY if registro.activo else ft.Colors.OUTLINE
        detalle = "1 movimiento" if usos == 1 else f"{usos} movimientos"
        if getattr(registro, "meta", None):
            detalle += f" · meta ${registro.meta:,.2f}"
        if not registro.activo:
            detalle += f" · archivad{self.t.hecho}"
        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,
            on_click=lambda e, r=registro: self.edit(r),
            content=ft.Row(
                spacing=10,
                controls=[
                    icon_box(self.icono if registro.activo else ft.Icons.ARCHIVE, color),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(
                                registro.nombre,
                                size=16,
                                weight=ft.FontWeight.W_500,
                                color=None if registro.activo else ft.Colors.OUTLINE,
                            ),
                            ft.Text(detalle, size=12, color=ft.Colors.OUTLINE),
                        ],
                    ),
                ],
            ),
        )
        if usos:
            return linea  # con movimientos no se puede borrar: sin deslizar
        return swipe_to_delete(
            self.page,
            key=f"{self.modelo.__tablename__}-{registro.id}",
            contenido=linea,
            titulo=f"Eliminar {self.t.singular.lower()}",
            mensaje=f"¿Eliminar «{registro.nombre}»?",
            on_delete=lambda r=registro: self._delete(r),
        )

    def _after_save(self, registro):  # propio
        self.load()
        notify(self.page, f"«{registro.nombre}» guardad{self.t.hecho}")
        self.page.update()

    def new(self, e=None):  # propio
        catalog_dialog(self.page, self.modelo, self._after_save)

    def edit(self, registro):  # propio
        catalog_dialog(self.page, self.modelo, self._after_save, registro)

    def _delete(self, registro):  # propio
        try:
            self.modelo.delete(registro.id)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"Error al eliminar: {ex}")
        self.load()
        self.page.update()

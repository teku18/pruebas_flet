"""
Ajustes de Finanzas (/finanzas/ajustes), desde el engrane de la lista de periodos:
  - Plataformas  -> catálogo
  - Conceptos    -> catálogo (modelo Inversion)
  - Importar desde Excel
"""
import flet as ft

from core.ui import notify
from modulos.finanzas import routes
from modulos.finanzas.importador import import_workbook
from modulos.finanzas.models import TIPO_SELECTION, Inversion, Plataforma
from modulos.finanzas.views.catalogos import labels


class FinanceSettingsView:
    def __init__(self, page: ft.Page, on_imported):
        """on_imported: se llama después de importar (para refrescar la lista de periodos)."""
        self.page = page
        self.on_imported = on_imported
        self.picker = ft.FilePicker()

        self.tile_plataformas = self._tile(
            ft.Icons.ACCOUNT_BALANCE, "Plataformas", routes.PLATAFORMAS
        )
        self.tile_inversiones = self._tile(ft.Icons.FLAG, "Conceptos", routes.INVERSIONES)
        self.tile_importar = ft.ListTile(
            leading=ft.Icon(ft.Icons.UPLOAD_FILE),
            title=ft.Text("Importar desde Excel"),
            subtitle=ft.Text("Cada pestaña se vuelve un periodo"),
            on_click=self.pick_excel,
        )

        self.vista = ft.View(
            route=routes.AJUSTES,
            appbar=ft.AppBar(title=ft.Text("Ajustes de Finanzas")),
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text("Catálogos", weight=ft.FontWeight.BOLD),
                            self.tile_plataformas,
                            self.tile_inversiones,
                            ft.Divider(),
                            ft.Text("Datos", weight=ft.FontWeight.BOLD),
                            self.tile_importar,
                        ],
                    )
                )
            ],
        )

    def _tile(self, icono, titulo: str, ruta: str) -> ft.ListTile:  # propio
        return ft.ListTile(
            leading=ft.Icon(icono),
            title=ft.Text(titulo),
            subtitle=ft.Text(""),
            trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT),
            on_click=lambda e: self.page.navigate(ruta),
        )

    def load(self):  # propio
        """Cuántos activos hay en cada catálogo."""
        for tile, modelo in ((self.tile_plataformas, Plataforma),
                             (self.tile_inversiones, Inversion)):
            registros = modelo.search_all()
            activos = sum(1 for r in registros if r.activo)
            g = labels(modelo).hecho  # "o" / "a" según el género del catálogo
            tile.subtitle.value = (f"{activos} activ{g}s · "
                                   f"{len(registros) - activos} archivad{g}s")

    # --- Importar ---------------------------------------------------------
    async def pick_excel(self, e=None):  # propio
        archivos = await self.picker.pick_files(
            dialog_title="Elige el Excel de movimientos",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx"],
        )
        if not archivos:
            return
        if not archivos[0].path:
            notify(self.page, "No se pudo leer la ruta del archivo")
            return
        try:
            resultado = import_workbook(archivos[0].path)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se importó nada: {ex}")
            return
        self.load()
        self.on_imported()
        self._show_result(resultado)

    def _show_result(self, r):  # propio
        """Resumen de lo que se importó, en un diálogo."""
        lineas = []
        if r.periodos:
            lineas.append(f"Periodos: {', '.join(r.periodos)}")
            lineas.append(f"Movimientos: {r.movimientos}")
            for tipo, n in r.por_tipo.most_common():
                lineas.append(f"   {TIPO_SELECTION.get(tipo, tipo)}: {n}")
        if r.catalogos_nuevos:
            lineas.append("Nuevos en catálogo: " + ", ".join(r.catalogos_nuevos))
        lineas += [f"ℹ {n}" for n in r.notas]
        lineas += [f"⚠ {a}" for a in r.avisos]
        if r.omitidas:
            lineas.append("Omitidas: " + "; ".join(r.omitidas))
        if r.filas_con_error:
            lineas.append(f"Filas con error ({len(r.filas_con_error)}): "
                          + "; ".join(r.filas_con_error[:5]))
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Importación terminada" if r.periodos else "No se importó nada"),
                content=ft.Text("\n".join(lineas) or "El archivo no tenía pestañas válidas."),
                actions=[ft.TextButton("Listo", on_click=lambda e: self.page.pop_dialog())],
            )
        )

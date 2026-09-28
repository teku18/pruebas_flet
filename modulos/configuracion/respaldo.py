"""
Sección "Respaldo" de Configuración.

  Carpeta          -> dónde se guardan los zip (p. ej. ~/Respaldos/ControlKraken,
                      que rclone sube a Google Drive)
  Automático       -> 2 min después de tu último cambio se crea un respaldo
                      (también al abrir la app si quedaron cambios sin respaldar)
  Respaldar ahora  -> uno manual
  Restaurar…       -> eliges un zip; tu BD actual se guarda antes en respaldos/

Equipo nuevo: si al abrir la app no había BD, se ofrece restaurar el respaldo
más reciente (o elegir otro).

Cambio de base: al abrir, si en la carpeta hay un respaldo de OTRO equipo más
nuevo que lo último que respaldaste/restauraste aquí, avisa:
  [Restaurar]              -> este equipo sigue desde ahí
  [Este equipo es mi base] -> no vuelve a preguntar por ese respaldo
Mientras el aviso está abierto no corre el automático (para no taparlo).

Las preferencias (carpeta, automático, último respaldo) viven en el
dispositivo (SharedPreferences), NO en la BD: así restaurar no las pisa.
"""
import asyncio
import time
from pathlib import Path

import flet as ft

from core import backup, database
from core.storage import human_size
from core.ui import confirm, notify

CLAVE_CARPETA = "respaldo_carpeta"
CLAVE_AUTO = "respaldo_auto"
CLAVE_ULTIMO = "respaldo_ultimo"   # timestamp del último respaldo o restauración aquí
CLAVE_IGNORADOS = "respaldo_ignorados"  # zips de otro equipo a los que dijiste "no"
CARPETA_SUGERIDA = str(Path.home() / "Respaldos" / "ControlKraken")

ESPERA_TRAS_CAMBIO = 120  # segundos sin cambios antes del respaldo automático
REVISAR_CADA = 30         # segundos entre revisiones


class BackupSection:
    def __init__(self, page: ft.Page, prefs: ft.SharedPreferences):
        self.page = page
        self.prefs = prefs
        self.picker = ft.FilePicker()
        self.carpeta = ""
        self.auto = True
        self.ultimo = 0.0
        self.ocupado = False
        self.pausado = False   # True mientras decides sobre un respaldo de otro equipo
        self.ignorados: list[str] = []

        self.lbl_carpeta = ft.Text(size=13)
        self.lbl_estado = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.sw_auto = ft.Switch(label="Respaldo automático", value=True,
                                 on_change=self.toggle_auto)
        self.btn_respaldar = ft.Button("Respaldar ahora", icon=ft.Icons.BACKUP,
                                       on_click=self.backup_now)

        self.controles = [
            ft.Text("Respaldo", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Un zip con tu BD y adjuntos. Guárdalo en una carpeta que se suba "
                    "a Drive y podrás restaurarlo en otro equipo.",
                    size=12, color=ft.Colors.OUTLINE),
            ft.Row([ft.Icon(ft.Icons.FOLDER, size=18), ft.Container(self.lbl_carpeta, expand=True),
                    ft.TextButton("Cambiar", on_click=self.pick_folder)]),
            self.sw_auto,
            self.lbl_estado,
            ft.Row(wrap=True, controls=[
                self.btn_respaldar,
                ft.OutlinedButton("Restaurar…", icon=ft.Icons.SETTINGS_BACKUP_RESTORE,
                                  on_click=self.pick_backup),
            ]),
        ]

    # ==================================================================
    # Preferencias
    # ==================================================================
    async def load(self):  # propio
        """Al abrir la app: lee preferencias, arranca el automático y, si es un
        equipo nuevo, ofrece restaurar."""
        self.carpeta = await self.prefs.get(CLAVE_CARPETA) or CARPETA_SUGERIDA
        auto = await self.prefs.get(CLAVE_AUTO)
        self.auto = auto is None or str(auto).lower() in ("true", "1")
        self.ultimo = float(await self.prefs.get(CLAVE_ULTIMO) or 0)
        self.ignorados = list(await self.prefs.get(CLAVE_IGNORADOS) or [])
        self.sw_auto.value = self.auto
        self._refresh()
        self.page.update()

        # Primero se revisa si hay algo que restaurar; DESPUÉS el automático
        # (si respaldara antes, taparía el respaldo del otro equipo)
        if database.BD_NUEVA:
            self._offer_restore()
        else:
            self.check_other_device()
        self.page.run_task(self._auto_loop)

    def _refresh(self):  # propio
        """Textos: carpeta y cuándo fue el último respaldo."""
        self.lbl_carpeta.value = self.carpeta.replace(str(Path.home()), "~")
        respaldos = backup.list_backups(Path(self.carpeta))
        if respaldos:
            r = respaldos[0]
            estado = f"Último: {r.fecha:%d/%m/%Y %H:%M} · {human_size(r.tamaño)} · {len(respaldos)} en la carpeta"
        else:
            estado = "Aún no hay respaldos en esta carpeta."
        if backup.changed_since(self.ultimo):
            estado += "\nHay cambios sin respaldar."
        self.lbl_estado.value = estado

    async def toggle_auto(self, e):  # propio
        self.auto = bool(self.sw_auto.value)
        await self.prefs.set(CLAVE_AUTO, self.auto)

    async def pick_folder(self, e=None):  # propio
        ruta = await self.picker.get_directory_path(
            dialog_title="Carpeta para los respaldos", initial_directory=self.carpeta
        )
        if not ruta:
            return
        self.carpeta = ruta
        await self.prefs.set(CLAVE_CARPETA, ruta)
        self._refresh()
        self.page.update()

    # ==================================================================
    # Respaldar
    # ==================================================================
    async def _do_backup(self, motivo: str) -> Path | None:  # propio
        """Crea el zip en la carpeta (en otro hilo para no congelar la pantalla)."""
        if self.ocupado:
            return None
        self.ocupado = True
        self.btn_respaldar.disabled = True
        self.page.update()
        try:
            inicio = time.time()
            ruta = await asyncio.to_thread(backup.create_backup, Path(self.carpeta), motivo)
            await asyncio.to_thread(backup.prune, Path(self.carpeta))
            self.ultimo = inicio
            await self.prefs.set(CLAVE_ULTIMO, str(inicio))
            return ruta
        finally:
            self.ocupado = False
            self.btn_respaldar.disabled = False
            self._refresh()
            self.page.update()

    async def backup_now(self, e=None):  # propio
        try:
            ruta = await self._do_backup("manual")
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo respaldar: {ex}")
            return
        if ruta:
            notify(self.page, f"Respaldo creado: {ruta.name}")

    async def _auto_loop(self):  # propio
        """Cada 30 s: si hubo cambios y ya pasaron 2 min sin más, respalda."""
        while True:
            try:
                quieto = time.time() - backup.last_change() >= ESPERA_TRAS_CAMBIO
                if (self.auto and not self.pausado and quieto
                        and backup.changed_since(self.ultimo)):
                    await self._do_backup("automático")
            except Exception:  # noqa: BLE001  (p. ej. carpeta no disponible: se reintenta)
                pass
            await asyncio.sleep(REVISAR_CADA)

    # ==================================================================
    # Restaurar
    # ==================================================================
    def _offer_restore(self):  # propio
        """Primer arranque en este equipo: ¿empezar vacío o restaurar?"""
        respaldos = backup.list_backups(Path(self.carpeta))
        mas_nuevo = respaldos[0] if respaldos else None

        def restore_newest(e):  # propio
            self.page.pop_dialog()
            self.page.run_task(self._restore, mas_nuevo.ruta)

        def choose(e):  # propio
            self.page.pop_dialog()
            self.page.run_task(self.pick_backup)

        texto = "No hay datos en este equipo. ¿Recuperas tu información de un respaldo?"
        acciones = [ft.TextButton("Empezar vacío", on_click=lambda e: self.page.pop_dialog()),
                    ft.TextButton("Elegir archivo…", on_click=choose)]
        if mas_nuevo:
            texto += f"\n\nEl más reciente en tu carpeta: {self._describe(mas_nuevo)}."
            acciones.append(ft.Button("Restaurar el más reciente", on_click=restore_newest))
        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Bienvenido a ControlKraken"),
            content=ft.Text(texto), actions=acciones,
        ))

    def _describe(self, b: backup.BackupInfo, manifest: dict | None = None) -> str:  # propio
        """'27/09/2026 18:50 · «laptop-edgar»'"""
        if manifest is None:
            try:
                manifest = backup.read_manifest(b.ruta)
            except ValueError:
                manifest = {}
        texto = f"{b.fecha:%d/%m/%Y %H:%M}"
        if manifest.get("equipo"):
            texto += f" · «{manifest['equipo']}»"
        return texto

    def check_other_device(self):  # propio
        """¿Hay un respaldo de otro equipo más nuevo que lo último de aquí?"""
        hallado = backup.newest_foreign(Path(self.carpeta), self.ultimo, set(self.ignorados))
        if hallado is None:
            return
        b, manifest = hallado
        self.pausado = True

        texto = (f"Hay un respaldo más reciente hecho en otro equipo:\n"
                 f"{self._describe(b, manifest)}\n\n"
                 "Si ahora capturas en aquel equipo, restáuralo para seguir desde ahí.")
        # (+1 s: la fecha del nombre del zip no trae fracciones de segundo)
        if backup.changed_since(max(self.ultimo, b.fecha.timestamp() + 1)):
            texto += ("\n\n⚠ Este equipo tiene cambios posteriores a ese respaldo: si "
                      "restauras se reemplazan (quedan guardados en respaldos/).")

        def restore(e):  # propio
            self.page.pop_dialog()
            self.pausado = False
            self.page.run_task(self._restore, b.ruta)

        async def keep_mine(e):  # propio
            self.page.pop_dialog()
            self.pausado = False
            self.ignorados = (self.ignorados + [b.ruta.name])[-20:]
            await self.prefs.set(CLAVE_IGNORADOS, self.ignorados)
            notify(self.page, "Sigues con los datos de este equipo")

        self.page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Respaldo de otro equipo"),
            content=ft.Text(texto),
            actions=[
                ft.TextButton("Este equipo es mi base", on_click=keep_mine),
                ft.Button("Restaurar", on_click=restore),
            ],
        ))

    async def pick_backup(self, e=None):  # propio
        archivos = await self.picker.pick_files(
            dialog_title="Elige el respaldo (ControlKraken_….zip)",
            initial_directory=self.carpeta,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["zip"],
        )
        if not archivos or not archivos[0].path:
            return
        ruta = Path(archivos[0].path)
        try:
            m = backup.read_manifest(ruta)
        except ValueError as ex:
            notify(self.page, f"No se puede restaurar: {ex}")
            return

        detalle = f"Respaldo del {m.get('creado', '?').replace('T', ' ')}"
        if m.get("equipo"):
            detalle += f" (equipo «{m['equipo']}», v{m.get('version_app', '?')})"
        confirm(
            self.page, "Restaurar respaldo",
            f"{detalle}.\n\nReemplaza TODOS los datos de este equipo. Tu información "
            "actual se guarda antes en la carpeta respaldos/ por si acaso.",
            lambda: self.page.run_task(self._restore, ruta),
        )

    async def _restore(self, ruta: Path):  # propio
        try:
            await asyncio.to_thread(backup.restore_backup, ruta)
        except Exception as ex:  # noqa: BLE001
            notify(self.page, f"No se pudo restaurar: {ex}")
            return
        # Lo restaurado ya está en la carpeta: no hace falta respaldarlo otra vez
        self.ultimo = time.time()
        await self.prefs.set(CLAVE_ULTIMO, str(self.ultimo))
        self._refresh()
        notify(self.page, "Datos restaurados")
        self.page.navigate("/")  # al inicio: cada pantalla relee la BD al abrirla
        self.page.update()


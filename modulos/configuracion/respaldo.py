"""
Sección "Respaldo" de Configuración.

  Carpeta          -> dónde se guardan los zip (p. ej. ~/Respaldos/ControlKraken,
                      que rclone sube a Google Drive)
  Automático       -> cada N horas / días / semanas / meses (tú eliges).
                      "Próximo respaldo" = último + N × periodo. Solo respalda si
                      hubo cambios; si la app estaba cerrada cuando tocaba, lo
                      hace al abrirla.
  Respaldar ahora  -> uno manual
  Restaurar…       -> eliges un zip; tu BD actual se guarda antes en respaldos/

Equipo nuevo: si al abrir la app no había BD, se ofrece restaurar el respaldo
más reciente (o elegir otro).

Cambio de base: al abrir, si en la carpeta hay un respaldo de OTRO equipo más
nuevo que lo último que respaldaste/restauraste aquí, avisa:
  [Restaurar]              -> este equipo sigue desde ahí
  [Este equipo es mi base] -> no vuelve a preguntar por ese respaldo
Mientras el aviso está abierto no corre el automático (para no taparlo).

Drive: una línea dice a qué cuenta de Google sube rclone y si tus respaldos
ya están arriba (core/drive.py). La app misma sincroniza con rclone (no hace
falta cron): sube después de cada respaldo, baja lo reciente al abrir, y el
botón [Sincronizar] hace las dos cosas.

Las preferencias (carpeta, automático, último respaldo) viven en el
dispositivo (SharedPreferences), NO en la BD: así restaurar no las pisa.
"""
import asyncio
import time
from datetime import datetime
from pathlib import Path

import flet as ft

from core import backup, database, drive
from core.storage import human_size
from core.ui import confirm, notify, pref_get, pref_set, service

CLAVE_CARPETA = "respaldo_carpeta"
CLAVE_AUTO = "respaldo_auto"
CLAVE_ULTIMO = "respaldo_ultimo"   # timestamp del último respaldo o restauración aquí
CLAVE_IGNORADOS = "respaldo_ignorados"  # zips de otro equipo a los que dijiste "no"
CLAVE_CADA = "respaldo_cada"            # número: cada 15…
CLAVE_PERIODO = "respaldo_periodo"      # …"dia" | "semana" | "mes" | "hora"
CARPETA_SUGERIDA = str(Path.home() / "Respaldos" / "ControlKraken")

ESPERA_TRAS_CAMBIO = 120  # si toca, espera 2 min sin cambios (no respalda a media captura)
REVISAR_CADA = 30         # segundos entre revisiones


class BackupSection:
    def __init__(self, page: ft.Page, prefs: ft.SharedPreferences):
        self.page = page
        self.prefs = prefs
        self.carpeta = ""
        self.auto = True
        self.ultimo = 0.0
        self.cada = 1
        self.periodo = "dia"
        self.ocupado = False
        self.pausado = False   # True mientras decides sobre un respaldo de otro equipo
        self.ignorados: list[str] = []

        self.lbl_carpeta = ft.Text(size=13)
        self.lbl_estado = ft.Text(size=12, color=ft.Colors.OUTLINE)
        self.lbl_drive = ft.Text("Drive: sin revisar", size=12)
        self.ico_drive = ft.Icon(ft.Icons.CLOUD_OUTLINED, size=18, color=ft.Colors.OUTLINE)
        self.sw_auto = ft.Switch(label="Respaldo automático", value=True,
                                 on_change=self.toggle_auto)
        self.txt_cada = ft.TextField(
            value="1", width=70, dense=True, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^\d{0,3}$", allow=True),
            on_blur=self.change_frequency, on_submit=self.change_frequency,
        )
        self.dd_periodo = ft.Dropdown(
            value="dia", width=150, dense=True, on_select=self.change_frequency,
            options=[ft.DropdownOption(key=k, text=v.capitalize())
                     for k, v in backup.PERIODOS.items()],
        )
        self.lbl_proximo = ft.Text(size=12)
        self.fila_frecuencia = ft.Column(spacing=4, controls=[
            ft.Row([ft.Text("Respaldar cada"), self.txt_cada, self.dd_periodo],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            self.lbl_proximo,
        ])
        self.btn_respaldar = ft.Button("Respaldar ahora", icon=ft.Icons.BACKUP,
                                       on_click=self.backup_now)

        self.controles = [
            ft.Text("Respaldo", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Un zip con tu BD y adjuntos. Guárdalo en una carpeta que se suba "
                    "a Drive y podrás restaurarlo en otro equipo.",
                    size=12, color=ft.Colors.OUTLINE),
            ft.Row([ft.Icon(ft.Icons.FOLDER, size=18), ft.Container(self.lbl_carpeta, expand=True),
                    ft.TextButton("Cambiar", on_click=self.pick_folder)]),
            ft.Row([self.ico_drive, ft.Container(self.lbl_drive, expand=True),
                    ft.TextButton("Sincronizar", on_click=self.sync_drive)]),
            self.sw_auto,
            self.fila_frecuencia,
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
        self.carpeta = await pref_get(self.prefs, CLAVE_CARPETA) or CARPETA_SUGERIDA
        auto = await pref_get(self.prefs, CLAVE_AUTO)
        self.auto = auto is None or str(auto).lower() in ("true", "1")
        self.ultimo = float(await pref_get(self.prefs, CLAVE_ULTIMO) or 0)
        self.ignorados = list(await pref_get(self.prefs, CLAVE_IGNORADOS) or [])
        self.cada = int(await pref_get(self.prefs, CLAVE_CADA) or 1)
        periodo = await pref_get(self.prefs, CLAVE_PERIODO)
        self.periodo = periodo if periodo in backup.PERIODOS else "dia"
        self.sw_auto.value = self.auto
        self.txt_cada.value, self.dd_periodo.value = str(self.cada), self.periodo
        self._refresh()
        self.page.update()

        # Primero se revisa si hay algo que restaurar; DESPUÉS el automático
        # (si respaldara antes, taparía el respaldo del otro equipo)
        self.pausado = True  # el automático espera a que bajen los de otros equipos
        self.page.run_task(self._auto_loop)
        self.page.run_task(self._startup_sync)

    async def _startup_sync(self):  # propio
        """Al abrir: baja de Drive lo reciente y LUEGO revisa si hay algo que restaurar."""
        self.lbl_drive.value = "Drive: bajando respaldos recientes…"
        self.page.update()
        await asyncio.to_thread(drive.download_recent, self.carpeta)
        self.pausado = False
        self._refresh()
        if database.BD_NUEVA:
            self._offer_restore()
        else:
            self.check_other_device()  # si hay aviso, vuelve a pausar
        await self.check_drive()

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

        # Próximo respaldo automático
        self.fila_frecuencia.visible = self.auto
        proximo = backup.next_backup(self.ultimo, self.cada, self.periodo)
        if proximo <= datetime.now():
            cuando = ("ahora (en cuanto termines de capturar)"
                      if backup.changed_since(self.ultimo) else "cuando haya cambios")
        else:
            cuando = f"{proximo:%d/%m/%Y %H:%M}"
        self.lbl_proximo.value = f"Próximo respaldo: {cuando}"

    async def sync_drive(self, e=None):  # propio
        """[Sincronizar]: sube lo que falte, baja lo reciente y muestra el estado."""
        self.lbl_drive.value = "Drive: sincronizando…"
        self.page.update()
        error = await asyncio.to_thread(drive.upload, self.carpeta)
        if not error:
            error = await asyncio.to_thread(drive.download_recent, self.carpeta)
        self._refresh()
        await self.check_drive()
        if error:
            notify(self.page, error)

    async def _upload_after_backup(self):  # propio
        await asyncio.to_thread(drive.upload, self.carpeta)
        await self.check_drive()

    async def check_drive(self, e=None):  # propio
        """¿A qué cuenta de Google sube rclone y ya subió lo más reciente?"""
        self.lbl_drive.value = "Drive: revisando…"
        self.page.update()
        estado = await asyncio.to_thread(drive.drive_status)

        if estado.error:
            icono, color, texto = ft.Icons.CLOUD_OFF, ft.Colors.ORANGE, estado.error
        else:
            cuenta = estado.cuenta or "?"
            if estado.nombre:
                cuenta += f" ({estado.nombre})"
            locales = [b.ruta.name for b in backup.list_backups(Path(self.carpeta))]
            faltan = [n for n in locales if n not in estado.en_drive]
            if locales and locales[0] in estado.en_drive:
                icono, color, detalle = ft.Icons.CLOUD_DONE, ft.Colors.GREEN, "al día"
            elif locales:
                icono, color = ft.Icons.CLOUD_UPLOAD, ft.Colors.ORANGE
                detalle = f"{len(faltan)} por subir (toca Sincronizar)"
            else:
                icono, color, detalle = ft.Icons.CLOUD_DONE, ft.Colors.OUTLINE, "sin respaldos aún"
            texto = f"Drive: {cuenta}\n{detalle}"
        self.ico_drive.icon, self.ico_drive.color = icono, color
        self.lbl_drive.value = texto
        self.page.update()

    async def toggle_auto(self, e):  # propio
        self.auto = bool(self.sw_auto.value)
        await pref_set(self.prefs, CLAVE_AUTO, self.auto)
        self._refresh()
        self.page.update()

    async def change_frequency(self, e=None):  # propio
        """Cambiaste el número o el periodo: se guarda y se recalcula el próximo."""
        try:
            self.cada = max(1, int(self.txt_cada.value or 1))
        except ValueError:
            self.cada = 1
        self.txt_cada.value = str(self.cada)
        self.periodo = self.dd_periodo.value or "dia"
        await pref_set(self.prefs, CLAVE_CADA, self.cada)
        await pref_set(self.prefs, CLAVE_PERIODO, self.periodo)
        self._refresh()
        self.page.update()

    async def pick_folder(self, e=None):  # propio
        ruta = await service(self.page, ft.FilePicker).get_directory_path(
            dialog_title="Carpeta para los respaldos", initial_directory=self.carpeta
        )
        if not ruta:
            return
        self.carpeta = ruta
        await pref_set(self.prefs, CLAVE_CARPETA, ruta)
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
            await pref_set(self.prefs, CLAVE_ULTIMO, str(inicio))
            self.page.run_task(self._upload_after_backup)  # a Drive, en segundo plano
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
        """Cada 30 s: si ya toca (según tu periodicidad), hubo cambios y llevas
        2 min sin capturar, respalda."""
        while True:
            try:
                toca = backup.next_backup(self.ultimo, self.cada, self.periodo) <= datetime.now()
                quieto = time.time() - backup.last_change() >= ESPERA_TRAS_CAMBIO
                if (self.auto and not self.pausado and toca and quieto
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
            await pref_set(self.prefs, CLAVE_IGNORADOS, self.ignorados)
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
        archivos = await service(self.page, ft.FilePicker).pick_files(
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
        await pref_set(self.prefs, CLAVE_ULTIMO, str(self.ultimo))
        self._refresh()
        notify(self.page, "Datos restaurados")
        self.page.navigate("/")  # al inicio: cada pantalla relee la BD al abrirla
        self.page.update()


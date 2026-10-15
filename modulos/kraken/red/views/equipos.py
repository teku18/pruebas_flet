"""
Mis equipos: alta y edición (diálogo) + acciones rápidas de un equipo.

  Nombre   [Servidor casa      ]
  IP o dominio [192.168.1.10   ]
  Puertos  [22, 80, 8069       ]   (los que te importan: Puertos los usa)
  MAC      [AA:BB:CC:DD:EE:FF  ]   (opcional: para encenderlo con Wake-on-LAN)
  Notas    [                   ]
  [✓] Acceso SSH                    (aparece en la herramienta SSH)
      Usuario [edgar]  Puerto [22]  Contraseña [••••]
      Servicios a vigilar [odoo postgresql nginx]   Log [/var/log/odoo/odoo-server.log]

La contraseña SSH se guarda tal cual (texto normal) y viaja en el respaldo,
como todo lo de Kraken Tools.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from modulos.kraken.comun import MONO
from modulos.kraken.models import Equipo
from modulos.kraken.models.red import LOG_POR_DEFECTO, SERVICIOS_POR_DEFECTO
from modulos.kraken.red.wol import normalize_mac


def equipment_dialog(page: ft.Page, equipo: Equipo | None, on_saved,  # propio
                     host: str = "", puertos: str | None = None, nombre: str | None = None,
                     ssh: bool = False):
    """
    on_saved(equipo) al guardar. host/puertos/nombre: valores sugeridos para uno nuevo.
    ssh=True: la sección "Acceso SSH" viene abierta (desde la herramienta SSH).
    """
    mono = ft.TextStyle(font_family=MONO)
    txt_nombre = ft.TextField(label="Nombre", value=equipo.nombre if equipo else (nombre or ""),
                              autofocus=True, hint_text="Servidor casa, Router, Mi PC…")
    txt_host = ft.TextField(label="IP o dominio", value=equipo.host if equipo else host,
                            text_style=mono, autocorrect=False,
                            capitalization=ft.TextCapitalization.NONE)
    txt_puertos = ft.TextField(label="Puertos (opcional)", helper="Los que te importan",
                               value=(equipo.puertos if equipo else puertos) or "",
                               hint_text="22, 80, 443, 8069", text_style=mono)
    txt_mac = ft.TextField(label="MAC (opcional)", helper="Para encenderlo con Wake-on-LAN",
                           value=(equipo.mac if equipo else "") or "",
                           hint_text="AA:BB:CC:DD:EE:FF", text_style=mono)
    txt_notas = ft.TextField(label="Notas (opcional)", value=(equipo.notas if equipo else "") or "",
                             multiline=True, max_lines=3)
    # --- SSH ---
    con_ssh = bool(equipo and equipo.tiene_ssh) or ssh
    sw_ssh = ft.Switch(label="Acceso SSH", value=con_ssh)
    txt_usuario = ft.TextField(label="Usuario SSH", expand=2, text_style=mono, autocorrect=False,
                               capitalization=ft.TextCapitalization.NONE,
                               value=(equipo.ssh_usuario if equipo else "") or "")
    txt_ssh_puerto = ft.TextField(label="Puerto", expand=1, text_style=mono,
                                  keyboard_type=ft.KeyboardType.NUMBER,
                                  value=str((equipo.ssh_puerto if equipo else None) or 22))
    txt_clave = ft.TextField(label="Contraseña", password=True, can_reveal_password=True,
                             value=(equipo.ssh_clave if equipo else "") or "",
                             helper="También se usa para los comandos con sudo")
    txt_servicios = ft.TextField(label="Servicios a vigilar", text_style=mono,
                                 value=(equipo.ssh_servicios if equipo else None)
                                 or SERVICIOS_POR_DEFECTO,
                                 helper="Separados por espacio (como en systemctl)")
    txt_log = ft.TextField(label="Archivo de log", text_style=mono,
                           value=(equipo.ssh_log if equipo else None) or LOG_POR_DEFECTO)
    bloque_ssh = ft.Column(spacing=10, visible=con_ssh, controls=[
        ft.Row([txt_usuario, txt_ssh_puerto]), txt_clave, txt_servicios, txt_log,
        ft.Text("La contraseña se guarda tal cual y viaja en tu respaldo.", size=11,
                color=ft.Colors.OUTLINE)])

    def toggle_ssh(e):  # propio
        bloque_ssh.visible = sw_ssh.value
        page.update()

    sw_ssh.on_change = toggle_ssh

    def save(e=None):  # propio
        for campo in (txt_nombre, txt_host, txt_puertos, txt_mac, txt_usuario, txt_ssh_puerto):
            campo.error = None
        valores = dict(nombre=(txt_nombre.value or "").strip(),
                       host=(txt_host.value or "").strip().lower(),
                       puertos=(txt_puertos.value or "").strip() or None,
                       mac=None, notas=(txt_notas.value or "").strip() or None)
        if sw_ssh.value:
            usuario = (txt_usuario.value or "").strip()
            puerto = (txt_ssh_puerto.value or "22").strip()
            if not usuario:
                txt_usuario.error = "Escribe el usuario"
            if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
                txt_ssh_puerto.error = "1 a 65535"
            if txt_usuario.error or txt_ssh_puerto.error:
                page.update()
                return
            valores.update(ssh_usuario=usuario, ssh_puerto=int(puerto),
                           ssh_clave=txt_clave.value or None,
                           ssh_servicios=(txt_servicios.value or "").strip() or None,
                           ssh_log=(txt_log.value or "").strip() or None)
            if equipo and (equipo.host != valores["host"]
                           or (equipo.ssh_puerto or 22) != int(puerto)):
                valores["ssh_huella"] = None  # otro servidor: se aprende su huella de nuevo
        else:
            valores.update(ssh_usuario=None, ssh_clave=None, ssh_huella=None)
        try:
            if (txt_mac.value or "").strip():
                try:
                    valores["mac"] = normalize_mac(txt_mac.value)
                except ValueError as ex:
                    txt_mac.error = str(ex)
                    raise
            Equipo.check_unique(valores["nombre"], excluir_id=equipo.id if equipo else None)
            guardado = (Equipo.update(equipo.id, **valores) if equipo
                        else Equipo.create(**valores))
        except ValueError as ex:
            texto = str(ex)
            destino = (txt_mac if txt_mac.error else txt_puertos if "uerto" in texto or
                       "ango" in texto else txt_host if "IP" in texto else txt_nombre)
            destino.error = texto
            page.update()
            return
        page.pop_dialog()
        on_saved(guardado)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar equipo" if equipo else "Nuevo equipo"),
        content=ft.Container(width=460, content=ft.Column(
            tight=True, spacing=10, scroll=ft.ScrollMode.AUTO,
            controls=[txt_nombre, txt_host, txt_puertos, txt_mac, txt_notas,
                      sw_ssh, bloque_ssh])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar", on_click=save)],
    ))

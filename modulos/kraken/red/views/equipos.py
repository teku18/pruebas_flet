"""
Mis equipos: alta y edición (diálogo) + acciones rápidas de un equipo.

  Nombre   [Servidor casa      ]
  IP o dominio [192.168.1.10   ]
  Puertos  [22, 80, 8069       ]   (los que te importan: Puertos los usa)
  MAC      [AA:BB:CC:DD:EE:FF  ]   (opcional: para encenderlo con Wake-on-LAN)
  Notas    [                   ]

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from modulos.kraken.comun import MONO
from modulos.kraken.models import Equipo
from modulos.kraken.red.wol import normalize_mac


def equipment_dialog(page: ft.Page, equipo: Equipo | None, on_saved,  # propio
                     host: str = "", puertos: str | None = None, nombre: str | None = None):
    """on_saved(equipo) al guardar. host/puertos/nombre: valores sugeridos para uno nuevo."""
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

    def save(e=None):  # propio
        for campo in (txt_nombre, txt_host, txt_puertos, txt_mac):
            campo.error = None
        valores = dict(nombre=(txt_nombre.value or "").strip(),
                       host=(txt_host.value or "").strip().lower(),
                       puertos=(txt_puertos.value or "").strip() or None,
                       mac=None, notas=(txt_notas.value or "").strip() or None)
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
            tight=True, spacing=10,
            controls=[txt_nombre, txt_host, txt_puertos, txt_mac, txt_notas])),
        actions=[ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                 ft.FilledButton("Guardar", on_click=save)],
    ))

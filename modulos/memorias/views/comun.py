"""
Piezas que comparten las pantallas de Memorias.

  thumb(adjunto, tamaño)   miniatura (bytes) o un ícono si no hay
  tag_chip(etiqueta)       etiqueta de color chiquita
  show_photo(page, ...)    foto en grande (toca afuera para cerrar)

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft

from core.adjuntos import Adjunto
from modulos.memorias import imagenes


def thumb(adjunto: Adjunto | None, ancho: float | None, alto: float | None, radio: int = 10,
          on_click=None, cuadrado: bool = False) -> ft.Control:  # propio
    """
    Miniatura recortada para llenar el cuadro (como en la galería del celular).
    Va como imagen de FONDO del Container (DecorationImage, fit=COVER): así llena
    el cuadro aunque el ancho venga de la cuadrícula (cuadrado=True: alto = ancho).
    """
    datos = imagenes.read_thumbnail(adjunto.ruta) if adjunto else None
    return ft.Container(
        width=ancho, height=alto, border_radius=radio,
        aspect_ratio=1 if cuadrado else None,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        image=ft.DecorationImage(src=datos, fit=ft.BoxFit.COVER) if datos else None,
        alignment=ft.Alignment.CENTER,
        content=None if datos else ft.Icon(ft.Icons.IMAGE_OUTLINED, color=ft.Colors.OUTLINE),
        on_click=on_click,
    )


def tag_chip(etiqueta) -> ft.Control:  # propio
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=2), border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.2, etiqueta.color),
        content=ft.Text(etiqueta.nombre, size=11, color=etiqueta.color,
                        weight=ft.FontWeight.W_500),
    )


def show_photo(page: ft.Page, datos: bytes | None, titulo: str = ""):  # propio
    """La foto completa, del tamaño de la pantalla."""
    if not datos:
        return
    page.show_dialog(ft.AlertDialog(
        inset_padding=ft.Padding.all(8),
        content_padding=ft.Padding.all(0),
        title=ft.Text(titulo, size=14) if titulo else None,
        content=ft.Container(
            width=420, height=620,
            content=ft.InteractiveViewer(  # pellizcar para hacer zoom
                min_scale=1, max_scale=5,
                content=ft.Image(src=datos, fit=ft.BoxFit.CONTAIN),
            ),
        ),
        actions=[ft.TextButton("Cerrar", on_click=lambda e: page.pop_dialog())],
    ))

"""
Pincel: una "hoja de acetato" transparente encima de toda la app para marcar
con el dedo (o el mouse) antes de capturar o mientras grabas.

  page.overlay
   ├─ capa del pincel  ← GestureDetector + Canvas a pantalla completa
   ├─ barra de herramientas del pincel (colores, deshacer, borrar…)
   └─ botón flotante 📷

Como page.take_screenshot() captura también el overlay, los trazos salen en la
foto y en cada cuadro de la grabación.

Cómo se dibuja:
  on_pan_start  -> empieza un trazo nuevo (cv.Path con MoveTo en ese punto)
  on_pan_update -> le agrega LineTo al punto donde va el dedo
  Cada trazo es un cv.Path con su color; "Deshacer" quita el último.

Mientras el pincel está activo, la capa "se come" los toques: la app de abajo
no responde hasta que lo apagas.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import flet as ft
import flet.canvas as cv

COLORES = [ft.Colors.RED, ft.Colors.AMBER, ft.Colors.LIGHT_GREEN, ft.Colors.CYAN]
GROSOR = 5


class DrawLayer:
    def __init__(self, page: ft.Page):
        self.page = page
        self.color = COLORES[0]
        self.lienzo = cv.Canvas(shapes=[], expand=True)
        self._trazo: cv.Path | None = None

        # Capa a pantalla completa (left/top/right/bottom = 0 dentro del overlay).
        # bgcolor transparente: sin color, las zonas vacías no "agarran" el dedo.
        self.capa = ft.Container(
            left=0, top=0, right=0, bottom=0,
            bgcolor=ft.Colors.TRANSPARENT,
            content=ft.GestureDetector(
                content=self.lienzo,
                expand=True,
                drag_interval=16,  # ~60 actualizaciones por segundo como máximo
                on_pan_start=self._on_start,
                on_pan_update=self._on_move,
                on_pan_end=self._on_end,
            ),
        )

    # ==================================================================
    # Encender / apagar
    # ==================================================================
    @property
    def activo(self) -> bool:  # propio
        return self.capa in self.page.overlay

    def show(self, debajo_de: ft.Control):  # propio
        """Pone la capa en el overlay DEBAJO de 'debajo_de' (barra/botón encima)."""
        if not self.activo:
            self.page.overlay.insert(self.page.overlay.index(debajo_de), self.capa)

    def hide(self):  # propio
        """Quita la capa y borra los trazos."""
        if self.activo:
            self.page.overlay.remove(self.capa)
        self.clear(actualizar=False)

    # ==================================================================
    # Dibujar
    # ==================================================================
    def _paint(self) -> ft.Paint:  # propio
        return ft.Paint(
            color=self.color,
            stroke_width=GROSOR,
            style=ft.PaintingStyle.STROKE,
            stroke_cap=ft.StrokeCap.ROUND,     # puntas redondas
            stroke_join=ft.StrokeJoin.ROUND,   # esquinas redondas
        )

    def _on_start(self, e):  # propio
        x, y = e.local_position.x, e.local_position.y
        self._trazo = cv.Path([cv.Path.MoveTo(x, y), cv.Path.LineTo(x, y)], paint=self._paint())
        self.lienzo.shapes.append(self._trazo)
        self.lienzo.update()

    def _on_move(self, e):  # propio
        if self._trazo is None:
            return
        self._trazo.elements.append(cv.Path.LineTo(e.local_position.x, e.local_position.y))
        self.lienzo.update()

    def _on_end(self, e):  # propio
        self._trazo = None

    def set_color(self, color):  # propio
        self.color = color

    def undo(self):  # propio
        if self.lienzo.shapes:
            self.lienzo.shapes.pop()
            self.lienzo.update()

    def clear(self, actualizar: bool = True):  # propio
        self.lienzo.shapes.clear()
        self._trazo = None
        if actualizar and self.activo:
            self.lienzo.update()

    # ==================================================================
    # Controles para la barra de herramientas
    # ==================================================================
    def color_buttons(self, on_change=None) -> list[ft.Control]:  # propio
        """Circulitos de color; el elegido lleva borde blanco."""
        botones: list[ft.Control] = []

        def pick(color):  # propio
            self.set_color(color)
            for b, c in zip(botones, COLORES):
                b.border = ft.Border.all(3, ft.Colors.WHITE) if c == color else None
            if on_change:
                on_change()
            self.page.update()

        for c in COLORES:
            botones.append(
                ft.Container(
                    width=26, height=26, border_radius=13, bgcolor=c,
                    border=ft.Border.all(3, ft.Colors.WHITE) if c == self.color else None,
                    on_click=lambda e, col=c: pick(col),
                )
            )
        return botones

"""
Pestaña [Calendario] de la Agenda: cuántas tareas hay en un rango de tiempo.

  ◀  Septiembre 2026  ▶   [Hoy]
  [Día] [Semana] [Mes] [Año]
  [Todas] [Personal] [Familiar] [Trabajo] [Sin proyecto]   + Proyecto ▾
  38 tareas · 5 hechas · 2 vencidas

  Día     -> la lista de tareas de ese día (tocar = abrir la tarea;
             ○ = marcar hecha, ✓ = deshacer, con las reglas del chismoso)
  Semana  -> 7 renglones L..D con su conteo y las primeras tareas
  Mes     -> cuadrícula del mes; cada día con su número de tareas
  Año     -> los 12 meses completos en miniatura (mapa de calor)

Tocar un día (en Semana/Mes/Año) baja a la vista Día; tocar un mes en Año
abre ese Mes.

Deslizar ← → (con el dedo, o arrastrando con el mouse) cambia al siguiente /
anterior día, semana, mes o año, con animación de carrusel:

   dedo ←   [ Sept ]──sale a la izq.──►  [ Oct ] entra por la der.
   dedo →   [ Sept ]──sale a la der.──►  [ Ago ] entra por la izq.
 El conteo lo hace services.occurrences(): esta clase solo pinta.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio
import calendar
from datetime import date, timedelta

import flet as ft

from core.ui import notify, short_date
from modulos.agenda import services
from modulos.agenda.services import SIN_PROYECTO, Ocurrencia

DIAS_CORTOS = ["L", "M", "M", "J", "V", "S", "D"]
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES_LARGOS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Deslizar: cuánto hay que arrastrar (px) o qué tan rápido (px/s) para cambiar
DISTANCIA_MINIMA = 60
VELOCIDAD_MINIMA = 400
# Animación del carrusel: cuánto se corre (fracción del ancho) y cuánto tarda
DESPLAZAMIENTO = 0.35
ANIMACION = ft.Animation(160, ft.AnimationCurve.EASE_OUT)

MODOS = (("dia", "Día"), ("semana", "Semana"), ("mes", "Mes"), ("anio", "Año"))

COLOR_ESTADO = {
    "vencida": ft.Colors.RED,
    "pendiente": ft.Colors.PRIMARY,
    "hecha": ft.Colors.GREEN,
}


def _plural(n: int, singular: str, plural: str) -> str:  # propio
    return f"{n} {singular if n == 1 else plural}"


def _heat(n: int, maximo: int):  # propio
    """Color del día según cuántas tareas tiene (más tareas = más intenso)."""
    if n == 0:
        return None
    return ft.Colors.with_opacity(0.15 + 0.65 * min(n / max(maximo, 1), 1), ft.Colors.PRIMARY)


class CalendarPanel:
    def __init__(self, page: ft.Page, on_open_task, on_change):
        """
        on_open_task(tarea): abre el formulario de la tarea
        on_change():         pide a la Agenda que vuelva a pintar esta pestaña
        """
        self.page = page
        self.on_open_task = on_open_task
        self.on_change = on_change
        self.modo = "mes"
        self.ref = date.today()          # el día "de referencia" del rango
        self.tipo: str | None = None     # filtro tipo de proyecto
        self.proyecto_id: int | None = None

        # Zona deslizable: resumen + calendario. Es SIEMPRE el mismo Container
        # (solo cambia su content); así Flet puede animar su offset/opacity.
        self._dx = 0.0            # cuánto se ha arrastrado en este gesto
        self._animando = False    # evita encimar dos deslizadas
        self.cuerpo = ft.Container(
            bgcolor=ft.Colors.TRANSPARENT,  # con color, el hueco vacío también "agarra" el gesto
            offset=ft.Offset(0, 0),
            opacity=1,
            animate_offset=ANIMACION,
            animate_opacity=ANIMACION,
        )
        self.zona = ft.GestureDetector(
            content=self.cuerpo,
            on_horizontal_drag_start=self._on_drag_start,
            on_horizontal_drag_update=self._on_drag_update,
            on_horizontal_drag_end=self._on_drag_end,
        )

    # ==================================================================
    # Rango de fechas
    # ==================================================================
    def _range(self) -> tuple[date, date]:  # propio
        r = self.ref
        if self.modo == "dia":
            return r, r
        if self.modo == "semana":
            lunes = r - timedelta(days=r.weekday())
            return lunes, lunes + timedelta(days=6)
        if self.modo == "mes":
            return r.replace(day=1), r.replace(day=calendar.monthrange(r.year, r.month)[1])
        return date(r.year, 1, 1), date(r.year, 12, 31)

    def _title(self) -> str:  # propio
        inicio, fin = self._range()
        if self.modo == "dia":
            return f"{DIAS[inicio.weekday()]} {short_date(inicio)}"
        if self.modo == "semana":
            return f"{inicio.day} {short_date(inicio).split()[1]} – {short_date(fin)}"
        if self.modo == "mes":
            return f"{MESES_LARGOS[inicio.month - 1]} {inicio.year}"
        return str(inicio.year)

    def move(self, paso: int):  # propio
        """◀ = -1, ▶ = +1 (un día, una semana, un mes o un año según el modo)."""
        r = self.ref
        if self.modo == "dia":
            self.ref = r + timedelta(days=paso)
        elif self.modo == "semana":
            self.ref = r + timedelta(days=7 * paso)
        elif self.modo == "mes":
            total = r.year * 12 + (r.month - 1) + paso
            anio, mes = divmod(total, 12)
            self.ref = date(anio, mes + 1, 1)
        else:
            self.ref = date(r.year + paso, 1, 1)
        self.on_change()

    # ==================================================================
    # Deslizar  (GestureDetector -> _slide)
    # ==================================================================
    def _on_drag_start(self, e):  # propio
        self._dx = 0.0

    def _on_drag_update(self, e):  # propio
        # primary_delta: cuánto se movió en X desde el evento anterior (+ = derecha)
        self._dx += e.primary_delta or 0

    def _on_drag_end(self, e):  # propio
        """Suficiente distancia o velocidad -> cambia de periodo."""
        dx, self._dx = self._dx, 0.0
        velocidad = e.primary_velocity or 0
        if dx <= -DISTANCIA_MINIMA or velocidad <= -VELOCIDAD_MINIMA:
            self.page.run_task(self._slide, 1)    # dedo a la izquierda -> siguiente
        elif dx >= DISTANCIA_MINIMA or velocidad >= VELOCIDAD_MINIMA:
            self.page.run_task(self._slide, -1)   # dedo a la derecha -> anterior

    async def _slide(self, paso: int):  # propio
        """
        Carrusel en 3 tiempos (paso = +1 siguiente, -1 anterior):
          1. el actual sale hacia el lado del dedo y se desvanece (animado)
          2. se cambia el periodo y el nuevo se coloca, invisible, del otro lado
             (sin animación, para que no "viaje" de un lado al otro)
          3. el nuevo entra al centro (animado)
        """
        if self._animando:
            return
        self._animando = True
        c = self.cuerpo
        try:
            c.offset = ft.Offset(-DESPLAZAMIENTO * paso, 0)
            c.opacity = 0
            self.page.update()
            await asyncio.sleep(ANIMACION.duration / 1000)

            c.animate_offset = c.animate_opacity = None
            c.offset = ft.Offset(DESPLAZAMIENTO * paso, 0)
            self.move(paso)            # repinta (on_change -> page.update)
            await asyncio.sleep(0.03)

            c.animate_offset = c.animate_opacity = ANIMACION
            c.offset = ft.Offset(0, 0)
            c.opacity = 1
            self.page.update()
        finally:
            # Pase lo que pase, que no se quede invisible ni bloqueado
            c.animate_offset = c.animate_opacity = ANIMACION
            c.offset, c.opacity = ft.Offset(0, 0), 1
            self._animando = False

    def go(self, modo: str, fecha: date | None = None):  # propio
        self.modo = modo
        if fecha is not None:
            self.ref = fecha
        self.on_change()

    # ==================================================================
    # Filtros
    # ==================================================================
    def set_tipo(self, tipo: str | None):  # propio
        self.tipo = tipo
        self.proyecto_id = None  # el proyecto elegido puede no ser de ese tipo
        self.on_change()

    def _on_proyecto(self, e):  # propio
        valor = e.control.value
        self.proyecto_id = int(valor) if valor and valor != "0" else None
        self.on_change()

    def _filters(self) -> list[ft.Control]:  # propio
        from modulos.proyectos.models import TIPO_PROYECTO_SELECTION, Proyecto

        opciones = [(None, "Todas"), *TIPO_PROYECTO_SELECTION.items(), (SIN_PROYECTO, "Sin proyecto")]
        chips = ft.Row(
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
            controls=[
                ft.Chip(
                    label=ft.Text(texto),
                    selected=self.tipo == clave,
                    on_select=lambda e, c=clave: self.set_tipo(c),
                )
                for clave, texto in opciones
            ],
        )
        controles: list[ft.Control] = [chips]

        # El selector de proyecto solo lista los del tipo elegido
        if self.tipo != SIN_PROYECTO:
            proyectos = Proyecto.search_by_tipo(self.tipo)
            if proyectos:
                controles.append(
                    ft.Dropdown(
                        label="Proyecto",
                        dense=True,
                        expand=True,
                        value=str(self.proyecto_id or 0),
                        options=[ft.DropdownOption(key="0", text="Todos los proyectos")]
                        + [ft.DropdownOption(key=str(p.id), text=p.nombre) for p in proyectos],
                        on_select=self._on_proyecto,
                    )
                )
        return controles

    # ==================================================================
    # Pintar
    # ==================================================================
    def controls(self) -> list[ft.Control]:  # propio
        inicio, fin = self._range()
        hoy = date.today()
        ocurrencias = services.occurrences(inicio, fin, self.tipo, self.proyecto_id, hoy)

        controles: list[ft.Control] = [
            self._navigation(),
            ft.Row(
                spacing=6,
                controls=[
                    ft.Chip(
                        label=ft.Text(texto),
                        selected=self.modo == clave,
                        on_select=lambda e, c=clave: self.go(c),
                    )
                    for clave, texto in MODOS
                ],
            ),
            *self._filters(),
        ]

        # Lo que se desliza: resumen + calendario del modo elegido
        cuerpo: list[ft.Control] = [self._summary(ocurrencias)]
        if self.modo == "dia":
            cuerpo += self._day(ocurrencias)
            cuerpo.append(ft.Container(height=160))  # espacio para deslizar aunque haya pocas
        elif self.modo == "semana":
            cuerpo += self._week(inicio, ocurrencias, hoy)
        elif self.modo == "mes":
            conteo = services.count_by_day(ocurrencias)
            vencidos = {o.fecha for o in ocurrencias if o.estado == "vencida"}
            cuerpo.append(self._month(inicio, conteo, vencidos, hoy))
            cuerpo.append(self._legend())
        else:
            cuerpo += self._year(inicio.year, ocurrencias, hoy)

        self.cuerpo.content = ft.Column(cuerpo, spacing=6)
        controles.append(self.zona)
        return controles

    def _navigation(self) -> ft.Control:  # propio
        return ft.Row(
            controls=[
                ft.IconButton(ft.Icons.CHEVRON_LEFT,
                              on_click=lambda e: self.page.run_task(self._slide, -1)),
                ft.Text(self._title(), size=17, weight=ft.FontWeight.BOLD, expand=True,
                        text_align=ft.TextAlign.CENTER),
                ft.IconButton(ft.Icons.CHEVRON_RIGHT,
                              on_click=lambda e: self.page.run_task(self._slide, 1)),
                ft.TextButton("Hoy", on_click=lambda e: self.go(self.modo, date.today())),
            ],
        )

    @staticmethod
    def _summary(ocurrencias: list[Ocurrencia]) -> ft.Control:  # propio
        """'38 tareas · 5 hechas · 2 vencidas' (lo que más importa del rango)."""
        total = len(ocurrencias)
        hechas = sum(1 for o in ocurrencias if o.estado == "hecha")
        vencidas = sum(1 for o in ocurrencias if o.estado == "vencida")
        partes = [ft.Text(_plural(total, "tarea", "tareas"), weight=ft.FontWeight.BOLD)]
        if hechas:
            partes.append(ft.Text(f"· {_plural(hechas, 'hecha', 'hechas')}", color=ft.Colors.GREEN))
        if vencidas:
            partes.append(ft.Text(f"· {_plural(vencidas, 'vencida', 'vencidas')}",
                                  color=ft.Colors.RED))
        # Pista de que se puede deslizar a los lados
        partes += [ft.Container(expand=True),
                   ft.Icon(ft.Icons.SWIPE, size=16, color=ft.Colors.OUTLINE,
                           tooltip="Desliza ← → para cambiar")]
        return ft.Container(padding=ft.Padding.symmetric(vertical=4),
                            content=ft.Row(partes, spacing=6))

    @staticmethod
    def _legend() -> ft.Control:  # propio
        return ft.Row(
            alignment=ft.MainAxisAlignment.END,
            spacing=4,
            controls=[
                ft.Text("menos", size=11, color=ft.Colors.OUTLINE),
                *[ft.Container(width=14, height=14, border_radius=3, bgcolor=_heat(n, 4))
                  for n in (1, 2, 3, 4)],
                ft.Text("más", size=11, color=ft.Colors.OUTLINE),
                ft.Container(width=8),
                ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.RED),
                ft.Text("vencida", size=11, color=ft.Colors.OUTLINE),
            ],
        )

    # --- Día ----------------------------------------------------------
    def _day(self, ocurrencias: list[Ocurrencia]) -> list[ft.Control]:  # propio
        if not ocurrencias:
            return [ft.Text("Sin tareas este día.", italic=True)]
        return [self._task_row(o) for o in ocurrencias]

    def _task_row(self, o: Ocurrencia) -> ft.Control:  # propio
        t = o.tarea
        color = COLOR_ESTADO[o.estado]
        detalle = [x for x in (t.horario, f"📁 {t.proyecto.nombre}" if t.proyecto else "",
                               f"↻ {t.frecuencia_label}" if t.recurrente else "") if x]
        return ft.Container(
            border_radius=10,
            padding=ft.Padding.only(right=12, top=4, bottom=4),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border=ft.Border.only(left=ft.BorderSide(4, color)),
            ink=True,
            on_click=lambda e, x=t: self.on_open_task(x),
            content=ft.Row(
                spacing=0,
                controls=[
                    self._check_button(o, color),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                    ft.Text(
                        t.titulo, weight=ft.FontWeight.W_500,
                        color=ft.Colors.OUTLINE if o.estado == "hecha" else None,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)
                        if o.estado == "hecha" else None,
                    ),
                    *([ft.Text(" · ".join(detalle), size=12, color=ft.Colors.OUTLINE)]
                      if detalle else []),
                        ],
                    ),
                ],
            ),
        )

    # --- Marcar / desmarcar (vista Día) ------------------------------------
    def _check_button(self, o: Ocurrencia, color) -> ft.Control:  # propio
        """
        ○  pendiente que toca ahorita      -> marcar hecha
        ○  (tenue) una futura de recurrente -> avisa cuál va primero
        ✓  la última vez que la marcaste    -> deshacer
        ✓  (tenue) una vez anterior         -> avisa que solo la última se deshace
        """
        if o.estado == "hecha":
            icono, activo = ft.Icons.CHECK_CIRCLE, o.deshacible
            ayuda = "Deshacer" if activo else "Solo se deshace la última vez que la marcaste"
        else:
            icono, activo = ft.Icons.RADIO_BUTTON_UNCHECKED, o.marcable
            ayuda = "Marcar como hecha" if activo else f"Primero va la del {short_date(o.tarea.fecha)}"
        return ft.IconButton(
            icono,
            icon_color=color if activo else ft.Colors.with_opacity(0.35, color),
            tooltip=ayuda,
            on_click=lambda e, x=o: self._toggle(x),
        )

    def _toggle(self, o: Ocurrencia):  # propio
        t = o.tarea
        if o.estado == "hecha":
            if not o.deshacible:
                notify(self.page, "Solo puedes deshacer la última vez que la marcaste")
                return
            services.undo(o.cumplimiento_id)
            notify(self.page, f"«{t.titulo}» regresó a pendientes")
            self.on_change()
            return

        if not o.marcable:
            notify(self.page, f"Primero marca la del {short_date(t.fecha)}")
            return
        # Misma acción que el chismoso (incluye ofrecer el avance a la bitácora).
        # Import aquí: chismoso.py importa este archivo, así no se enciclan.
        from modulos.agenda.views.chismoso import complete_task

        complete_task(self.page, t, on_done=self.on_change)

    # --- Semana -------------------------------------------------------
    def _week(self, lunes: date, ocurrencias: list[Ocurrencia], hoy: date) -> list[ft.Control]:  # propio
        por_dia: dict[date, list[Ocurrencia]] = {}
        for o in ocurrencias:
            por_dia.setdefault(o.fecha, []).append(o)

        filas = []
        for i in range(7):
            dia = lunes + timedelta(days=i)
            del_dia = por_dia.get(dia, [])
            titulos = [o.tarea.titulo for o in del_dia[:3]]
            if len(del_dia) > 3:
                titulos.append(f"+{len(del_dia) - 3} más")
            vencidas = any(o.estado == "vencida" for o in del_dia)
            filas.append(
                ft.Container(
                    border_radius=10,
                    padding=ft.Padding.all(10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    border=ft.Border.all(2, ft.Colors.PRIMARY) if dia == hoy else None,
                    ink=True,
                    on_click=lambda e, d=dia: self.go("dia", d),
                    content=ft.Row(
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Column(
                                width=44,
                                spacing=0,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(DIAS[i], size=12, color=ft.Colors.OUTLINE),
                                    ft.Text(str(dia.day), size=20, weight=ft.FontWeight.BOLD),
                                ],
                            ),
                            ft.Column(
                                expand=True,
                                spacing=0,
                                controls=[ft.Text(x, size=12, max_lines=1,
                                                  overflow=ft.TextOverflow.ELLIPSIS)
                                          for x in titulos]
                                or [ft.Text("—", size=12, color=ft.Colors.OUTLINE)],
                            ),
                            self._badge(len(del_dia), vencidas),
                        ],
                    ),
                )
            )
        return filas

    @staticmethod
    def _badge(n: int, vencidas: bool) -> ft.Control:  # propio
        """Circulito con el número de tareas (rojo si hay vencidas)."""
        if n == 0:
            return ft.Container(width=28)
        return ft.Container(
            width=28, height=28, border_radius=14,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.RED if vencidas else ft.Colors.PRIMARY,
            content=ft.Text(str(n), size=12, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.WHITE if vencidas else ft.Colors.ON_PRIMARY),
        )

    # --- Mes ----------------------------------------------------------
    def _month(self, primero: date, conteo: dict[date, int], vencidos: set[date],  # propio
               hoy: date, mini: bool = False, maximo: int | None = None) -> ft.Control:
        """
        Cuadrícula L..D del mes. mini=True es la versión chiquita del Año
        (solo color, sin números de tareas).
        """
        maximo = maximo or max(conteo.values(), default=1)
        alto = 22 if mini else 52
        semanas = calendar.Calendar(firstweekday=0).monthdatescalendar(primero.year, primero.month)

        def cell(dia: date) -> ft.Control:  # propio
            if dia.month != primero.month:
                return ft.Container(expand=True, height=alto)  # día de otro mes: vacío
            n = conteo.get(dia, 0)
            textos: list[ft.Control] = [
                ft.Text(str(dia.day), size=9 if mini else 13,
                        weight=ft.FontWeight.BOLD if dia == hoy else None),
            ]
            if not mini and n:
                textos.append(ft.Text(str(n), size=11, weight=ft.FontWeight.BOLD,
                                      color=ft.Colors.RED if dia in vencidos else None))
            return ft.Container(
                expand=True,
                height=alto,
                border_radius=3 if mini else 8,
                bgcolor=_heat(n, maximo),
                border=ft.Border.all(1.5 if mini else 2, ft.Colors.PRIMARY) if dia == hoy
                else ft.Border.all(1, ft.Colors.RED) if (dia in vencidos and not mini) else None,
                alignment=ft.Alignment.CENTER,
                ink=not mini,
                on_click=None if mini else (lambda e, d=dia: self.go("dia", d)),
                content=ft.Column(textos, spacing=0, tight=True,
                                  horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )

        encabezado = ft.Row(
            spacing=2,
            controls=[ft.Container(expand=True, alignment=ft.Alignment.CENTER,
                                   content=ft.Text(d, size=9 if mini else 12,
                                                   color=ft.Colors.OUTLINE))
                      for d in DIAS_CORTOS],
        )
        return ft.Column(
            spacing=2,
            controls=[encabezado]
            + [ft.Row([cell(d) for d in semana], spacing=2) for semana in semanas],
        )

    # --- Año ----------------------------------------------------------
    def _year(self, anio: int, ocurrencias: list[Ocurrencia], hoy: date) -> list[ft.Control]:  # propio
        conteo = services.count_by_day(ocurrencias)
        maximo = max(conteo.values(), default=1)  # mismo color para todo el año
        por_mes = [0] * 12
        for o in ocurrencias:
            por_mes[o.fecha.month - 1] += 1

        tarjetas = []
        for mes in range(1, 13):
            primero = date(anio, mes, 1)
            del_mes = {d: n for d, n in conteo.items() if d.month == mes}
            tarjetas.append(
                ft.Container(
                    col=6,  # dos meses por fila
                    padding=8,
                    border_radius=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    ink=True,
                    on_click=lambda e, p=primero: self.go("mes", p),
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Row([
                                ft.Text(MESES_LARGOS[mes - 1], weight=ft.FontWeight.BOLD,
                                        expand=True, size=13),
                                ft.Text(str(por_mes[mes - 1]), size=12,
                                        color=ft.Colors.OUTLINE),
                            ]),
                            self._month(primero, del_mes, set(), hoy, mini=True, maximo=maximo),
                        ],
                    ),
                )
            )
        return [ft.ResponsiveRow(spacing=8, run_spacing=8, controls=tarjetas)]

"""
Pantallas de Movimientos (detalle de un periodo):
  /movimientos -> lista de movimientos del periodo abierto
  /movimiento  -> un movimiento: nuevo, ver (solo lectura) o editar

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]
"""
from datetime import date

import flet as ft

from models import (
    INVERSION_SELECTION,
    PLATAFORMA_SELECTION,
    TIPO_SELECTION,
    Movimiento,
    Periodo,
)
from views.comun import (
    MESES,
    CampoFecha,
    aviso,
    boton_agregar,
    boton_editar,
    boton_eliminar,
    confirmar,
    cuadro_icono,
    deslizar_para_eliminar,
    fecha_corta,
    opciones_dropdown,
)

# Ícono y color de cada tipo de movimiento
ESTILO_TIPO = {
    "deposito": (ft.Icons.SAVINGS, ft.Colors.GREEN),
    "retiro": (ft.Icons.ARROW_OUTWARD, ft.Colors.ORANGE),
    "rendimiento": (ft.Icons.TRENDING_UP, ft.Colors.TEAL),
}


class MovimientosVista:
    def __init__(self, page: ft.Page, al_ver_periodo):
        """
        al_ver_periodo: función que se llama al tocar el engrane
        (la pantalla de periodos se encarga de mostrar su detalle).
        """
        self.page = page
        self.al_ver_periodo = al_ver_periodo
        self.periodo: Periodo | None = None      # periodo abierto
        self.registro: Movimiento | None = None  # movimiento mostrado en el formulario
        self.modo = "nuevo"                      # "nuevo" | "ver" | "editar"

        self._crear_formulario()
        self._crear_lista()

    # ==================================================================
    # Lista
    # ==================================================================
    def _crear_lista(self):
        # ListView: lista con scroll, ideal para muchos registros
        self.lista = ft.ListView(
            expand=True,
            spacing=4,
            # Espacio al final para que el botón verde no tape el último registro
            padding=ft.Padding.only(bottom=90),
        )
        self.lbl_vacio = ft.Text("Este periodo aún no tiene movimientos", italic=True)
        self.lbl_titulo_lista = ft.Text("Movimientos")  # nombre del periodo

        self.vista_lista = ft.View(
            route="/movimientos",
            appbar=ft.AppBar(
                title=self.lbl_titulo_lista,
                actions=[
                    # Engrane: ver los datos del periodo
                    ft.IconButton(
                        ft.Icons.SETTINGS,
                        tooltip="Datos del periodo",
                        on_click=lambda e: self.al_ver_periodo(self.periodo),
                    ),
                ],
            ),
            floating_action_button=boton_agregar("Nuevo movimiento", self.nuevo),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_vacio, self.lista]),
                )
            ],
        )

    def abrir_periodo(self, periodo: Periodo):
        """Lo llama la pantalla de Periodos al tocar una línea."""
        self.periodo = periodo
        self.page.navigate("/movimientos")

    def cargar(self):
        # Se relee el periodo por si se editó (nombre o fechas) desde su detalle
        self.periodo = Periodo.get(self.periodo.id)
        if self.periodo is None:  # se eliminó
            return
        self.lbl_titulo_lista.value = self.periodo.nombre
        movimientos = Movimiento.search_by_periodo(self.periodo.id)
        self.lista.controls = [self._fila(m) for m in movimientos]
        self.lbl_vacio.visible = not movimientos

    def _fila(self, m: Movimiento) -> ft.Control:
        """Una línea de la lista, al estilo de la imagen de referencia."""
        icono, color = ESTILO_TIPO.get(m.tipo, (ft.Icons.RECEIPT_LONG, ft.Colors.GREY))

        subtitulo = m.inversion_label
        if m.comentarios:
            subtitulo += f" · {m.comentarios}"

        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,  # efecto al tocar
            on_click=lambda e, mov=m: self.ver(mov),  # tocar la línea -> ver detalle
            content=ft.Row(
                spacing=10,
                controls=[
                    # Fecha: mes arriba, día abajo
                    ft.Column(
                        width=36,
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(MESES[m.fecha.month - 1], size=12),
                            ft.Text(str(m.fecha.day), size=16),
                        ],
                    ),
                    cuadro_icono(icono, color),
                    # Plataforma + inversión/comentarios (ocupa el espacio libre)
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(m.plataforma_label, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(
                                subtitulo,
                                size=12,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    # Tipo y monto a la derecha, con el color del tipo
                    ft.Column(
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                        controls=[
                            ft.Text(m.tipo_label.lower(), size=12, color=color),
                            ft.Text(f"${m.monto:,.2f}", size=15, color=color),
                        ],
                    ),
                ],
            ),
        )
        # ◄── deslizar a la izquierda: eliminar (con confirmación)
        return deslizar_para_eliminar(
            self.page,
            key=f"movimiento-{m.id}",
            contenido=linea,
            titulo="Eliminar movimiento",
            mensaje=self._mensaje_eliminar(m),
            al_eliminar=lambda mov=m: self._eliminar(mov),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _crear_formulario(self):
        # Filas que contienen los desplegables (se rellenan en _nuevos_desplegables)
        self.fila_inversion = ft.Row()
        self.fila_plataforma = ft.Row()
        self.fila_tipo = ft.Row()
        self._nuevos_desplegables()

        self.txt_monto = ft.TextField(
            label="Monto",
            prefix="$ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"^\d*\.?\d{0,2}$", allow=True),
        )
        self.campo_fecha = CampoFecha(self.page, "Fecha")
        self.txt_comentarios = ft.TextField(label="Comentarios", max_length=255)

        self.lbl_titulo_form = ft.Text("Nuevo movimiento")  # va en la barra superior
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.guardar)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancelar)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        # Lápiz y bote en la barra superior (solo en modo "ver")
        self.btn_barra_editar = boton_editar(self.editar)
        self.btn_barra_eliminar = boton_eliminar(self.confirmar_eliminar)

        self.vista_form = ft.View(
            route="/movimiento",
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,  # flecha de regreso automática
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.fila_inversion,
                            self.txt_monto,
                            self.fila_plataforma,
                            self.campo_fecha.fila,
                            self.fila_tipo,
                            self.txt_comentarios,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._aplicar_modo()

    def _nuevos_desplegables(self):
        """
        Crea los Dropdown desde cero y los pone en su fila.

        ¿Por qué no solo `dd.value = None`? Porque el Dropdown de Flet, al
        regresarle el valor a None, sigue MOSTRANDO el texto anterior
        (en Python el valor sí es None, por eso marcaba "Requerido").
        Un Dropdown nuevo siempre arranca vacío.
        """
        self.dd_inversion = ft.Dropdown(
            label="Inversión", options=opciones_dropdown(INVERSION_SELECTION), expand=True
        )
        self.dd_plataforma = ft.Dropdown(
            label="Plataforma", options=opciones_dropdown(PLATAFORMA_SELECTION), expand=True
        )
        self.dd_tipo = ft.Dropdown(
            label="Tipo", options=opciones_dropdown(TIPO_SELECTION), expand=True
        )
        self.fila_inversion.controls = [self.dd_inversion]
        self.fila_plataforma.controls = [self.dd_plataforma]
        self.fila_tipo.controls = [self.dd_tipo]

    def _aplicar_modo(self):
        """Ajusta campos, botones y título según self.modo."""
        lectura = self.modo == "ver"

        for dd in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            dd.disabled = lectura
        for txt in (self.txt_monto, self.txt_comentarios):
            txt.read_only = lectura
        self.campo_fecha.habilitar(not lectura)

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo movimiento"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Movimiento"
        else:
            self.lbl_titulo_form.value = "Editar movimiento"
            self.btn_guardar.content = "Actualizar"

    def _fecha_por_defecto(self) -> date:
        """Hoy, pero ajustado para que quede dentro del periodo abierto."""
        hoy = date.today()
        if self.periodo is None:
            return hoy
        return min(max(hoy, self.periodo.fecha_inicio), self.periodo.fecha_fin)

    def _llenar(self, mov: Movimiento):
        """Pasa los datos del registro a los campos."""
        self.dd_inversion.value = mov.inversion
        self.txt_monto.value = f"{mov.monto:.2f}"
        self.dd_plataforma.value = mov.plataforma
        self.dd_tipo.value = mov.tipo
        self.txt_comentarios.value = mov.comentarios or ""
        self.campo_fecha.asignar(mov.fecha)

    def limpiar_errores(self):
        for campo in (self.dd_inversion, self.txt_monto, self.dd_plataforma,
                      self.dd_tipo, self.campo_fecha.txt):
            campo.error_text = None

    def limpiar_formulario(self):
        self.limpiar_errores()
        self._nuevos_desplegables()  # ver la explicación en ese método
        self.txt_monto.value = ""
        self.txt_comentarios.value = ""
        self.campo_fecha.asignar(self._fecha_por_defecto())
        self.registro = None
        self.modo = "nuevo"
        self._aplicar_modo()

    def _preparar_calendario(self):
        # Solo se pueden elegir fechas dentro del periodo abierto
        self.campo_fecha.limitar(self.periodo.fecha_inicio, self.periodo.fecha_fin)

    # --- Acciones -------------------------------------------------------
    def nuevo(self, e=None):
        """Botón verde: abre el formulario vacío, listo para capturar."""
        self.limpiar_formulario()
        self._preparar_calendario()
        self.page.navigate("/movimiento")

    def ver(self, mov: Movimiento):
        """Tocar una línea: muestra el movimiento en solo lectura."""
        self.limpiar_errores()
        self.registro = mov
        self._llenar(mov)
        self._preparar_calendario()
        self.modo = "ver"
        self._aplicar_modo()
        self.page.navigate("/movimiento")

    def editar(self, e=None):
        """Lápiz: habilita los campos del movimiento mostrado."""
        self.modo = "editar"
        self._aplicar_modo()
        self.page.update()

    def cancelar(self, e=None):
        if self.modo == "editar":
            # Descarta los cambios: vuelve a leer el registro y regresa a "ver"
            self.limpiar_errores()
            self.registro = Movimiento.get(self.registro.id)
            self._llenar(self.registro)
            self.modo = "ver"
            self._aplicar_modo()
            self.page.update()
        else:
            self.limpiar_formulario()
            self.page.navigate("/movimientos")

    def guardar(self, e=None):
        self.limpiar_errores()
        faltantes = False
        for campo in (self.dd_inversion, self.dd_plataforma, self.dd_tipo):
            if not campo.value:
                campo.error_text = "Requerido"
                faltantes = True
        try:
            monto = float(self.txt_monto.value)
            if monto <= 0:
                raise ValueError
        except (TypeError, ValueError):
            self.txt_monto.error_text = "Monto inválido"
            faltantes = True

        # La fecha debe caer dentro del periodo
        periodo = self.periodo
        if not (periodo.fecha_inicio <= self.campo_fecha.valor <= periodo.fecha_fin):
            self.campo_fecha.txt.error_text = (
                f"Debe estar entre {fecha_corta(periodo.fecha_inicio)} "
                f"y {fecha_corta(periodo.fecha_fin)}"
            )
            faltantes = True

        if faltantes:
            self.page.update()
            return

        valores = dict(
            inversion=self.dd_inversion.value,
            monto=monto,
            plataforma=self.dd_plataforma.value,
            fecha=self.campo_fecha.valor,
            tipo=self.dd_tipo.value,
            comentarios=(self.txt_comentarios.value or "").strip() or None,
            periodo_id=periodo.id,
        )
        try:
            if self.modo == "nuevo":
                Movimiento.create(**valores)
            else:
                self.registro = Movimiento.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            aviso(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.limpiar_formulario()
            aviso(self.page, "Movimiento guardado")
            self.page.navigate("/movimientos")  # regresa a la lista del periodo
        else:
            # Se queda en el registro, ahora en solo lectura
            self._llenar(self.registro)
            self.modo = "ver"
            self._aplicar_modo()
            aviso(self.page, "Movimiento actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _mensaje_eliminar(self, mov: Movimiento) -> str:
        return (
            f"¿Seguro que deseas eliminar el {mov.tipo_label.lower()} de "
            f"${mov.monto:,.2f} en {mov.plataforma_label} ({mov.fecha.isoformat()})?"
        )

    def confirmar_eliminar(self, e=None):
        """Bote de la barra: elimina el movimiento mostrado, con confirmación."""
        mov = self.registro

        def eliminar():
            if self._eliminar(mov):
                self.limpiar_formulario()
                self.page.navigate("/movimientos")

        confirmar(self.page, "Eliminar movimiento", self._mensaje_eliminar(mov), eliminar)

    def _eliminar(self, mov: Movimiento) -> bool:
        """Borra el movimiento y refresca la lista. Regresa True si se borró."""
        try:
            Movimiento.delete(mov.id)
        except Exception as ex:  # noqa: BLE001
            aviso(self.page, f"Error al eliminar: {ex}")
            return False
        self.cargar()
        aviso(self.page, "Movimiento eliminado")
        self.page.update()
        return True

"""
Pantallas de Periodos (cabecera de los movimientos):
  /                    -> lista de periodos (pantalla principal)
  /periodo             -> nuevo periodo (desde el botón verde)
  /movimientos/periodo -> datos del periodo abierto (desde el engrane)

Modos del formulario (como en Odoo):
  "nuevo"  -> campos editables, [Guardar] [Cancelar]
  "ver"    -> solo lectura, en la barra: ✏ editar  🗑 eliminar
  "editar" -> campos editables, [Actualizar] [Cancelar = descartar cambios]
"""
import calendar
from datetime import date

import flet as ft

from models import Periodo
from views.comun import (
    CampoFecha,
    aviso,
    boton_agregar,
    boton_editar,
    boton_eliminar,
    confirmar,
    cuadro_icono,
    deslizar_para_eliminar,
    fecha_corta,
)


class PeriodosVista:
    def __init__(self, page: ft.Page, al_abrir_periodo):
        """
        al_abrir_periodo: función que se llama al tocar un periodo
        (la pantalla de movimientos se encarga de mostrarlo).
        """
        self.page = page
        self.al_abrir_periodo = al_abrir_periodo
        self.registro: Periodo | None = None  # periodo mostrado en el formulario
        self.modo = "nuevo"                   # "nuevo" | "ver" | "editar"

        self._crear_formulario()
        self._crear_lista()

    # ==================================================================
    # Lista
    # ==================================================================
    def _crear_lista(self):
        self.lista = ft.ListView(
            expand=True,
            spacing=4,
            padding=ft.Padding.only(bottom=90),  # espacio para el botón verde
        )
        self.lbl_vacio = ft.Text(
            "Aún no hay periodos. Crea uno con el botón verde.", italic=True
        )

        self.vista_lista = ft.View(
            route="/",
            appbar=ft.AppBar(
                title=ft.Text("Periodos"),
                actions=[
                    # Engrane: abre la pantalla de ajustes
                    ft.IconButton(
                        ft.Icons.SETTINGS,
                        tooltip="Ajustes",
                        on_click=lambda e: self.page.navigate("/ajustes"),
                    ),
                ],
            ),
            floating_action_button=boton_agregar("Nuevo periodo", self.nuevo),
            controls=[
                ft.SafeArea(
                    expand=True,
                    content=ft.Column(expand=True, controls=[self.lbl_vacio, self.lista]),
                )
            ],
        )

    def cargar(self):
        periodos = Periodo.search_all()
        cantidades = Periodo.contar_movimientos()
        self.lista.controls = [self._fila(p, cantidades.get(p.id, 0)) for p in periodos]
        self.lbl_vacio.visible = not periodos

    def _fila(self, per: Periodo, cantidad: int) -> ft.Control:
        """Una línea de la lista de periodos. Al tocarla se abre el periodo."""
        texto_cantidad = "1 movimiento" if cantidad == 1 else f"{cantidad} movimientos"
        linea = ft.Container(
            padding=ft.Padding.symmetric(vertical=6),
            border_radius=8,
            ink=True,  # efecto al tocar
            on_click=lambda e, p=per: self.al_abrir_periodo(p),
            content=ft.Row(
                spacing=10,
                controls=[
                    cuadro_icono(ft.Icons.CALENDAR_MONTH, ft.Colors.BLUE),
                    ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            ft.Text(per.nombre, size=16, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{fecha_corta(per.fecha_inicio)} – {fecha_corta(per.fecha_fin)}",
                                size=12,
                            ),
                            ft.Text(texto_cantidad, size=12, color=ft.Colors.OUTLINE),
                        ],
                    ),
                ],
            ),
        )
        # ◄── deslizar a la izquierda: eliminar (con confirmación), igual que movimientos
        return deslizar_para_eliminar(
            self.page,
            key=f"periodo-{per.id}",
            contenido=linea,
            titulo="Eliminar periodo",
            mensaje=self._mensaje_eliminar(per, cantidad),
            al_eliminar=lambda p=per: self._eliminar(p),
        )

    # ==================================================================
    # Formulario
    # ==================================================================
    def _crear_formulario(self):
        self.txt_nombre = ft.TextField(label="Nombre", max_length=100)
        self.campo_inicio = CampoFecha(self.page, "Fecha inicio")
        self.campo_fin = CampoFecha(self.page, "Fecha fin")

        self.lbl_titulo_form = ft.Text("Nuevo periodo")  # va en la barra superior
        self.btn_guardar = ft.Button("Guardar", icon=ft.Icons.SAVE, on_click=self.guardar)
        btn_cancelar = ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, on_click=self.cancelar)
        self.fila_botones = ft.Row([self.btn_guardar, btn_cancelar])

        # Lápiz y bote en la barra superior (solo en modo "ver")
        self.btn_barra_editar = boton_editar(self.editar)
        self.btn_barra_eliminar = boton_eliminar(self.confirmar_eliminar)

        self.vista_form = ft.View(
            route="/periodo",  # main.py la ajusta: /periodo o /movimientos/periodo
            appbar=ft.AppBar(
                title=self.lbl_titulo_form,
                actions=[self.btn_barra_editar, self.btn_barra_eliminar],
            ),
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.SafeArea(
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            self.txt_nombre,
                            self.campo_inicio.fila,
                            self.campo_fin.fila,
                            self.fila_botones,
                        ],
                    )
                )
            ],
        )
        self._aplicar_modo()

    def _aplicar_modo(self):
        """Ajusta campos, botones y título según self.modo."""
        lectura = self.modo == "ver"

        self.txt_nombre.read_only = lectura
        self.campo_inicio.habilitar(not lectura)
        self.campo_fin.habilitar(not lectura)

        self.btn_barra_editar.visible = lectura
        self.btn_barra_eliminar.visible = lectura
        self.fila_botones.visible = not lectura

        if self.modo == "nuevo":
            self.lbl_titulo_form.value = "Nuevo periodo"
            self.btn_guardar.content = "Guardar"
        elif self.modo == "ver":
            self.lbl_titulo_form.value = "Periodo"
        else:
            self.lbl_titulo_form.value = "Editar periodo"
            self.btn_guardar.content = "Actualizar"

    def _llenar(self, per: Periodo):
        """Pasa los datos del registro a los campos."""
        self.txt_nombre.value = per.nombre
        self.campo_inicio.asignar(per.fecha_inicio)
        self.campo_fin.asignar(per.fecha_fin)

    def limpiar_errores(self):
        self.txt_nombre.error_text = None
        self.campo_fin.txt.error_text = None

    def limpiar_formulario(self):
        """Por defecto propone el mes actual completo."""
        self.limpiar_errores()
        hoy = date.today()
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        self.txt_nombre.value = ""
        self.campo_inicio.asignar(hoy.replace(day=1))
        self.campo_fin.asignar(hoy.replace(day=ultimo_dia))
        self.registro = None
        self.modo = "nuevo"
        self._aplicar_modo()

    # --- Acciones -------------------------------------------------------
    def nuevo(self, e=None):
        """Botón verde: abre el formulario de periodo vacío."""
        self.limpiar_formulario()
        self.page.navigate("/periodo")

    def ver(self, per: Periodo):
        """Engrane (desde movimientos): muestra el periodo en solo lectura."""
        self.limpiar_errores()
        self.registro = Periodo.get(per.id)  # datos frescos de la BD
        self._llenar(self.registro)
        self.modo = "ver"
        self._aplicar_modo()
        self.page.navigate("/movimientos/periodo")

    def editar(self, e=None):
        """Lápiz: habilita los campos del periodo mostrado."""
        self.modo = "editar"
        self._aplicar_modo()
        self.page.update()

    def cancelar(self, e=None):
        if self.modo == "editar":
            # Descarta los cambios: vuelve a leer el registro y regresa a "ver"
            self.limpiar_errores()
            self.registro = Periodo.get(self.registro.id)
            self._llenar(self.registro)
            self.modo = "ver"
            self._aplicar_modo()
            self.page.update()
        else:
            self.limpiar_formulario()
            self.page.navigate("/")

    def guardar(self, e=None):
        self.limpiar_errores()
        nombre = (self.txt_nombre.value or "").strip()
        faltantes = False
        if not nombre:
            self.txt_nombre.error_text = "Requerido"
            faltantes = True
        if self.campo_fin.valor < self.campo_inicio.valor:
            self.campo_fin.txt.error_text = "No puede ser anterior a la fecha inicio"
            faltantes = True
        if faltantes:
            self.page.update()
            return

        valores = dict(
            nombre=nombre,
            fecha_inicio=self.campo_inicio.valor,
            fecha_fin=self.campo_fin.valor,
        )
        try:
            if self.modo == "nuevo":
                Periodo.create(**valores)
            else:
                self.registro = Periodo.update(self.registro.id, **valores)
        except Exception as ex:  # noqa: BLE001
            aviso(self.page, f"Error al guardar: {ex}")
            return

        if self.modo == "nuevo":
            self.limpiar_formulario()
            aviso(self.page, "Periodo guardado")
            self.page.navigate("/")  # regresa a la lista de periodos
        else:
            # Se queda en el registro, ahora en solo lectura
            self._llenar(self.registro)
            self.modo = "ver"
            self._aplicar_modo()
            aviso(self.page, "Periodo actualizado")
            self.page.update()

    # ==================================================================
    # Eliminar
    # ==================================================================
    def _mensaje_eliminar(self, per: Periodo, cantidad: int) -> str:
        mensaje = f"¿Seguro que deseas eliminar el periodo «{per.nombre}»?"
        if cantidad:
            mensaje += f"\n\nTambién se eliminarán sus {cantidad} movimiento(s)."
        return mensaje

    def confirmar_eliminar(self, e=None):
        """Bote de la barra: elimina el periodo mostrado, con confirmación."""
        per = self.registro
        cantidad = Periodo.contar_movimientos().get(per.id, 0)

        def eliminar():
            if self._eliminar(per):
                self.limpiar_formulario()
                self.page.navigate("/")  # el periodo ya no existe: a la lista

        confirmar(self.page, "Eliminar periodo", self._mensaje_eliminar(per, cantidad), eliminar)

    def _eliminar(self, per: Periodo) -> bool:
        """Borra el periodo (y sus movimientos) y refresca la lista."""
        try:
            Periodo.delete(per.id)
        except Exception as ex:  # noqa: BLE001
            aviso(self.page, f"Error al eliminar: {ex}")
            return False
        self.cargar()
        aviso(self.page, "Periodo eliminado")
        self.page.update()
        return True

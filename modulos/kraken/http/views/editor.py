"""
Editor de una petición (/kraken/http/peticion):

  ← Usuarios •                                   [💾] [⋮]
  Entorno [Local ▾]  [{}]
  [GET ▾] [ {{base}}/users                           ]
  [          Enviar          ]
  ⚠ Sin definir: {{token}}
  (Params 1) (Headers 2) (Body) (Auth)
  [✓] page   2   ✕
  ───────────────────────────────────────────
  200 OK · 120 ms · 1.2 KB             [⧉] [⬇]
  (Body) (Headers 8) (Enviado)
  { "id": 1, … }

Guardado:
  - petición GUARDADA: se guarda sola al enviar y al salir (el • del título
    dice que hay cambios sin guardar)
  - petición NUEVA (o abierta desde el historial): 💾 le pone nombre y
    colección. Si sales sin guardar no pasa nada: lo que enviaste está en el
    historial.

Truco: pega un `curl …` en la URL y se llena todo solo.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
import asyncio

import flet as ft

from core.storage import human_size
from core.ui import confirm, dropdown_options, notify, service
from modulos.kraken import routes
from modulos.kraken.comun import (MONO, KeyValueEditor, ask_text, copy_text, status_chip,
                                  tabs_row)
from modulos.kraken.http import services
from modulos.kraken.models import (AUTH_SELECTION, BODY_SELECTION, METODOS, Ajustes,
                                   Coleccion, Entorno, HistorialHttp, Peticion)

MOSTRAR_MAX = 200 * 1024   # en pantalla se pintan hasta 200 KB (copiar/guardar llevan todo)


class RequestEditor:
    def __init__(self, page: ft.Page, on_closed):
        """on_closed(): al salir (la lista se recarga)."""
        self.page = page
        self.on_closed = on_closed
        self.peticion_id: int | None = None
        self.coleccion_id: int | None = None
        self.nombre = ""
        self.b = services.Borrador()
        self.sucio = False
        self.resultado: services.Resultado | None = None
        self.enviando = False
        self._tarea: asyncio.Task | None = None
        self._vars: dict[str, str] = {}
        self.seccion = "params"
        self.seccion_resp = "body"
        self.crudo = False   # respuesta JSON: bonita (False) o tal cual (True)
        self.activo = False  # ¿hay una petición abierta? (si se recarga la app, no)

        # --- Arriba: entorno, método, URL, Enviar ---
        self.dd_entorno = ft.Dropdown(label="Entorno", dense=True, expand=True,
                                      on_select=self._on_environment)
        self.dd_metodo = ft.Dropdown(
            value="GET", width=120, dense=True,
            options=[ft.DropdownOption(key=m, text=m) for m in METODOS],
            text_style=ft.TextStyle(font_family=MONO, weight=ft.FontWeight.BOLD),
            on_select=self._on_method)
        self.txt_url = ft.TextField(
            hint_text="https://api.ejemplo.com/recurso  ·  o pega un curl", dense=True,
            expand=True, text_style=ft.TextStyle(font_family=MONO), on_change=self._on_url,
            on_submit=self._send_from_url)
        self.btn_enviar = ft.FilledButton("Enviar", icon=ft.Icons.SEND, expand=True,
                                          on_click=self.send)
        self.btn_cancelar = ft.OutlinedButton("Cancelar", icon=ft.Icons.STOP, expand=True,
                                              visible=False, on_click=self.cancel)
        self.lbl_faltan = ft.Text(size=12, color=ft.Colors.ORANGE, visible=False)

        # --- Secciones de la petición ---
        self.fila_secciones = ft.Container()
        self.kv_params = KeyValueEditor(page, self._changed, "Parámetro", "Valor")
        self.kv_headers = KeyValueEditor(page, self._changed, "Header", "Valor")
        self.kv_form = KeyValueEditor(page, self._changed, "Campo", "Valor")
        self.fila_body_tipo = ft.Container()
        self.txt_body = ft.TextField(
            multiline=True, min_lines=8, max_lines=24, dense=True,
            text_style=ft.TextStyle(font_family=MONO, size=13), on_change=self._on_body)
        self.btn_formatear = ft.TextButton("Formatear JSON", icon=ft.Icons.AUTO_FIX_HIGH,
                                           on_click=self.format_json)
        self.dd_auth = ft.Dropdown(label="Tipo", dense=True,
                                   options=dropdown_options(AUTH_SELECTION),
                                   on_select=self._on_auth_type)
        self.txt_auth_usuario = ft.TextField(dense=True, text_style=ft.TextStyle(font_family=MONO),
                                             on_change=lambda e: self._set("auth_usuario",
                                                                           e.control.value))
        self.txt_auth_clave = ft.TextField(label="Contraseña", dense=True,
                                           text_style=ft.TextStyle(font_family=MONO),
                                           on_change=lambda e: self._set("auth_clave",
                                                                         e.control.value))
        self.seccion_ctrl = ft.Container()

        # --- Respuesta ---
        self.respuesta = ft.Column(spacing=8)

        self.titulo = ft.Text(overflow=ft.TextOverflow.ELLIPSIS)
        self.menu = ft.PopupMenuButton(icon=ft.Icons.MORE_VERT)
        self.vista = ft.View(
            route=routes.PETICION,
            appbar=ft.AppBar(title=self.titulo, actions=[
                ft.IconButton(ft.Icons.SAVE, tooltip="Guardar", on_click=lambda e: self.save_as()),
                self.menu,
            ]),
            scroll=ft.ScrollMode.AUTO,
            controls=[ft.SafeArea(content=ft.Column(spacing=10, controls=[
                ft.Row([self.dd_entorno,
                        ft.IconButton(ft.Icons.DATA_OBJECT, tooltip="Editar variables",
                                      on_click=lambda e: page.navigate(routes.ENTORNOS))]),
                ft.Row([self.dd_metodo, self.txt_url],
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Row([self.btn_enviar, self.btn_cancelar]),
                self.lbl_faltan,
                self.fila_secciones,
                self.seccion_ctrl,
                ft.Divider(),
                self.respuesta,
                ft.Container(height=40),
            ]))],
        )

    # ==================================================================
    # Abrir / cerrar
    # ==================================================================
    def open_request(self, p: Peticion):  # propio
        p = Peticion.get(p.id)
        self._open(p.id, p.coleccion_id, p.nombre, services.Borrador.from_request(p))

    def open_new(self, coleccion_id: int | None = None,  # propio
                 borrador: services.Borrador | None = None):
        self._open(None, coleccion_id, "", borrador or services.Borrador())

    def open_history(self, h: HistorialHttp):  # propio
        """Un envío viejo: su petición tal como estaba + la respuesta que llegó."""
        h = HistorialHttp.get(h.id)
        b = services.Borrador.from_dict(h.borrador) if h.borrador else services.Borrador(
            metodo=h.metodo, url=h.url)
        p = Peticion.get(h.peticion_id) if h.peticion_id else None
        if p is not None:  # sigue guardada: se abre ESA (con lo que se mandó aquella vez)
            self._open(p.id, p.coleccion_id, p.nombre, b)
            self.sucio = services.Borrador.from_request(p) != b
        else:
            self._open(None, None, "", b)
        self.resultado = services.result_from_history(h)
        self._render_all()

    def _open(self, peticion_id, coleccion_id, nombre, b: services.Borrador):  # propio
        self.peticion_id, self.coleccion_id, self.nombre, self.b = (peticion_id, coleccion_id,
                                                                   nombre, b)
        self.sucio = False
        self.activo = True
        self.resultado = None
        self.seccion = "body" if b.body_tipo != "ninguno" else "params"
        self.seccion_resp = "body"
        self.txt_url.autofocus = not b.url
        self._load_environments()
        self._fill_fields()
        self._render_all()
        self.page.navigate(routes.PETICION)

    def close(self):  # propio
        """Al salir: una petición guardada con cambios se guarda sola."""
        if self._tarea is not None:  # se cancela en el hilo de asyncio (no desde aquí)
            self.page.run_task(self.cancel)
        if self.peticion_id is not None and self.sucio:
            self._save_existing()
        self.activo = False
        self.on_closed()

    # ==================================================================
    # Pintar
    # ==================================================================
    def _fill_fields(self):  # propio
        b = self.b
        self.dd_metodo.value = b.metodo
        self.txt_url.value = b.url
        self.txt_body.value = b.body
        self.dd_auth.value = b.auth_tipo
        self.txt_auth_usuario.value = b.auth_usuario
        self.txt_auth_clave.value = b.auth_clave
        self.kv_params.load(b.params)
        self.kv_headers.load(b.headers)
        self.kv_form.load(b.form)

    def _render_all(self):  # propio
        self._render_title()
        self._render_menu()
        self._render_sections()
        self._render_missing()
        self._render_response()

    def _render_title(self):  # propio
        nombre = self.nombre or "Nueva petición"
        self.titulo.value = f"{nombre} •" if (self.sucio and self.peticion_id) else nombre

    def _render_menu(self):  # propio
        guardada = self.peticion_id is not None
        items = [
            ft.PopupMenuItem(content=ft.Text("Copiar como cURL"), icon=ft.Icons.TERMINAL,
                             on_click=self.copy_curl),
            ft.PopupMenuItem(content=ft.Text("Pegar cURL…"), icon=ft.Icons.INPUT,
                             on_click=lambda e: self.import_curl()),
        ]
        if guardada:
            items += [
                ft.PopupMenuItem(content=ft.Text("Renombrar"), icon=ft.Icons.EDIT,
                                 on_click=lambda e: self.rename()),
                ft.PopupMenuItem(content=ft.Text("Guardar como nueva…"), icon=ft.Icons.SAVE_AS,
                                 on_click=lambda e: self.save_as(nueva=True)),
                ft.PopupMenuItem(content=ft.Text("Eliminar"), icon=ft.Icons.DELETE,
                                 on_click=lambda e: self.confirm_delete()),
            ]
        self.menu.items = items

    def _render_tabs(self):  # propio
        """Solo la fila de pestañas (con sus contadores): se rearma en cada cambio."""
        b = self.b
        n_params, n_headers = self.kv_params.activos, self.kv_headers.activos
        body = "Body" if b.body_tipo == "ninguno" else f"Body · {BODY_SELECTION[b.body_tipo]}"
        auth = {"ninguna": "Auth", "bearer": "Auth · Bearer", "basic": "Auth · Básica"}.get(
            b.auth_tipo, "Auth")
        self.fila_secciones.content = tabs_row([
            ("params", f"Params ({n_params})" if n_params else "Params"),
            ("headers", f"Headers ({n_headers})" if n_headers else "Headers"),
            ("body", body), ("auth", auth)], self.seccion, self.set_section)

    def _render_sections(self):  # propio
        """Pestañas + el contenido de la elegida (al cambiar de pestaña o de tipo)."""
        self._render_tabs()
        if self.seccion == "headers":
            contenido = self.kv_headers.control
        elif self.seccion == "body":
            contenido = self._body_section()
        elif self.seccion == "auth":
            contenido = self._auth_section()
        else:
            contenido = self.kv_params.control
        self.seccion_ctrl.content = contenido

    def _body_section(self) -> ft.Control:  # propio
        b = self.b
        self.fila_body_tipo.content = tabs_row(list(BODY_SELECTION.items()), b.body_tipo,
                                               self.set_body_type)
        if b.body_tipo == "ninguno":
            extra = ft.Text("Sin cuerpo (lo normal en GET y DELETE).", size=12,
                            color=ft.Colors.OUTLINE)
        elif b.body_tipo == "form":
            extra = ft.Column(spacing=4, controls=[
                ft.Text("Se manda como application/x-www-form-urlencoded", size=12,
                        color=ft.Colors.OUTLINE),
                self.kv_form.control])
        else:
            self.txt_body.hint_text = ('{\n  "nombre": "Kraken",\n  "token": "{{token}}"\n}'
                                       if b.body_tipo == "json" else "Texto libre")
            self.btn_formatear.visible = b.body_tipo == "json"
            extra = ft.Column(spacing=2, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                              controls=[self.txt_body,
                                        ft.Row([self.btn_formatear])])
        return ft.Column(spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                         controls=[self.fila_body_tipo, extra])

    def _auth_section(self) -> ft.Control:  # propio
        tipo = self.b.auth_tipo
        controles: list[ft.Control] = [self.dd_auth]
        if tipo == "bearer":
            self.txt_auth_usuario.label = "Token"
            controles.append(self.txt_auth_usuario)
            controles.append(ft.Text("Se manda como  Authorization: Bearer <token>. "
                                     "Puedes usar {{token}}.", size=12, color=ft.Colors.OUTLINE))
        elif tipo == "basic":
            self.txt_auth_usuario.label = "Usuario"
            controles += [self.txt_auth_usuario, self.txt_auth_clave]
        return ft.Column(spacing=8, controls=controles)

    def _render_missing(self):  # propio
        faltan = services.missing_variables(self.b, self._vars)
        self.lbl_faltan.value = ("Sin definir: " + ", ".join("{{" + f + "}}" for f in faltan)
                                 if faltan else "")
        self.lbl_faltan.visible = bool(faltan)

    def _render_response(self):  # propio
        self.btn_enviar.visible = not self.enviando
        self.btn_cancelar.visible = self.enviando
        if self.enviando:
            self.respuesta.controls = [ft.ProgressBar(),
                                       ft.Text("Esperando respuesta…", color=ft.Colors.OUTLINE)]
            return
        r = self.resultado
        if r is None:
            self.respuesta.controls = [ft.Text("La respuesta aparece aquí.", italic=True,
                                               color=ft.Colors.OUTLINE)]
            return
        resumen = ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER,
                         controls=[status_chip(r.status, r.motivo),
                                   ft.Text(f"{r.tiempo_ms} ms", size=12),
                                   ft.Text(human_size(r.tamano), size=12)])
        if r.error:
            self.respuesta.controls = [resumen, ft.Container(
                padding=10, border_radius=8, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
                content=ft.Text(r.error, color=ft.Colors.RED, selectable=True))]
            return
        botones = ft.Row(spacing=0, controls=[
            ft.IconButton(ft.Icons.COPY, tooltip="Copiar respuesta", on_click=self.copy_body),
            ft.IconButton(ft.Icons.DOWNLOAD, tooltip="Guardar como archivo",
                          on_click=self.save_body, visible=bool(r.datos)),
        ])
        resumen.controls.append(ft.Container(expand=True))
        resumen.controls.append(botones)
        tabs = tabs_row([("body", "Body"), ("headers", f"Headers ({len(r.headers)})"),
                         ("enviado", "Enviado")], self.seccion_resp, self.set_response_section)
        self.respuesta.controls = [resumen, tabs, self._response_content(r)]

    def _response_content(self, r: services.Resultado) -> ft.Control:  # propio
        avisos = []
        if self.seccion_resp == "headers":
            texto = "\n".join(f"{k}: {v}" for k, v in r.headers)
        elif self.seccion_resp == "enviado":
            texto = f"{r.metodo} {r.url}\n\n" + "\n".join(f"{k}: {v}" for k, v in r.req_headers)
        else:
            texto = r.texto
            if r.es_json and not self.crudo:
                texto = services.pretty(texto)
            if r.es_json:
                avisos.append(ft.TextButton("Ver tal cual" if not self.crudo else "Ver bonito",
                                            icon=ft.Icons.DATA_OBJECT,
                                            on_click=self.toggle_raw))
            if r.incompleto and r.datos == b"":
                avisos.append(ft.Text("Del historial: guardada recortada según tus ajustes.",
                                      size=12, color=ft.Colors.OUTLINE))
            elif r.incompleto:
                avisos.append(ft.Text("Respuesta de más de 50 MB: se leyó solo el principio.",
                                      size=12, color=ft.Colors.ORANGE))
            if not texto:
                texto = "(sin cuerpo)"
        if len(texto) > MOSTRAR_MAX:
            avisos.append(ft.Text(f"Se muestran los primeros {human_size(MOSTRAR_MAX)}; "
                                  "copiar y guardar llevan todo.", size=12,
                                  color=ft.Colors.OUTLINE))
            texto = texto[:MOSTRAR_MAX]
        return ft.Column(spacing=4, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=[
            ft.Row(avisos, wrap=True, spacing=8),
            ft.Container(
                padding=10, border_radius=8, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                content=ft.Text(texto, selectable=True, size=12, font_family=MONO)),
        ])

    def refresh(self):  # propio
        self._render_all()
        self.page.update()

    # ==================================================================
    # Cambios del usuario
    # ==================================================================
    def _changed(self):  # propio
        """Algo de la petición cambió: título con •, contadores y variables."""
        self.sucio = True
        self._render_title()
        self._render_missing()
        self._render_tabs()  # no el contenido: el campo que escribes no se toca
        self.titulo.update()
        self.lbl_faltan.update()
        self.fila_secciones.update()

    def _set(self, campo: str, valor):  # propio
        setattr(self.b, campo, valor)
        self._changed()

    def _on_url(self, e):  # propio
        texto = e.control.value or ""
        if texto.lstrip().startswith("curl ") and len(texto) > 10:
            try:  # pegaste un curl en la URL: se llena todo
                self._load_borrador(services.parse_curl(texto))
                notify(self.page, "cURL importado")
                return
            except ValueError:
                pass  # aún no está completo: sigue escribiendo
        self._set("url", texto)

    def _send_from_url(self, e):  # propio
        self.page.run_task(self.send)

    def _on_method(self, e):  # propio
        self._set("metodo", e.control.value)

    def _on_body(self, e):  # propio
        self._set("body", e.control.value or "")

    def _on_auth_type(self, e):  # propio
        self.b.auth_tipo = e.control.value
        self._changed()
        self._render_sections()
        self.seccion_ctrl.update()

    def set_section(self, seccion: str):  # propio
        self.seccion = seccion
        self._render_sections()
        self.page.update()

    def set_body_type(self, tipo: str):  # propio
        self.b.body_tipo = tipo
        if tipo == "json" and self.b.body.strip():
            self.b.body = services.pretty(self.b.body)
            self.txt_body.value = self.b.body
        self._changed()
        self._render_sections()
        self.page.update()

    def set_response_section(self, seccion: str):  # propio
        self.seccion_resp = seccion
        self._render_response()
        self.page.update()

    def toggle_raw(self, e=None):  # propio
        self.crudo = not self.crudo
        self._render_response()
        self.page.update()

    def format_json(self, e=None):  # propio
        bonito = services.pretty(self.b.body)
        if bonito == self.b.body and self.b.body.strip():
            try:
                import json
                json.loads(self.b.body)
            except ValueError as ex:
                notify(self.page, f"No es JSON válido: {ex}")
                return
        self.b.body = bonito
        self.txt_body.value = bonito
        self._changed()
        self.txt_body.update()

    def _load_borrador(self, b: services.Borrador):  # propio
        """Reemplaza la petición del editor (p. ej. al pegar un curl)."""
        self.b = b
        self.seccion = "body" if b.body_tipo != "ninguno" else "params"
        self._fill_fields()
        self.sucio = True
        self._render_all()
        self.page.update()

    # ==================================================================
    # Entornos
    # ==================================================================
    def _load_environments(self):  # propio
        entornos = [e for e in Entorno.search_all() if not e.es_global]
        actual = Ajustes.current().entorno_id
        self.dd_entorno.options = [ft.DropdownOption(key="0", text="Sin entorno"),
                                   *(ft.DropdownOption(key=str(e.id), text=e.nombre)
                                     for e in entornos)]
        self.dd_entorno.value = str(actual or 0)
        self._vars = services.variables()

    def _on_environment(self, e):  # propio
        valor = int(e.control.value or 0)
        Ajustes.change(entorno_id=valor or None)
        self._vars = services.variables()
        self._render_missing()
        self.lbl_faltan.update()

    def reload_environments(self):  # propio
        """Al regresar de la pantalla de Entornos."""
        self._load_environments()
        self._render_missing()

    # ==================================================================
    # Enviar
    # ==================================================================
    async def send(self, e=None):  # propio
        if self.enviando:
            return
        if self.peticion_id is not None and self.sucio:
            self._save_existing()
        self.enviando = True
        self.seccion_resp = "body"
        self._render_response()
        self.page.update()
        self._tarea = asyncio.current_task()
        try:
            self.resultado = await services.send(self.b, self.peticion_id)
        except asyncio.CancelledError:
            notify(self.page, "Envío cancelado")
        finally:
            self._tarea = None
            self.enviando = False
        self._render_response()
        self.page.update()

    async def cancel(self, e=None):  # propio
        if self._tarea is not None:
            self._tarea.cancel()

    # ==================================================================
    # Guardar
    # ==================================================================
    def _save_existing(self):  # propio
        try:
            services.save_request(self.peticion_id, self.b)
        except ValueError as ex:
            notify(self.page, str(ex))
            return
        self.sucio = False
        self._render_title()

    def save_as(self, nueva: bool = False):  # propio
        """💾: guardada -> guarda ya · nueva (o "Guardar como nueva") -> nombre y colección."""
        if self.peticion_id is not None and not nueva:
            self._save_existing()
            notify(self.page, "Guardada")
            self.page.update()
            return
        colecciones = Coleccion.search_all()
        txt_nombre = ft.TextField(label="Nombre", autofocus=True,
                                  value=self.b.nombre_sugerido if not nueva
                                  else f"{self.nombre} (copia)")
        dd_coleccion = ft.Dropdown(
            label="Colección", value=str(self.coleccion_id or 0), expand=True,
            options=[ft.DropdownOption(key="0", text="Sin colección"),
                     *(ft.DropdownOption(key=str(c.id), text=c.nombre) for c in colecciones)])
        txt_nueva = ft.TextField(label="…o crea una colección nueva", dense=True)

        def ok(e=None):  # propio
            try:
                coleccion_id = int(dd_coleccion.value or 0) or None
                if (txt_nueva.value or "").strip():
                    coleccion_id = services.create_collection(txt_nueva.value).id
                p = services.save_request(None, self.b, txt_nombre.value or "", coleccion_id)
            except ValueError as ex:
                txt_nombre.error = str(ex)
                self.page.update()
                return
            self.page.pop_dialog()
            self.peticion_id, self.coleccion_id, self.nombre = p.id, p.coleccion_id, p.nombre
            self.sucio = False
            if self.resultado and self.resultado.historial_id:  # el envío queda ligado a ella
                HistorialHttp.update(self.resultado.historial_id, peticion_id=p.id)
            notify(self.page, "Petición guardada")
            self.refresh()

        txt_nombre.on_submit = ok
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Guardar petición"),
            content=ft.Container(width=460, content=ft.Column(
                tight=True, spacing=12, controls=[txt_nombre, ft.Row([dd_coleccion]),
                                                  txt_nueva])),
            actions=[ft.TextButton("Cancelar", on_click=lambda e: self.page.pop_dialog()),
                     ft.FilledButton("Guardar", on_click=ok)],
        ))

    def rename(self):  # propio
        def ok(nombre):  # propio
            if not nombre:
                raise ValueError("Ponle un nombre")
            Peticion.update(self.peticion_id, nombre=nombre)
            self.nombre = nombre
            self.refresh()
        ask_text(self.page, "Renombrar petición", ok, valor=self.nombre)

    def confirm_delete(self):  # propio
        def ok():  # propio
            Peticion.delete(self.peticion_id)
            self.peticion_id = None
            self.sucio = False
            self.activo = False
            notify(self.page, "Petición eliminada")
            self.on_closed()
            self.page.navigate(routes.HTTP)
        confirm(self.page, "Eliminar petición", f"¿Eliminar «{self.nombre}»?", ok)

    # ==================================================================
    # cURL, copiar, guardar archivo
    # ==================================================================
    async def copy_curl(self, e=None):  # propio
        try:
            await copy_text(self.page, services.to_curl(self.b), "cURL copiado")
        except ValueError as ex:
            notify(self.page, str(ex))

    def import_curl(self):  # propio
        def ok(texto):  # propio
            self._load_borrador(services.parse_curl(texto))
        ask_text(self.page, "Pegar cURL", ok, etiqueta="Comando curl", boton="Usar",
                 multilinea=True, ayuda="Reemplaza lo que hay en el editor")

    async def copy_body(self, e=None):  # propio
        r = self.resultado
        if r is None:
            return
        texto = services.pretty(r.texto) if (r.es_json and not self.crudo) else r.texto
        await copy_text(self.page, texto, "Respuesta copiada")

    async def save_body(self, e=None):  # propio
        r = self.resultado
        if r is None or not r.datos:
            return
        ruta = await service(self.page, ft.FilePicker).save_file(
            dialog_title="Guardar respuesta", file_name=_file_name(r), src_bytes=r.datos)
        if ruta or self.page.web:
            notify(self.page, "Respuesta guardada")


def _file_name(r: services.Resultado) -> str:  # propio
    """respuesta.json / .png / .html… según el Content-Type."""
    tipo = r.tipo.split(";")[0].strip().lower()
    extension = {"application/json": "json", "text/html": "html", "text/plain": "txt",
                 "text/csv": "csv", "application/xml": "xml", "text/xml": "xml",
                 "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
                 "image/webp": "webp", "application/pdf": "pdf",
                 "application/zip": "zip"}.get(tipo, "json" if r.es_json else "bin")
    return f"respuesta.{extension}"

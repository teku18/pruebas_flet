# Notas técnicas de ControlKraken

Conceptos que fueron apareciendo al construir la app, explicados para estudiarlos
con calma. Cada nota dice **qué es**, **para qué lo usamos** y **dónde está en el
código** (para que lo abras y lo veas funcionando).

> Se actualiza con cada cambio de la app. Lo más nuevo va al final de cada sección
> y en el [Registro](#registro-de-cambios-de-estas-notas).

## Índice

| # | Tema | Dónde lo usamos |
|---|------|-----------------|
| 1 | [Capas: modelo · servicio · vista](#1-capas-modelo--servicio--vista) | todos los módulos |
| 2 | [El contrato `AppModule` y la pila de vistas](#2-el-contrato-appmodule-y-la-pila-de-vistas) | `core/module.py`, `modulos/*/__init__.py` |
| 3 | [Rutas y "a dónde regresa la flecha"](#3-rutas-y-a-dónde-regresa-la-flecha) | `modulos/desarrollo/__init__.py` |
| 4 | [Migraciones con Alembic (y datos iniciales)](#4-migraciones-con-alembic-y-datos-iniciales) | `alembic/versions/` |
| 5 | [Contar por grupos en UNA consulta (`CASE`)](#5-contar-por-grupos-en-una-consulta-case) | `modulos/desarrollo/services.py` |
| 6 | [Ordenar por prioridad en Python, no en SQL](#6-ordenar-por-prioridad-en-python-no-en-sql) | `modulos/desarrollo/services.py` |
| 7 | [Calcular en vez de guardar (recurrentes)](#7-calcular-en-vez-de-guardar-recurrentes) | `modulos/agenda/services.py` → `occurrences()` |
| 8 | [`calendar.monthdatescalendar`](#8-calendarmonthdatescalendar) | `modulos/agenda/views/calendario.py` |
| 9 | [Gestos: `ft.GestureDetector`](#9-gestos-ftgesturedetector) | `calendario.py` |
| 10 | [Animación carrusel en 3 tiempos](#10-animación-carrusel-en-3-tiempos) | `calendario.py` → `_slide()` |
| 11 | [`async`, `await` y `page.run_task`](#11-async-await-y-pagerun_task) | calendario, herramienta de captura |
| 12 | [La vista pregunta, el servicio decide (`marcable`/`deshacible`)](#12-la-vista-pregunta-el-servicio-decide) | `agenda/services.py`, `calendario.py` |
| 13 | [Truco "el último gana" con un diccionario](#13-truco-el-último-gana-con-un-diccionario) | `agenda/services.py` → `_last_done_ids()` |
| 14 | [Imports dentro de funciones (imports circulares)](#14-imports-dentro-de-funciones-imports-circulares) | varios |
| 15 | [Archivos fuera de la BD (filestore) y borrado en cascada](#15-archivos-fuera-de-la-bd-filestore-y-borrado-en-cascada) | `core/storage.py`, modelos con adjuntos |
| 16 | [Cambios "pendientes" que se aplican al Guardar](#16-cambios-pendientes-que-se-aplican-al-guardar) | `bitacora.py`, `desarrollo/views/adjuntos.py` |
| 17 | [`page.overlay`: algo encima de todas las pantallas](#17-pageoverlay-algo-encima-de-todas-las-pantallas) | `desarrollo/views/herramienta.py` |
| 18 | [`page.take_screenshot` y la grabación como GIF](#18-pagetake_screenshot-y-la-grabación-como-gif) | `herramienta.py`, `desarrollo/capturas.py` |
| 19 | [`asyncio.to_thread`: trabajo pesado sin congelar](#19-asyncioto_thread-trabajo-pesado-sin-congelar) | `herramienta.py` |
| 20 | [Guardar un dato en el nombre del archivo](#20-guardar-un-dato-en-el-nombre-del-archivo) | `desarrollo/capturas.py` |
| 21 | [Excel con openpyxl: fórmulas, vínculos, formato](#21-excel-con-openpyxl-fórmulas-vínculos-formato) | `desarrollo/exportador.py`, `finanzas/exportador.py` |
| 22 | [Servicios de Flet (`FilePicker`…) y por qué "desaparecen"](#22-servicios-de-flet-filepicker-y-por-qué-desaparecen) | `core/ui.py` → `service()` |
| 23 | [Archivos desde el celular: ruta vs contenido](#23-archivos-desde-el-celular-ruta-vs-contenido) | `adjuntos.py`, `bitacora.py` |
| 24 | [`page.media.padding`: no quedar tapado por la barra del celular](#24-pagemediapadding-no-quedar-tapado-por-la-barra-del-celular) | `herramienta.py` → `_place()` |
| 25 | [Menú flotante con "velo" en el overlay](#25-menú-flotante-con-velo-en-el-overlay) | `herramienta.py` |
| 26 | [Dibujar con el dedo: `Canvas` + `GestureDetector`](#26-dibujar-con-el-dedo-canvas--gesturedetector) | `desarrollo/views/pincel.py` |
| 27 | [Arranque frágil: preferencias que no responden](#27-arranque-frágil-preferencias-que-no-responden) | `core/ui.py` → `pref_get()` |
| 28 | [rclone: subir, consultar y bajar respaldos](#28-rclone-subir-consultar-y-bajar-respaldos) | `core/drive.py`, `docs/respaldo.md` |
| 29 | [Del código al APK: datos, firma y versiones](#29-del-código-al-apk-datos-firma-y-versiones) | `core/database.py`, `pyproject.toml`, `scripts/build_apk.sh` |
| 30 | [El candado de la BD](#30-el-candado-de-la-bd-por-qué-se-perdieron-desarrollo-proyectos-y-agenda) | `core/database.py` |
| 31 | [De Selection a catálogo: etapas](#31-de-selection-a-catálogo-etapas-como-los-stage_id-de-odoo) | `modulos/proyectos/models/catalogos.py`, migración 0011 |
| 32 | [Kanban con Flet: Draggable + DragTarget](#32-kanban-con-flet-draggable--dragtarget) | `modulos/proyectos/views/comun.py`, `tareas.py` |
| 33 | [Probar en el navegador con Playwright](#33-cómo-se-probó-sin-celular-flet-en-el-navegador--playwright) | (pruebas, fuera del repo) |
| 34 | [Una sola tabla de adjuntos](#34-una-sola-tabla-de-adjuntos-como-irattachment-de-odoo) | `core/adjuntos.py`, migración 0012 |
| 35 | [Probar que el respaldo está completo](#35-probar-que-el-respaldo-está-completo-sin-listas-fijas) | `scripts/verificar_respaldo.py` |
| 36 | [Avisos con la app cerrada](#36-avisos-con-la-app-cerrada-quién-despierta-a-quién) | `pruebas/notificaciones/` |
| 37 | [Avisos de la Agenda: proveedores y eventos](#37-avisos-de-la-agenda-proveedores-eventos-y-reprograma-todo) | `core/avisos.py`, `modulos/agenda/avisos.py` |
| 38 | [Notas: guardado automático, EXISTS y 2 columnas](#38-notas-guardado-automático-búsqueda-con-exists-y-tarjetas-en-2-columnas) | `modulos/notas/` |
| 39 | [Memorias: fotos con Pillow, un día como hoy, voz](#39-memorias-fotos-con-pillow-un-día-como-hoy-y-diseño-listo-para-la-voz) | `modulos/memorias/`, `scripts/verificar_flet.py` |
| 40 | [Cliente HTTP: httpx async, cancelar y `{{variables}}`](#40-cliente-http-httpx-async-cancelar-y-variables) | `modulos/kraken/http/` |
| 41 | [cURL: `shlex` para leer comandos como la terminal](#41-curl-shlex-para-leer-comandos-como-la-terminal) | `modulos/kraken/http/services.py` |
| 42 | [SQLite por dentro: solo lectura real, PRAGMA y archivos fuera del respaldo](#42-sqlite-por-dentro-solo-lectura-real-pragma-y-archivos-fuera-del-respaldo) | `modulos/kraken/sqlite/`, `core/backup.py` |
| 43 | [Red: sockets, ping sin ser root y puertos en paralelo](#43-red-sockets-ping-sin-ser-root-y-puertos-en-paralelo) | `modulos/kraken/red/ping.py`, `puertos.py`, `dispositivos.py` |
| 44 | [DNS, certificados, Whois y Wake-on-LAN por dentro](#44-dns-certificados-whois-y-wake-on-lan-por-dentro) | `modulos/kraken/red/` |
| 45 | [Probar red sin internet: servidores falsos](#45-probar-red-sin-internet-servidores-falsos) | `scripts/verificar_kraken.py` |
| 46 | [SSH con paramiko: huella del servidor y sudo sin teclado](#46-ssh-con-paramiko-huella-del-servidor-y-sudo-sin-teclado) | `modulos/kraken/ssh/conexion.py` |
| 47 | [Panel en vivo: /proc, diferencias y "solo mientras lo ves"](#47-panel-en-vivo-proc-diferencias-y-solo-mientras-lo-ves) | `modulos/kraken/ssh/metricas.py`, `views/panel.py` |
| 48 | [Una sola pantalla para tres motores: DB-API](#48-una-sola-pantalla-para-tres-motores-db-api) | `modulos/kraken/sqlite/motores.py` |
| 49 | [Solo lectura y 30 s: que lo cuide el servidor](#49-solo-lectura-y-30-s-que-lo-cuide-el-servidor) | `motores.py` (`connect`) |
| 50 | [Túnel SSH: llegar a la base sin abrir puertos](#50-túnel-ssh-llegar-a-la-base-sin-abrir-puertos) | `modulos/kraken/ssh/tunel.py` |
| 51 | [Consola SSH sin terminal: carpeta, sudo y Ctrl+C](#51-consola-ssh-sin-terminal-carpeta-sudo-y-ctrlc) | `modulos/kraken/ssh/consola.py` |
| 52 | [Postman: el formato Collection v2.1](#52-postman-el-formato-collection-v21) | `modulos/kraken/http/postman.py` |
| 53 | [Variables de colores y autocompletar: cursor y TextSpan](#53-variables-de-colores-y-autocompletar-cursor-y-textspan) | `modulos/kraken/http/views/variables.py` |

---

## 1. Capas: modelo · servicio · vista

**Qué es.** Separar el código en tres "cuartos" que no se mezclan:

```
 ┌──────────────┐   pregunta    ┌──────────────┐   lee/escribe   ┌──────────────┐
 │    views/    │ ────────────► │ services.py  │ ──────────────► │   models/    │
 │  el mesero   │ ◄──────────── │ el cocinero  │ ◄────────────── │ la despensa  │
 │ (solo pinta) │  datos listos │ (decide)     │                 │ (tablas, BD) │
 └──────────────┘               └──────────────┘                 └──────────────┘
```

**Para qué.** La pantalla nunca calcula: si mañana cambia una regla (p. ej. qué
cuenta como "vencida"), solo tocas el servicio. Es como en Odoo separar el
modelo (`models.Model`) de la vista XML, con la lógica en métodos del modelo.

**Dónde.** Cada módulo: `models/`, `services.py`, `views/`.

## 2. El contrato `AppModule` y la pila de vistas

**Qué es.** Cada módulo es una clase que hereda de `AppModule` (como el
`__manifest__` de un addon) y dice: nombre, ícono, ruta base y **qué pantallas
apila** para cada ruta (`build_views`).

```
 page.views  (la pila; la de arriba es la que ves)
 ┌─────────────────────────────┐
 │ Formulario del pendiente    │  ← /desarrollo/modulo/pendiente
 ├─────────────────────────────┤
 │ Pendientes del módulo       │  ← /desarrollo/modulo
 ├─────────────────────────────┤
 │ Desarrollo (lista)          │  ← /desarrollo
 ├─────────────────────────────┤
 │ Inicio (siempre abajo)      │  ← /
 └─────────────────────────────┘
```

**Para qué.** `main.py` no sabe nada de los módulos: pregunta al dueño de la ruta
qué pantallas poner. Agregar un módulo = crear la clase y sumarla a `MODULES`.

**Dónde.** `core/module.py`, `modulos/__init__.py`, `main.py` → `on_route_change`.

## 3. Rutas y "a dónde regresa la flecha"

**Qué es.** En Desarrollo, en vez de un `if/elif` por ruta en `go_back`, hay un
**diccionario** `{ruta: ruta_padre}` en `_parent()`. La flecha de regreso y el
"después de guardar" usan el mismo mapa.

```python
{MODULO_DATOS: MODULO, MODULO_PENDIENTE: MODULO, MODULO: BASE, ...}.get(route, "/")
```

**Para qué.** Una sola fuente de verdad; agregar una pantalla es agregar una línea.

**Dónde.** `modulos/desarrollo/__init__.py` → `_parent()`.

## 4. Migraciones con Alembic (y datos iniciales)

**Qué es.** Cada cambio de tablas es un archivo numerado (`0009_…`, `0010_…`) con
`upgrade()` / `downgrade()`. Al abrir la app, `init_db()` aplica las pendientes
(como `migrate` de Django). Antes respalda la BD.

- `op.create_table(...)` crea tablas nuevas.
- `op.bulk_insert(tabla, [dict(...), ...])` mete **datos iniciales** (así nacieron
  Finanzas 95 %, Proyectos 50 %… en la 0009).
- `batch_alter_table` (modo *batch*): SQLite casi no sabe `ALTER TABLE`, así que
  Alembic copia la tabla con el cambio y la reemplaza.

**Dónde.** `alembic/versions/0009_desarrollo.py`, `0010_desarrollo_adjuntos.py`,
`core/database.py` → `init_db()`.

## 5. Contar por grupos en UNA consulta (`CASE`)

**Qué es.** Para saber de cada módulo cuántos pendientes, cuántos de alta y
cuántos hechos, no se hacen 3 consultas por módulo: se hace **una** agrupada,
sumando 1 o 0 según una condición.

```python
select(Pendiente.modulo_id,
       func.sum(case((abierto, 1), else_=0)),                         # pendientes
       func.sum(case((abierto & (Pendiente.prioridad == "alta"), 1), else_=0)),
       func.sum(case((Pendiente.hecho.is_(True), 1), else_=0)))       # hechos
 .group_by(Pendiente.modulo_id)
```

**Para qué.** Rápido aunque tengas muchos módulos. Es el equivalente a un
`read_group` de Odoo.

**Dónde.** `modulos/desarrollo/services.py` → `_counts()`.

## 6. Ordenar por prioridad en Python, no en SQL

**Qué es.** La prioridad se guarda como texto (`"alta"`, `"media"`, `"baja"`). En SQL
se ordenaría alfabéticamente (alta, baja, media ✗). Se ordena en Python con un
diccionario de pesos:

```python
PRIORIDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2}
sorted(items, key=lambda p: (PRIORIDAD_ORDEN[p.prioridad], p.id))
```

**Dónde.** `modulos/desarrollo/models/modulo.py`, `services.py` → `_priority_key()`.

## 7. Calcular en vez de guardar (recurrentes)

**Qué es.** Una tarea guarda **solo su próxima fecha**. Para el calendario se
"expande" aplicando `next_date()` hasta el fin del rango:

```
Tarea(fecha=8 oct, mensual) + rango oct–dic  →  8 oct, 8 nov, 8 dic
Tarea(fecha=hoy, diaria)    + año completo   →  365 apariciones (sin guardar 365 filas)
```

Lo ya hecho sale del historial (`Cumplimiento.fecha_programada`).

**Para qué.** La BD no crece con repeticiones y cambiar la frecuencia se refleja
al instante. Es como un campo `compute` **sin** `store=True` en Odoo.

**Dónde.** `modulos/agenda/services.py` → `occurrences()`.

## 8. `calendar.monthdatescalendar`

**Qué es.** Función de la librería estándar que regresa las semanas de un mes
como listas de 7 fechas (incluye días del mes anterior/siguiente para completar).

```python
calendar.Calendar(firstweekday=0).monthdatescalendar(2026, 9)
# [[31 ago, 1 sep, … 6 sep], [7 sep, …], … ]   (0 = semana empieza en lunes)
```

**Para qué.** Armar la cuadrícula del Mes y las miniaturas del Año con la misma
función `_month()` (`mini=True` para la versión chica).

**Dónde.** `modulos/agenda/views/calendario.py` → `_month()`, `_year()`.

## 9. Gestos: `ft.GestureDetector`

**Qué es.** Un control invisible que envuelve a otro y avisa de gestos. Para
deslizar a los lados se usan tres eventos:

```
 on_horizontal_drag_start   → self._dx = 0
 on_horizontal_drag_update  → self._dx += e.primary_delta   (cuánto se movió en X)
 on_horizontal_drag_end     → ¿|dx| ≥ 60 px  o  |velocidad| ≥ 400 px/s?  → cambiar
```

**Para qué.** Deslizar ← → para cambiar de día/semana/mes/año. Funciona con el
dedo y arrastrando con el mouse. Solo envuelve el resumen + calendario para no
pelear con la fila de chips (que también se desliza).

**Dónde.** `calendario.py` → `self.zona`, `_on_drag_*`.

## 10. Animación carrusel en 3 tiempos

**Qué es.** Flet 1.0 no trae transición de "deslizar", así que se arma a mano
animando `offset` y `opacity` de un contenedor:

```
 1. sale:    offset → -0.35 , opacity → 0      (animado)
 2. cambia:  quita la animación, pone offset +0.35 y cambia el periodo
 3. entra:   vuelve la animación, offset → 0 , opacity → 1   (animado)
```

**La clave:** `self.cuerpo` es **siempre el mismo objeto** (solo cambia su
`content`). Si se creara uno nuevo cada vez, Flet no tendría "de dónde" animar.

**Dónde.** `calendario.py` → `_slide()`.

## 11. `async`, `await` y `page.run_task`

**Qué es.**
- `async def` = función que puede **esperar** sin congelar la app.
- `await algo` = "espera a que termine esto" (una animación, un diálogo).
- `page.run_task(func)` = arranca una función `async` desde un evento normal.

```python
async def _slide(self, paso):
    ... ; self.page.update()
    await asyncio.sleep(0.16)   # la app sigue respondiendo mientras tanto
```

**Ojo** (ver [nota 22](#22-servicios-de-flet-filepicker-y-por-qué-desaparecen)):
con `run_task` el clic termina **de inmediato**; si lo que lanzas espera un
diálogo largo, mejor que el botón llame directo a la función `async`.

**Dónde.** `calendario.py`, `desarrollo/views/herramienta.py`, `main.py` (`on_start`).

## 12. La vista pregunta, el servicio decide

**Qué es.** Cada aparición en el calendario (`Ocurrencia`) trae ya decidido si se
puede marcar o deshacer. La vista solo pinta el círculo fuerte o tenue.

| Campo | Significa |
|---|---|
| `marcable` | es la fecha que toca AHORITA (`fecha == tarea.fecha`) |
| `deshacible` | es la ÚLTIMA vez que se marcó esa tarea |

**Para qué.** Las reglas viven en un solo lugar (igual que el chismoso) y las
recurrentes no se descuadran.

**Dónde.** `modulos/agenda/services.py` → `Ocurrencia`; `calendario.py` → `_check_button()`.

## 13. Truco "el último gana" con un diccionario

**Qué es.** Si recorres filas **ordenadas** y las metes a un diccionario, cada
clave se queda con el **último** valor visto:

```python
filas = [(tarea 1, id 10), (tarea 1, id 14), (tarea 2, id 11)]   # ordenadas por fecha
{t: cid for t, cid in filas}   →  {1: 14, 2: 11}
```

**Para qué.** Sacar "el más reciente por grupo" sin una consulta complicada.

**Dónde.** `modulos/agenda/services.py` → `_last_done_ids()`.

## 14. Imports dentro de funciones (imports circulares)

**Qué es.** Si A importa B y B importa A **arriba del archivo**, Python se traba
(uno de los dos todavía no termina de cargar). Solución: importar dentro de la
función que lo necesita, que corre después, cuando ya todo cargó.

```
 chismoso.py ──import──► calendario.py
      ▲                        │
      └──── import DENTRO de _toggle() (no arriba)
```

**Dónde.** `calendario.py` → `_toggle()`; `Proyecto.delete`; `herramienta.py` →
`_current_module()` (importa `MODULES`).

## 15. Archivos fuera de la BD (filestore) y borrado en cascada

**Qué es.** Los archivos van a `data/…` y la BD guarda solo la **ruta relativa**
(como el filestore de Odoo). `save_file()` antepone un id corto para que dos
archivos con el mismo nombre no choquen.

```
 data/adjuntos/<proyecto>/<entrada>/…      (Proyectos)
 data/desarrollo/<pendiente>/…             (Desarrollo)
 data/capturas/…                           (bandeja de capturas)
```

Borrar: `cascade="all, delete-orphan"` borra las **filas** hijas; los
**archivos** los borra un `delete()` redefinido en el modelo (como un `unlink()`
heredado en Odoo). `data/` entra completo en el respaldo.

**Dónde.** `core/storage.py`; `Pendiente.delete`, `ModuloApp.delete`, `DevAdjunto.delete`.

## 16. Cambios "pendientes" que se aplican al Guardar

**Qué es.** Mientras editas, los adjuntos agregados o quitados viven en una lista
en memoria (`id=None` = todavía no guardado; `borrar` = ids por borrar). Solo al
dar **Guardar** se copian los archivos y se crean/borran filas (`apply()`).

**Para qué.** Si das Cancelar, no queda basura ni se pierde nada.

**Dónde.** `proyectos/views/bitacora.py` → `_apply_attachment_changes()`;
`desarrollo/views/adjuntos.py` → `AttachmentsBox.apply()`.

## 17. `page.overlay`: algo encima de todas las pantallas

**Qué es.** Una capa que Flet pinta **encima de todas las vistas**. Los controles
ahí se posicionan con `left/top/right/bottom`.

```
 ┌──────────────── page.overlay ────────────────┐
 │ (📷)                                          │  ← siempre visible
 └──────────────────────────────────────────────┘
 ┌──────────────── page.views ──────────────────┐
 │  la pantalla que toque (Agenda, Finanzas…)    │
 └──────────────────────────────────────────────┘
```

**Para qué.** El botón de captura aparece en cualquier módulo **sin tocar sus
pantallas**. Se instala una vez en `DesarrolloModule.on_start` (el mismo gancho
que usa Configuración para cargar el tema).

**Dónde.** `modulos/desarrollo/views/herramienta.py` → `install()`.

## 18. `page.take_screenshot` y la grabación como GIF

**Qué es.** `page.enable_screenshots = True` + `await page.take_screenshot()`
regresa un PNG de la app completa (con overlays). Para "grabar" se toma una
captura cada 0.4 s y al detener se arman como **GIF animado** con Pillow.

```
 PNG  PNG  PNG  PNG …  ──Pillow──►  grabacion_agenda_….gif
 0.4s 0.4s 0.4s                     (cada cuadro dura lo que tardó el siguiente)
```

**Límites:** solo captura la app (no otras aplicaciones), ~2.5 cuadros/s.
`pixel_ratio=1` para que en el celular no salgan imágenes ×3 de pesadas.

**Dónde.** `herramienta.py` → `screenshot()`, `record()`; `capturas.py` → `save_recording()`.

## 19. `asyncio.to_thread`: trabajo pesado sin congelar

**Qué es.** Corre una función **normal** (no async) en otro hilo y la espera con
`await`. Mientras, la app sigue respondiendo.

```python
captura = await asyncio.to_thread(save_recording, cuadros, tiempos, origen)
```

**Para qué.** Armar el GIF puede tardar; sin esto la app se congelaría.

**Dónde.** `herramienta.py` → `record()`.

## 20. Guardar un dato en el nombre del archivo

**Qué es.** La captura recuerda en qué módulo se tomó **en su nombre**:
`captura_agenda_2026-09-29_203512.png`. Una expresión regular lo recupera
(`Captura.origen`) y `slug()` normaliza "Configuración" → `configuracion`.

**Para qué.** No hizo falta una tabla para la bandeja; al "Reportar" se elige solo
el módulo correcto.

**Dónde.** `modulos/desarrollo/capturas.py`.

## 21. Excel con openpyxl: fórmulas, vínculos, formato

**Qué es.** openpyxl escribe `.xlsx` celda por celda.

- **Fórmulas, no números fijos:** el Resumen cuenta con
  `=COUNTIFS('Agenda'!$C$6:$C$2000,"Pendiente",'Agenda'!$B$6:$B$2000,"Alta")`,
  así si editas en Excel se actualiza solo.
- **Nombre de hoja entre comillas** en fórmulas (`'Mis cosas'!A1`); una `'` se
  escribe `''`. Excel no acepta `[]:*?/\` y máximo 31 caracteres.
- **Vínculo interno:** `celda.hyperlink = "#'Agenda'!A1"`.
- **Porcentaje como fracción:** 0.95 con formato `0%` → 95 %.
- **Barra dentro de la celda:** `DataBarRule` (formato condicional).
- `freeze_panes`, `auto_filter`, y `page_setup` horizontal ajustado al ancho.
- Se arma en memoria (`BytesIO`) y `FilePicker.save_file(src_bytes=…)` lo escribe
  (funciona en compu, web y celular).

**Dónde.** `modulos/desarrollo/exportador.py`, `modulos/finanzas/exportador.py`.

## 22. Servicios de Flet (`FilePicker`…) y por qué "desaparecen"

**El bug:** al adjuntar desde el celular →
`RuntimeError: … Control with ID 2086 is not registered.`

**Qué pasaba.** `FilePicker`, `UrlLauncher`… son **servicios** (no se ven en
pantalla). Después de **cada evento**, Flet da de baja los que "nadie usa":
cuenta referencias (`sys.getrefcount`) y su índice de controles guarda
referencias **débiles** (`weakref`). Uno guardado solo en `self.picker` quedaba
justo en el límite. Además el botón lanzaba la selección con `page.run_task`: el
clic terminaba al instante → Flet limpiaba → el selector seguía abierto en el
celular → al volver la respuesta, el control ya no existía.

```
 clic ─► run_task(pick_files) ─► fin del evento ─► Flet: "¿quién usa el picker?" ─► baja ✗
                    └── (en el cel sigues eligiendo…) ──────────► respuesta ─► "not registered"
```

**Solución.** `service(page, ft.FilePicker)` en `core/ui.py`: lo crea al usarlo y
lo guarda en `page.services` (lista de la primera vista = Inicio, que nunca se
quita) → siempre hay una referencia fuerte. Uno por página, compartido.

```python
archivos = await service(self.page, ft.FilePicker).pick_files(...)
```

**Dónde.** `core/ui.py` → `service()`; usado en adjuntos, bitácora, respaldo,
importar Excel y exportar Excel.

## 23. Archivos desde el celular: ruta vs contenido

**Qué es.** Con `flet run` + el celular (código QR), **Python corre en tu compu**
y el selector de archivos en el **teléfono**. La ruta que llega
(`/storage/emulated/0/DCIM/…`) es del teléfono: la compu no la puede abrir.

```
 📱 eliges foto.jpg ──► ruta "/storage/…/foto.jpg" (no existe en la compu) ✗
                   └──► with_data=True: llegan los BYTES del archivo        ✓
```

**Solución.** `pick_files(..., with_data=True)` y usar la ruta solo si existe en
esta máquina (`local_path()`); si no, se guarda desde los bytes.

**Dónde.** `desarrollo/views/adjuntos.py` → `pick_files()`, `local_path()`;
`proyectos/views/bitacora.py` → `pick_files()`.

## 24. `page.media.padding`: no quedar tapado por la barra del celular

**Qué es.** `page.media.padding.bottom` = alto (en px lógicos) de lo que el sistema
ocupa abajo: la barra de botones ◁ ○ □ o la de gestos. En la compu es 0.
`page.on_media_change` avisa si cambia (girar el celular, etc.).

```
 ┌───────────────────────────────┐
 │ (📷)                   (+ …)  │  ← bottom = barra + 18  (misma altura que el "+")
 │───────────────────────────────│
 │   ◁      ○      □             │  ← page.media.padding.bottom (≈48 en muchos Android)
 └───────────────────────────────┘
```

**Para qué.** Lo que va en `page.overlay` NO respeta solo el área segura (a
diferencia del "+" de cada vista, que Flet acomoda por ti). Hay que sumarle ese
alto a mano para que el botón y el menú no queden debajo de los botones del
sistema.

**Dónde.** `herramienta.py` → `_inset()`, `_place()`; constantes `ALTURA_BOTON`, `ALTURA_MENU`.

## 25. Menú flotante con "velo" en el overlay

**Qué es.** En vez de un `BottomSheet` (que siempre sale pegado al borde de abajo),
dos piezas en el overlay:

```
 overlay:  [ velo (pantalla completa, negro 25 %, on_click = cerrar) ]
           [ menú (tarjeta chica, left/bottom a tu gusto)          ]
```

El **velo** oscurece un poco y atrapa el toque "afuera" para cerrar el menú.
El orden en `page.overlay` es el orden de encimado: lo último queda arriba.

**Dónde.** `herramienta.py` → `open_menu()`, `close_menu()`, `_show()`, `_hide()`.

## 26. Dibujar con el dedo: `Canvas` + `GestureDetector`

**Qué es.** Una "hoja de acetato" transparente a pantalla completa en el overlay:

```
 GestureDetector
   on_pan_start  → nuevo trazo:  cv.Path([MoveTo(x, y)])
   on_pan_update → trazo.elements.append(LineTo(x, y))  → lienzo.update()
 Canvas(shapes=[trazo1, trazo2, …])     ← "Deshacer" = shapes.pop()
```

- `ft.Paint(style=STROKE, stroke_cap=ROUND, stroke_join=ROUND)`: línea con puntas
  y esquinas redondas (se ve como marcador).
- `drag_interval=16`: máximo ~60 avisos por segundo (no satura la conexión).
- `lienzo.update()` en vez de `page.update()`: solo manda el cambio del lienzo.
- La capa tiene `bgcolor` TRANSPARENTE: sin color, las zonas vacías no reciben
  el toque (igual que en el deslizar del calendario, nota 9).
- Se inserta en el overlay **debajo** de la barra de herramientas
  (`overlay.insert(overlay.index(barra), capa)`), si no, taparía los botones.
- Como `take_screenshot` incluye el overlay, los trazos salen en la foto y en la
  grabación. Antes de la foto se quita la barra (para que no salga).

**Dónde.** `modulos/desarrollo/views/pincel.py` → `DrawLayer`;
`herramienta.py` → `start_marking()`, `screenshot()`, `toggle_pen()`.

## 27. Arranque frágil: preferencias que no responden

**El bug:** al abrir desde el celular →
`Timeout waiting for invoke method listener for SharedPreferences(477).get`,
y Configuración/Respaldo quedaban a medias (no se podía restaurar).

**Qué pasa por dentro.** `SharedPreferences` es un *servicio* (nota 22): Python
le pide algo al celular y espera la respuesta hasta 10 s. Al arrancar, todos
los módulos corren su `on_start` casi al mismo tiempo. La herramienta de
captura hacía `page.enable_screenshots = True` en ese momento; en el celular
eso reconstruye la pantalla y la petición de Configuración se perdía.

```
 on_start Desarrollo:  enable_screenshots ─► 📱 reconstruye todo ─┐
 on_start Configuración: prefs.get("modo") ───── se pierde ───────┘ ⏱ 10 s ✗
```

**Lecciones.**
1. No cambies algo "grande" de la página al arrancar si no hace falta:
   `enable_screenshots` ahora se activa en la primera captura
   (`_ensure_screenshots()`).
2. Lo que viene del dispositivo puede fallar: léelo con red de seguridad.
   `pref_get(prefs, clave, defecto)` reintenta y, si no hay respuesta, usa el
   valor de fábrica; si ya falló, las siguientes lecturas no vuelven a esperar
   10 s (recuerda el servicio "mudo" por su `id()`).

**Dónde.** `core/ui.py` → `pref_get()`, `pref_set()`;
`desarrollo/views/herramienta.py` → `_ensure_screenshots()`.

## 28. rclone: subir, consultar y bajar respaldos

**Qué es.** Un programa de terminal que copia archivos entre tu compu y nubes
(Drive, Dropbox…). La app NO guarda tu contraseña ni tu token de Google: le
pide a rclone que suba/baje (`subprocess.run(["rclone", ...])`). El "pase" de
Google vive en `~/.config/rclone/rclone.conf`.

```
 App ──zip──► ~/Respaldos/ControlKraken ──rclone copy──► Drive/ControlKraken
                         ▲                                     │
                         └──────── rclone copy (bajar) ◄───────┘
```

| Para… | Comando |
|---|---|
| ver que existe | `rclone version` · `rclone listremotes` (debe salir `gdrive:`) |
| subir | `rclone copy ~/Respaldos/ControlKraken gdrive:ControlKraken --include "ControlKraken_*.zip" -P` |
| consultar | `rclone lsl gdrive:ControlKraken` (tamaño, fecha, nombre) |
| bajar | `rclone copy gdrive:ControlKraken /tmp/prueba_drive -P` |
| ver qué trae un zip | `unzip -l archivo.zip` |

- **scope 3** (`drive.file`): rclone solo ve lo que él mismo creó, no todo tu
  Drive. Por eso `rclone lsd gdrive:` sale vacío al principio.
- `copy` nunca borra en el destino (`sync` sí: cuidado).
- Aviso "shared client_id is being retired": el client_id compartido de rclone
  dejará de funcionar en 2026; hay que crear uno propio en Google Cloud
  (pendiente; es el mismo trámite que necesitará la app para Drive en el cel).

**Dónde.** `core/drive.py` (`upload`, `download_recent`, `drive_status`);
guía paso a paso en `docs/respaldo.md`.

## 29. Del código al APK: datos, firma y versiones

**Qué es.** `flet build apk` mete tu código + Python + las dependencias de
`pyproject.toml` en una app de Android. Tres ideas clave:

**1. El código y los datos van en lugares distintos.**

```
 APK instalado
 ├─ carpeta de la app (código)     ← se REEMPLAZA en cada actualización
 └─ carpeta privada de datos       ← se CONSERVA  (FLET_APP_STORAGE_DATA)
      ├─ ControlKraken.db
      ├─ data/  (adjuntos, capturas)
      └─ respaldos/
```

Por eso `core/database.py` calcula `DATA_ROOT`: en el celular la carpeta
privada; en la compu, la del proyecto. Se detecta el celular por las variables
que Android define (`ANDROID_ROOT`), NO por `FLET_APP_STORAGE_DATA`, porque
`flet run` en la compu también la define.

**2. La firma.** Android solo acepta una actualización firmada con la misma
llave (`.jks`). Sin ella → desinstalar → se pierden los datos. Va fuera del
repo (`~/.claves`) y su contraseña no se guarda en archivos (el script la pide).

**3. Dos números de versión.**

| | Qué es | De dónde sale |
|---|---|---|
| `build-version` | lo que ves: 1.0.0 | `APP_VERSION` |
| `build-number` | entero interno que SIEMPRE debe subir | `git rev-list --count HEAD` |

**Extra:** `pyproject.toml` → `[tool.flet.app].exclude` deja fuera del APK tu
BD y adjuntos personales; `[tool.flet.compile] app = false` + Alembic
`sourceless` para que las migraciones se encuentren dentro del paquete.

**Dónde.** `core/database.py` (`ES_MOVIL`, `DATA_ROOT`), `pyproject.toml`,
`scripts/build_apk.sh`, `docs/apk.md`.

## 30. El candado de la BD: por qué se perdieron Desarrollo, Proyectos y Agenda

**Qué pasó.** Se cambió en el código `movimientos.db` → `ControlKraken.db`.
Al abrir, la app buscó `ControlKraken.db`, no la encontró y `init_db()` hizo lo
que hace con una compu nueva: crear una BD VACÍA y migrarla. Finanzas se
recuperó porque se volvió a importar del Excel; lo demás no tenía otra copia.

```
 antes:   código → ControlKraken.db ?  ✗ no existe → BD nueva vacía
 ahora:   código → ControlKraken.db ?  ✗ → ¿movimientos.db? ✓ → se RENOMBRA
```

**Lección.** Cambiar el nombre/ubicación de un archivo de datos es una
*migración*, no un cambio de texto: hay que mover lo viejo, no solo apuntar a
lo nuevo. (En Odoo pasa igual con un campo renombrado sin script de migración:
la columna vieja se queda huérfana y la nueva nace vacía.)

**Dónde.** `core/database.py` → `_adopt_previous_db()` (se llama al inicio de
`init_db()`), `DB_NOMBRES_ANTERIORES`.

## 31. De Selection a catálogo: etapas como los stage_id de Odoo

**Qué es.** Antes `Proyecto.estado` era texto fijo ("activo", "pausa"…). Ahora
es un Many2one a un **catálogo** (`EtapaProyecto`), igual que `stage_id` en
Odoo: registros que tú creas, ordenas y coloreas. Lo mismo para el tipo de
entrada (`TipoEntrada`) y las columnas de tareas (`EtapaTarea`).

**El truco: la "clase".** Si las etapas son libres, ¿cómo sabe la app cuál es
"terminado"? Cada etapa guarda QUÉ SIGNIFICA (`clase`): en_curso, pausa,
terminada, cancelada. Tú le pones el nombre que quieras ("En revisión") y el
código pregunta por la clase, no por el nombre (como `fold`/`is_closed` en Odoo).

```
 proyectos.etapa_id ──► proyecto_etapas (nombre, secuencia, clase, color)
 proyecto_entradas.tipo_id ──► proyecto_tipos_entrada (nombre, es_hito, icono)
 tareas.etapa_id ──► tarea_etapas (nombre, cerrada)
 proyecto_etapas_tarea  = Many2many: qué columnas de tarea usa cada proyecto
```

**Piezas de SQLAlchemy que aparecieron:**
- `relationship(lazy="joined")`: la etapa llega en la MISMA consulta que el
  proyecto (un JOIN). Así `pro.etapa.nombre` funciona aunque la sesión ya se
  cerró (sin esto: `DetachedInstanceError`).
- `relationship(secondary=tabla)`: Many2many con tabla intermedia
  (como `many2many` de Odoo con su `relation`).
- `Proyecto.etapa.has(EtapaProyecto.clase == "terminada")`: filtrar por un
  campo del registro relacionado (como un dominio `[("etapa_id.clase", "=", …)]`).
- `CatalogoMixin.delete` no deja borrar si está en uso: `ondelete="restrict"`.

**La migración (0011)** sigue la receta de la 0004: crear catálogo → llenarlo →
columna nueva opcional → copiar texto→id → hacerla obligatoria → borrar la vieja.

**Dónde.** `modulos/proyectos/models/catalogos.py`,
`alembic/versions/0011_proyectos_etapas.py`, pantalla
`modulos/proyectos/views/ajustes.py`.

## 32. Kanban con Flet: Draggable + DragTarget

**Qué es.** Flet trae arrastrar y soltar:

```
 Row(scroll)                      ← el tablero se desliza de lado
  ├ DragTarget(group="tareas")    ← columna "Por hacer"
  │   └ tarjeta ─ Draggable(group="tareas", data=7)   ← la manija ⋮⋮
  └ DragTarget(group="tareas")    ← columna "Hecho"
        on_accept(e): e.src.data == 7  → move_task(7, etapa)
```

- Solo se acepta si `group` coincide (proyectos y tareas no se mezclan).
- `on_will_accept` / `on_leave`: pintamos la columna mientras pasas encima.
- **Por qué solo la manija es arrastrable**: si toda la tarjeta fuera
  Draggable, al deslizar el tablero con el dedo empezarías a arrastrarla. Con
  la manija, el resto de la tarjeta sigue deslizando y abriendo.
- En el celular arrastrar puede ser incómodo: el menú ⋮ "Mover a…" hace lo mismo.

**Regla de negocio** (`services.move_task`): llevar una tarea a una etapa
`cerrada` = marcarla hecha con su `Cumplimiento` (igual que en la Agenda);
sacarla = deshacer el último. Una sola verdad para Agenda y Proyecto.

**Dónde.** `modulos/proyectos/views/comun.py` (`kanban_board`, `drag_handle`,
`move_menu`), `views/tareas.py`, `services.py` (`move_task`, `tasks_by_stage`).

## 33. Cómo se probó sin celular: Flet en el navegador + Playwright

Para ver las pantallas se corrió la app como página web y un navegador sin
ventana (Playwright) tomó capturas y simuló toques y arrastres:

```python
ft.run(main, view=ft.AppView.WEB_BROWSER, port=8551, no_cdn=True)
```

- `no_cdn=True`: usa los archivos de Flutter que trae `flet-web` en vez de
  bajarlos de internet.
- El navegador necesita un idioma (`locale="es-MX"`); sin él Flutter truena con
  "Incorrect locale information provided".
- Siempre sobre una **copia** de la BD, nunca la tuya.

## 34. Una sola tabla de adjuntos (como ir.attachment de Odoo)

**Qué es.** En vez de una tabla de adjuntos por módulo (`dev_adjuntos`,
`proyecto_adjuntos`, …), una sola tabla `adjuntos` donde cada fila dice de
quién es con dos columnas:

```
 adjuntos.modelo      = "agenda.tarea"     ← como res_model en Odoo
 adjuntos.registro_id = 12                 ← como res_id
```

Esto se llama **relación polimórfica**: `registro_id` puede apuntar a filas de
distintas tablas según `modelo`.

**Lo que se gana:** un solo modelo, un solo componente de pantalla
(`AttachmentsBox`) y cualquier módulo nuevo (Memorias, Kraken Tools) adjunta
sin crear tablas.

**Lo que se paga:** la BD ya no puede tener una llave foránea real (¿a qué
tabla apuntaría?). Por eso:
- Al borrar un registro, su dueño llama `Adjunto.delete_for(modelo, id)`:
  el "ondelete=cascade" se hace en código (igual que Odoo con `ir.attachment`).
- Para seguir escribiendo `pendiente.adjuntos` se usa una relación de solo
  lectura con un JOIN armado a mano:

```python
adjuntos = relationship(
    Adjunto,
    primaryjoin="and_(Adjunto.modelo == 'dev.pendiente', "
                "foreign(Adjunto.registro_id) == Pendiente.id)",
    viewonly=True,
)
```

`foreign(...)` le dice a SQLAlchemy cuál lado "apunta" (como si hubiera FK) y
`viewonly=True` que no intente guardar por ahí. Esto vive en
`attachments_relation()` para no repetirlo.

**La migración (0012)** crea la tabla, copia las filas viejas (la `ruta` se
copia tal cual: los archivos no se mueven) y borra las tablas viejas. El
downgrade las regresa.

**Dónde.** `core/adjuntos.py` (modelo), `core/adjuntos_ui.py` (pantalla),
`alembic/versions/0012_adjuntos_unicos.py`.

## 35. Probar que el respaldo está completo (sin listas fijas)

**El problema.** Cada módulo nuevo agrega tablas; si el respaldo dependiera de
una lista, tarde o temprano alguien olvida agregar una.

**La idea.** `scripts/verificar_respaldo.py` no conoce ninguna tabla por
nombre: las lee de `Base.metadata.sorted_tables` (todas las que declaran los
modelos, ordenadas para que los padres vayan antes que los hijos), mete un
registro de prueba en cada una según el tipo de cada columna, respalda,
"formatea" (borra BD y data/), restaura y compara.

Corre en una carpeta temporal gracias a `CK_DATA_ROOT`, así que nunca toca tu
BD. Úsalo cada vez que agregues un módulo:

```bash
python scripts/verificar_respaldo.py
```

**Dónde.** `scripts/verificar_respaldo.py`, `core/database.py` (`CK_DATA_ROOT`).

## 36. Avisos con la app cerrada: quién despierta a quién

**Qué es.** Python solo corre mientras la app está abierta. Para que llegue un
aviso con la app cerrada, alguien más tiene que "despertar": el sistema
operativo.

```
 app abierta ──► programa la alarma en Android (AlarmManager)
                          │
 app cerrada              ▼  a la hora indicada
                 Android muestra la notificación  (Python ni se entera)
```

- **Exacta vs inexacta**: Android agrupa las alarmas inexactas para ahorrar
  batería (pueden llegar unos minutos tarde); las exactas necesitan el
  permiso `SCHEDULE_EXACT_ALARM`.
- **Lo que las borra**: "Forzar detención" de la app y algunos modos de ahorro
  de batería (Xiaomi, Huawei…). Reiniciar no, si la app registra el
  "boot receiver" (lo agrega el parche de la extensión).
- **Extensión de Flet**: Flet deja usar paquetes de Flutter desde Python
  (aquí `flutter_local_notifications` vía `flet-android-notifications`). Al
  compilar, `flet build` registra la parte de Flutter que trae el paquete
  ("Registered Flutter user extensions").

**Resultado de la prueba (14 oct 2026)**: Redmi Note 14 Pro+ 5G, HyperOS 3.0 /
Android 16. Llegaron los avisos exacto e inexacto con la app cerrada y también
después de reiniciar (salen hasta el primer desbloqueo: antes Android no deja
correr las apps).

**Dónde.** `pruebas/notificaciones/` (app de prueba aparte).

## 37. Avisos de la Agenda: proveedores, eventos y "reprograma todo"

**Cómo está armado (1.2.1):**

```
 core/avisos.py              ← habla con Android (permiso, programar, probar)
   upcoming() = junta lo que dicen los PROVEEDORES (próximos 14 días)
        ▲
 modulos/agenda/avisos.py    ← proveedor: tareas pendientes → [Aviso(cuando, título, texto)]
```

Un módulo nuevo (Notas, Kraken Tools) solo registra su función con
`register_provider(...)`: no toca `core/avisos.py`.

**"Reprograma todo" en vez de llevar la cuenta.** Cada vez se hace
`cancel_all()` y se vuelve a programar lo de las próximas 2 semanas. Así nunca
queda un aviso de una tarea que cambiaste o borraste, y no hay que guardar qué
id de alarma corresponde a qué tarea.

**¿Quién avisa que algo cambió? Eventos de SQLAlchemy.** En vez de que cada
pantalla se acuerde de reprogramar:

```python
event.listen(Tarea, "after_update", _changed)   # también after_insert / after_delete
```

Es como heredar `write()` en Odoo para avisarle a otro módulo. Para no
reprogramar 3 veces si guardas 3 cosas seguidas, `request_sync()` espera 1.5 s
y solo la última petición hace el trabajo (*debounce*).

**Trampa que salió en las pruebas:** con `mapped_column(..., default=0)`,
SQLAlchemy usa el default **también cuando le pasas `None`**: "Sin aviso" se
guardaba como "a la hora". Solución: sin `default` en la columna y que los
formularios siempre manden el valor.

**El parche en cada build.** `flet build` genera el proyecto Android en
`build/flutter`; la extensión necesita parcharlo (receptores en el manifest y
*desugaring* en Gradle). `scripts/build_apk.sh` lo aplica y, si Flet regeneró
el proyecto, compila otra vez.

**Dónde.** `core/avisos.py`, `modulos/agenda/avisos.py`,
`modulos/configuracion/avisos.py`, migración 0013, `scripts/build_apk.sh`.


## 38. Notas: guardado automático, búsqueda con EXISTS y tarjetas en 2 columnas

**Guardado automático sin botón.** El editor pide guardar en cada cambio, pero
espera 0.8 s sin teclear (mismo *debounce* que los avisos, nota 37): con un
contador de "turno", solo la última petición guarda. Al salir se guarda al
instante y, si la nota quedó vacía, se borra.

**No redibujar mientras escribes.** Cada casilla es un `TextField`; al teclear
solo se actualiza un dict en memoria. La pantalla se reconstruye únicamente al
agregar, quitar o palomear. Si se reconstruyera en cada tecla, el cursor
saltaría al inicio.

**Guardar la "foto completa".** El editor manda título, cuerpo y TODAS las
casillas; el servicio reemplaza las casillas de la nota. Es más simple que
llevar la cuenta de cuál se agregó/movió/borró, y una lista del súper es chica.

**Buscar dentro de las casillas: EXISTS.** "¿Hay alguna casilla de esta nota
que contenga el texto?":

```python
en_items = exists().where(NotaItem.nota_id == Nota.id,
                          func.lower(NotaItem.texto).like("%leche%"))
Nota.search(or_(func.lower(Nota.titulo).like(...), en_items))
```

Es el equivalente a un dominio de Odoo sobre un One2many:
`[("items.texto", "ilike", "leche")]`. Ojo: `lower()` de SQLite solo cambia
letras sin acento (SÚPER ≠ súper); buscar en minúsculas siempre funciona.

**Tarjetas en 2 columnas: `ResponsiveRow`.** La fila se divide en 12; cada
tarjeta pide `col={"xs": 6, "md": 4}`: 2 por fila en el celular, 3 en pantallas
anchas. Como `GridView` obliga a que todas midan lo mismo, aquí cada tarjeta
mide lo que necesita.

**Dejar presionado.** `Container(on_long_press=...)` abre un `BottomSheet` con
las acciones (como en Keep).

**Dónde.** `modulos/notas/` (models, services, views/tablero.py,
views/editor.py, exportador.py), migración 0014.


## 39. Memorias: fotos con Pillow, "un día como hoy" y diseño listo para la voz

**Las fotos se copian, no se referencian.** Guardar la ruta de la galería del
celular sería frágil (si borras o mueves la foto, la memoria se queda sin
ella). Se copia a `data/memorias/<id>/` y entra al respaldo.

**Qué le hace Pillow a cada foto** (`modulos/memorias/imagenes.py`):

```
 foto del celular (4000×3000, 5 MB, "acostada" + etiqueta EXIF de giro)
   │ ImageOps.exif_transpose()   ← la gira de verdad (si no, sale de lado)
   │ thumbnail((3072, 3072))     ← solo si es más grande; conserva proporción
   │ save(JPEG, quality=92)      ← a simple vista igual; pesa mucho menos
   └ miniatura 480 px (JPEG 80)  ← para la galería y la línea de tiempo
```

La fecha se lee del EXIF (`DateTimeOriginal`, etiqueta 36867, dentro del
sub-bloque 0x8769) para proponerla como fecha de la memoria.

**"Un día como hoy" en SQL.** SQLite guarda las fechas como texto
`AAAA-MM-DD`; se compara solo mes y día:

```python
func.strftime("%m-%d", Memoria.fecha) == hoy.strftime("%m-%d")
```

**Filtrar por un Many2many: `.any()`.** "Memorias que tengan ALGUNA de estas
etiquetas":

```python
Memoria.etiquetas.any(EtiquetaMemoria.id.in_(ids))
```

(en Odoo: `[("etiqueta_ids", "in", ids)]`).

**Miniaturas que llenan el cuadro.** Un `ft.Image(fit=COVER)` necesita ancho y
alto fijos; en una cuadrícula el ancho lo decide `ResponsiveRow`. Por eso la
foto va como imagen de **fondo** del `Container`
(`image=ft.DecorationImage(src=…, fit=COVER)`) con `aspect_ratio=1`.

**Listo para la voz sin tocar tablas.** `Memoria.origen` ("texto" | "voz"); el
audio será un adjunto más (mimetype `audio/…`) y el relato, su transcripción.

**Lección: `scripts/verificar_flet.py`.** `ft.ActionChip` no existe en Flet 1.0
y pyflakes no lo ve (es un atributo, no un nombre): la pantalla tronaba al
abrirse. El script revisa cada `ft.Algo` contra el Flet instalado. Córrelo
antes de compilar y al actualizar Flet.

**Dónde.** `modulos/memorias/` (models, services, imagenes.py, views/),
migración 0015, `scripts/verificar_flet.py`.

---

## 40. Cliente HTTP: httpx async, cancelar y `{{variables}}`

**Qué es una petición HTTP.** Lo que hace el navegador o una app al hablar con
un servidor: un **método** (GET leer, POST crear, PUT/PATCH cambiar, DELETE
borrar), una **URL** (con `?params=...`), **headers** (datos extra:
`Content-Type`, `Authorization`…) y a veces un **body** (JSON, texto o
formulario). Regresa un **código** (2xx bien, 3xx redirección, 4xx error tuyo,
5xx error del servidor), headers y un body. Un 404 *sí es* una respuesta; un
"no se pudo conectar" no lo es (por eso el error va aparte en `Resultado.error`).

**Por qué httpx y no requests.** `requests` solo es síncrono: mientras espera,
el hilo se queda parado. `httpx` tiene `AsyncClient`, y `await cliente.send(...)`
suelta el control mientras llega la respuesta. Así la pantalla sigue viva y se
puede **cancelar**:

```python
async def send(self, e=None):
    self._tarea = asyncio.current_task()      # el botón Cancelar guarda esta tarea
    try:
        self.resultado = await services.send(self.b)
    except asyncio.CancelledError:            # alguien llamó self._tarea.cancel()
        notify(self.page, "Envío cancelado")
```

`task.cancel()` hace que el `await` en curso lance `CancelledError`. El servicio
lo deja pasar (no lo atrapa como "error de red") y así no ensucia el historial.

**Leer por trozos (`stream=True`).** La respuesta se lee con `aiter_bytes()` y
se corta a los 50 MB: una descarga gigante no se come la memoria del celular.

**Variables `{{así}}`.** Una expresión regular busca `{{nombre}}` y lo cambia
por su valor: primero las Globales y encima las del entorno elegido (un `dict`
actualizado con `update()`: si las dos tienen `token`, gana el entorno). Las que
no existen se quedan tal cual y el editor las avisa ("Sin definir: {{token}}").

**Historial con límites configurables.** Cada envío se guarda (lo mandado y lo
recibido). En Ajustes eliges cuántos envíos y cuánto de cada respuesta;
recortar texto UTF‑8 por bytes sin romper una "ñ" a la mitad:
`datos[:limite].decode("utf-8", errors="ignore")`.

**Listas clave/valor en JSON.** Params, headers, formulario y variables se
guardan en una columna `JSON`: `[{"clave": "page", "valor": "2", "activo": true}]`.
Una petición es una sola fila y se copia o respalda completa. (En Odoo sería
como un campo `Json`/serializado en vez de un One2many: para listas chicas que
siempre se leen juntas, conviene.)

**Dónde.** `modulos/kraken/http/services.py` (`build`, `send`, `variables`,
`prune_history`), `views/editor.py` (`send`, `cancel`), `models/ajustes.py`.


## 41. cURL: `shlex` para leer comandos como la terminal

**Qué es.** `curl` es el cliente HTTP de la terminal. Chrome (F12 → Network →
clic derecho → *Copy as cURL*), Postman y casi toda documentación de APIs te
dan las peticiones como un `curl ...`. Pegarlo en la app y que se llene sola
ahorra mucho.

**Partirlo bien: `shlex.split`.** Separar por espacios no sirve: los textos
entre comillas traen espacios. `shlex` parte como lo haría la terminal:

```python
shlex.split("curl -H 'Authorization: Bearer x' -d '{\"a\": 1}' https://x.com")
# ['curl', '-H', 'Authorization: Bearer x', '-d', '{"a": 1}', 'https://x.com']
```

Y al revés, `shlex.quote()` pone comillas solo donde hace falta para "Copiar
como cURL". Antes se quitan los `\` de fin de línea (comandos de varias líneas).

**Reglas que imita.** `-d` sin `-X` → POST; `?a=1` de la URL → pestaña Params;
`Authorization: Bearer …` → pestaña Auth; `-u usuario:clave` → Basic; si el
body parece JSON → tipo JSON. Opciones que no importan aquí (`-s`, `-L`, `-k`,
`--compressed`) se ignoran.

**Truco.** Pegar un `curl …` directo en el campo de la URL también lo importa.

**Dónde.** `modulos/kraken/http/services.py` → `parse_curl()`, `to_curl()`.


## 42. SQLite por dentro: solo lectura real, PRAGMA y archivos fuera del respaldo

**Solo lectura de verdad.** No basta con "no mostrar el botón": la conexión se
abre en modo lectura y SQLite mismo rechaza cualquier escritura:

```python
sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
con.execute("PRAGMA query_only = 1")    # segundo candado
# DELETE ... -> sqlite3.OperationalError: attempt to write a readonly database
```

La BD de ControlKraken siempre se abre así: el explorador no puede romper la app.

**Mirar adentro con PRAGMA.** Son "comandos de consulta" de SQLite:
`PRAGMA table_info(t)` (columnas, tipo, NOT NULL, PK), `foreign_key_list(t)`
(llaves foráneas), `index_list(t)` + `index_info(i)` (índices). Y
`sqlite_master` es la tabla donde SQLite guarda el `CREATE` de todo. Es lo que
muestran DBeaver o pgAdmin, sin instalar nada.

**Varias sentencias y "todo o nada".** `sqlite3.complete_statement()` dice si
un texto es una sentencia completa (respeta los `;` dentro de comillas). Se
ejecutan una por una dentro de la misma transacción: si una falla,
`rollback()` y no se aplica ninguna.

**Copiar en vez de abrir el original.** En Android el FilePicker regresa el
contenido, no una ruta estable. Por eso las bases se copian a
`data/kraken/bases/` (como los adjuntos). "Descargar copia" usa la API de
respaldo de SQLite (`origen.backup(destino)`), la misma que el respaldo de la
app: copia consistente aunque la base esté abierta.

**Archivos fuera del respaldo (gancho en `core/backup.py`).** Un módulo
registra una función que dice qué archivos de `data/` NO van al zip:

```python
backup.register_exclusion(_files_outside_backup)   # bases con respaldar=False
```

El respaldo los salta, y al **restaurar** se apartan y se regresan, para que
no se pierdan de este equipo (el zip no los trae). Si algo falla al preguntar,
se respalda todo: mejor un zip de más que un archivo perdido.

**El SQL en otro hilo.** `await asyncio.to_thread(services.run, base, sql)`
(nota 19): una consulta pesada no congela la pantalla.

**Dónde.** `modulos/kraken/sqlite/services.py`, `views/base.py`,
`models/sqlite.py`, `core/backup.py` (`register_exclusion`, `excluded_files`),
`scripts/verificar_kraken.py` (prueba todo sin celular ni internet).


## 43. Red: sockets, ping sin ser root y puertos en paralelo

**Socket.** El "enchufe" de red de un programa. `TCP` es una llamada telefónica
(se conecta, hay respuesta, llega en orden: web, SSH, bases de datos). `UDP` es
mandar una postal (sin conexión: DNS, Wake-on-LAN). `ICMP` es el idioma de los
avisos de red: el ping manda un "echo request" y espera un "echo reply".

**Ping sin ser administrador.** El ping clásico usa un socket "crudo" (raw),
que exige root. Linux y Android permiten otro tipo, **ICMP de datagrama**, si el
sistema lo autoriza (`/proc/sys/net/ipv4/ping_group_range`); el sistema pone el
identificador y la suma de verificación por nosotros:

```python
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
s.sendto(struct.pack("!BBHHH", 8, 0, 0, 0, seq) + b"datos", (ip, 0))  # 8 = echo
```

Si no se permite: el `ping` del sistema y, al final, **ping TCP** (cuánto tarda
en conectar al 443/80). Un "conexión rechazada" también cuenta: el equipo
contestó, está vivo. La pantalla dice qué manera se usó.

**Abierto, cerrado, filtrado.** Al conectar a un puerto: conecta → *abierto*;
`ConnectionRefusedError` (el equipo mandó "aquí no hay nadie") → *cerrado*;
no contesta a tiempo → *filtrado* (firewall o equipo apagado).

**Cientos a la vez sin saturar: `asyncio.Semaphore`.** `gather()` lanza todas
las conexiones, y un semáforo deja pasar solo N al mismo tiempo (como un cadenero):

```python
limite = asyncio.Semaphore(100)
async def one(p):
    async with limite:              # espera turno si ya hay 100 adentro
        return await tcp_connect(ip, p, timeout)
await asyncio.gather(*(one(p) for p in puertos))
```

**Dispositivos en mi red.** Lo mismo, pero a las 254 direcciones de tu red
(`ipaddress.ip_network("192.168.1.0/24").hosts()`) con 12 puertos comunes; el
que contesta en cualquiera existe. Por sus puertos se adivina qué es (62078 →
iPhone, 8009 → Chromecast, 9100 → impresora). Solo deja redes **privadas**
(`rango.is_private`): así nunca se barre internet por error. Android 10+ ya no
deja leer la tabla ARP (MAC y fabricante); en Linux sí (`/proc/net/arp`).

**Pintar mientras corre.** Ping y puertos llaman `on_progress(resultado)`; la
pantalla repinta solo el resultado, sin más de ~5 veces por segundo.

**Dónde.** `modulos/kraken/red/ping.py`, `puertos.py`, `dispositivos.py`,
`views/prueba.py` (`_progress`, `cancel`).


## 44. DNS, certificados, Whois y Wake-on-LAN por dentro

**DNS.** La "agenda" de internet: nombre → IP. Registros: `A`/`AAAA` (IP),
`CNAME` (alias), `MX` (quién recibe el correo), `TXT` (SPF, verificaciones),
`NS` (quién administra el dominio), `PTR` (al revés: IP → nombre). Con
**dnspython** se le pregunta a UN servidor que tú eliges (1.1.1.1 por defecto),
no al del celular, para ver lo que ve internet y no una respuesta guardada:

```python
resolver = dns.asyncresolver.Resolver(configure=False)  # no lee la config del equipo
resolver.nameservers = ["1.1.1.1"]
respuesta = await resolver.resolve("ejemplo.com", "MX")
```

**Certificado HTTPS.** Se conecta como un navegador (`ssl.create_default_context()`
verifica firma, fechas y dominio). Si falla, `SSLCertVerificationError` dice por
qué (vencido, autofirmado, de otro dominio) y se vuelve a conectar sin verificar
solo para leer sus datos (`getpeercert(binary_form=True)`). Los días que le
quedan: `ssl.cert_time_to_seconds(cert["notAfter"])`.

**Whois.** Primero **RDAP** (API web con JSON; `rdap.org` te manda al servidor
del dominio). Si no hay (varios `.mx`), **WHOIS** clásico: TCP al puerto 43,
mandas el dominio y regresa texto libre. Se pregunta a `whois.iana.org` quién
lleva el `.mx`/`.com` y luego a ese. Las fechas vienen en mil formatos
(`2026-03-15T04:00Z`, `15-mar-2026`, `2026.03.15`): se prueban varios patrones.

**Wake-on-LAN.** UDP a toda la red (broadcast `255.255.255.255`, puertos 9 y 7):
6 bytes `FF` + la MAC repetida 16 veces = 102 bytes. Hay que permitir broadcast
en el socket: `s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)`.

**Mi IP local sin mandar nada.** Un socket UDP "conectado" a 1.1.1.1 no envía
paquetes, pero el sistema decide por qué interfaz saldría:
`s.connect(("1.1.1.1", 80)); s.getsockname()[0]` → `192.168.1.37`.

**Dónde.** `modulos/kraken/red/consulta_dns.py`, `certificado.py`, `whois.py`,
`wol.py`, `mi_ip.py`. Equipos y pruebas: tablas `kt_equipos` y
`kt_historial_red` (migración 0017).


## 45. Probar red sin internet: servidores falsos

`scripts/verificar_kraken.py` levanta, en hilos y en `127.0.0.1`, servidores
que se comportan como los de verdad: un **DNS** con dnspython
(`dns.message.make_response`), un **WHOIS** (puerto 43) con `socketserver`,
**RDAP** e **ipinfo** en el mismo servidor HTTP de prueba, un **HTTPS** con
certificado autofirmado (openssl) y uno vencido, y un socket UDP que recibe
el paquete de Wake-on-LAN. Los servicios aceptan la dirección como parámetro
(`servidor=`, `rdap=`, `iana=`, `puerto=`), así la prueba no necesita internet
y la app usa los reales.


## 46. SSH con paramiko: huella del servidor y sudo sin teclado

**SSH** es la forma estándar de entrar a un servidor Linux por la red, cifrado
(puerto 22). **paramiko** es SSH escrito en Python. Es puro Python, pero usa
`cryptography`, `bcrypt` y `PyNaCl`, que tienen partes en C: en el APK solo
funcionan si Flet las tiene compiladas para Android. Por eso primero se probó
con una app aparte (`pruebas/ssh/`) y se fijaron esas versiones en `pyproject.toml`.

**Correr un comando:**

```python
cliente = paramiko.SSHClient()
cliente.connect(host, port=22, username="edgar", password="…", timeout=10)
entrada, salida, error = cliente.exec_command("uptime")
texto = salida.read().decode(); codigo = salida.channel.recv_exit_status()
```

**Huella del servidor (TOFU, "confía la primera vez").** Cada servidor tiene una
llave; su huella (`SHA256:zTVm…`) es como su cédula. La primera conexión la
guarda en el equipo (`ssh_huella`); las siguientes la comparan. Si cambia, NO
se conecta y pregunta: puede ser que reinstalaron el servidor… o que alguien se
hace pasar por él (ataque de intermediario). Es lo mismo que hace `ssh` con
`~/.ssh/known_hosts` y su aviso "REMOTE HOST IDENTIFICATION HAS CHANGED".

**sudo sin teclado.** Un comando con `sudo` se queda esperando la contraseña.
Con `sudo -S -p ''` sudo la lee de la entrada estándar (sin mostrar el
"[sudo] password:"), y la app se la escribe por el canal:

```python
entrada, salida, error = cliente.exec_command("sudo -S -p '' systemctl restart odoo")
entrada.write(clave + "\n"); entrada.flush()
```

**paramiko es bloqueante**: todo se llama con `asyncio.to_thread` (nota 19) para
no congelar la pantalla.

**Dónde.** `modulos/kraken/ssh/conexion.py` (`Sesion`, `HuellaCambio`),
`acciones.py`, `views/comandos.py`; migración 0018.


## 47. Panel en vivo: /proc, diferencias y "solo mientras lo ves"

**Un solo comando para todo.** En vez de 8 idas y vueltas, un script que
imprime secciones marcadas (`@@cpu`, `@@mem`, `@@df`…) y Python las separa.
Lleva `export LC_ALL=C` para que el servidor conteste en inglés y con formato
fijo: tu PC en español decía "Inter" y "S.ficheros" en vez de "Swap" y
"Filesystem".

**/proc: el sistema contado como archivos.** `/proc/meminfo` (memoria),
`/proc/loadavg` (carga), `/proc/uptime` (tiempo encendido), `/proc/net/dev`
(bytes de red), `/proc/stat` (tiempo de CPU).

**CPU % = diferencia entre dos lecturas.** `/proc/stat` cuenta cuánto tiempo
lleva el CPU trabajando y descansando DESDE QUE PRENDIÓ. Un número suelto no
dice nada; dos lecturas separadas 5 s sí:

```
% CPU = (ocupado_ahora − ocupado_antes) / (total_ahora − total_antes) × 100
```

Igual con la red: (bytes ahora − bytes antes) / segundos = velocidad. Por eso
la primera lectura muestra "Midiendo…".

**RAM "usada" de verdad.** Se usa `MemAvailable` (lo que de verdad se puede
pedir), no `MemFree`: Linux usa la RAM libre como caché y la suelta cuando
hace falta, así que "free" casi siempre parece lleno.

**Solo mientras lo ves.** El ciclo (`while self.activo: leer; esperar 5 s`) se
detiene al salir de la pantalla y cierra la conexión. Si la app se va a segundo
plano, `page.on_app_lifecycle_state_change` avisa (`PAUSE`/`HIDE`) y el ciclo
se pausa; al volver (`RESUME`/`SHOW`) se despierta con un `asyncio.Event` y lee
al instante.

**Dónde.** `modulos/kraken/ssh/metricas.py` (`SCRIPT`, `parse`),
`views/panel.py` (`_loop`, `_on_lifecycle`).


## 48. Una sola pantalla para tres motores: DB-API

**Qué es.** Python tiene un "contrato" para hablar con bases de datos, la
**DB-API** (PEP 249): `con = conectar(...)`, `cur = con.cursor()`,
`cur.execute(sql, params)`, `cur.fetchmany(n)`, `cur.description` (nombres de
columnas), `con.commit()` / `con.rollback()`. `sqlite3`, **pg8000**
(PostgreSQL) y **PyMySQL** lo cumplen, así que la pantalla de SQL es la misma
para los tres.

**Lo que NO es igual** va en una clase por motor (`Sqlite`, `Postgres`,
`Mysql` en `MOTORES`): cómo se escriben los nombres (`"tabla"` vs `` `tabla` ``),
de dónde salen las tablas (`sqlite_master` vs `information_schema`), el
marcador de parámetros (`?` vs `%s`) y cómo contar filas.

**Contar filas sin tardar minutos.** `SELECT count(*)` en una tabla de 50
millones de filas recorre todo. PostgreSQL y MySQL guardan un estimado
(`pg_class.reltuples`, `information_schema.TABLES.TABLE_ROWS`): se usa ese y se
muestra con **~**. En las páginas de datos, si el estimado pasa de 1 millón, el
total también es aproximado.

**Por qué pg8000 y PyMySQL** (y no psycopg2 / mysqlclient): son **puro
Python**, sin partes en C, así que funcionan en el APK sin depender de que Flet
los tenga compilados (nota 46).

**Dónde.** `modulos/kraken/sqlite/motores.py` (`MOTORES`, `opened`, `page`),
`services.py` (`run`, `test_server`, `friendly_connect_error`).


## 49. Solo lectura y 30 s: que lo cuide el servidor

**El problema.** Revisar si el SQL "empieza con SELECT" no basta: un
`SELECT funcion_que_borra()` o un `WITH x AS (DELETE …)` pasan el filtro.

**La solución:** al conectar, se le pide AL SERVIDOR que la sesión sea de solo
lectura. Ahí ya no hay truco que valga: el servidor rechaza cualquier escritura.

```sql
-- PostgreSQL
SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;
SET statement_timeout = '30s';
-- MySQL / MariaDB
SET SESSION TRANSACTION READ ONLY;
SET SESSION MAX_EXECUTION_TIME = 30000;   -- MySQL (MariaDB: max_statement_time = 30)
```

Con "Permitir cambios" todo corre en una transacción: si falla una sentencia,
`rollback()` y no se aplica ninguna. El **timeout** evita que una consulta
olvidada (sin `WHERE`, sin `LIMIT`) deje trabajando al servidor del cliente.

**Dónde.** `motores.py` (`Postgres.connect`, `Mysql.connect`,
`is_read_only_error`), `services.py` (`_friendly_error`).


## 50. Túnel SSH: llegar a la base sin abrir puertos

**El caso.** El PostgreSQL de un cliente escucha solo en `localhost` del
servidor (lo correcto). Desde el celular no se llega… pero por SSH sí.

**Cómo funciona** ("local port forwarding", lo mismo que `ssh -L`):

```
celular: 127.0.0.1:41873  ──(dentro de la conexión SSH)──▶  servidor: localhost:5432
```

1. La app abre un puerto local al azar (`127.0.0.1:0` = "el que esté libre").
2. Cada conexión que llega ahí se manda por SSH con un canal `direct-tcpip`:
   `transporte.open_channel("direct-tcpip", ("localhost", 5432), origen)`.
3. Un hilo pasa bytes de un lado al otro (`select` sobre los dos sockets).
4. pg8000 / PyMySQL se conectan a `127.0.0.1:41873` sin saber nada de SSH.

En el servidor no se abre nada nuevo: el tráfico va cifrado por el puerto 22.
Los túneles se reutilizan mientras ves la base y se cierran al salir
(`tunel.close_all()`). En el diálogo, "Host" es como lo ve el servidor SSH
(casi siempre `localhost`).

**Dónde.** `modulos/kraken/ssh/tunel.py` (`Tunel`, `tunnel_for`, `close_all`),
`motores.py` (`opened`).


## 51. Consola SSH sin terminal: carpeta, sudo y Ctrl+C

**Sin TTY.** Una terminal de verdad (la de `ssh` en la PC) pide una "pantalla"
al servidor (pty) para programas como vim o htop. La consola de la app no: cada
comando corre en un `bash -l -s` nuevo y se lee su salida. Es más simple y
estable en el celular; a cambio, vim/nano/htop/less no se pueden (se avisa qué
usar).

**¿Cómo se recuerda la carpeta si cada comando es un bash nuevo?** El script
que se manda envuelve tu comando y al final imprime una marca con el código de
salida y la carpeta en que quedó:

```bash
{
cd '/opt/odoo' 2>/dev/null || cd
<tu comando>
__ck_c=$?
printf '\n__CK_FIN_7f3a__ %s %s\n' "$__ck_c" "$(pwd)"
} < /dev/null 2>&1
```

La app quita esa marca de la salida y guarda la carpeta para el siguiente
comando. El bloque `{ }` hace que bash lea TODO el script antes de correrlo;
`< /dev/null` evita que un comando se "coma" el resto del script esperando
teclado; `2>&1` junta errores y salida en orden, como en una terminal.

**sudo en cualquier parte.** Se define una función `sudo` que primero valida
la contraseña guardada con `sudo -S -v` y luego corre `sudo -n …` (sin pedirla
otra vez). Así la contraseña **nunca le llega al comando**: con el simple
`echo clave | sudo -S tee archivo`, si sudo ya la recordaba, ¡la escribiría en
el archivo! El script viaja por la entrada estándar (no en la línea de
comandos), así que la contraseña tampoco se ve en `ps` del servidor.

**Ctrl+C** = cerrar el canal SSH: el servidor manda la señal al proceso y lo
corta. **Tab** = `compgen -c` (comandos) o `compgen -f` (archivos) en el
servidor. La salida llega en pedazos desde un hilo y la pantalla se pinta cada
0.2 s (no por cada pedazo) para no saturar el celular.

**Dónde.** `modulos/kraken/ssh/consola.py` (`script`, `split_marker`,
`Consola.run/complete/cancel`), `views/consola.py`.


## 52. Postman: el formato Collection v2.1

**Qué es.** Postman guarda una colección como un JSON con un esquema público
("Collection v2.1"). Si Kraken lee y escribe ese mismo JSON, puedes pasar
colecciones entre Postman, la app y tus compañeros sin copiar a mano.

**La forma del archivo (lo importante):**

```json
{
  "info": {"name": "Mi API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
  "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}"}]},
  "variable": [{"key": "base", "value": "http://localhost:8069"}],
  "item": [
    {"name": "Usuarios", "item": [                       <- carpeta (tiene "item")
      {"name": "Listar", "request": {                    <- petición (tiene "request")
        "method": "GET",
        "url": {"raw": "{{base}}/api/users?page=2", "query": [{"key": "page", "value": "2"}]},
        "header": [{"key": "Accept", "value": "application/json", "disabled": true}]}}]}]
}
```

**Recorrerlo: recursión.** `walk(items, ruta, auth)` se llama a sí misma por
cada carpeta, cargando el camino (`["Usuarios", "Admin"]`) y la auth que se
hereda. Kraken no tiene carpetas dentro de colecciones, así que el camino va en
el nombre con `" / "`; al exportar, `split(" / ")` las vuelve a armar.

**La URL viene dos veces** (`raw` y `query`): se toma `raw` sin lo que va
después de `?` y los params de `query`, que trae los desactivados (`raw` no).
Así no se duplican. Al exportar se escriben las dos.

**Lo que no se puede** se cuenta y se avisa: los scripts (JavaScript que
Postman corre antes y después) y los archivos de form-data.

**Archivos raros:** Postman en Windows puede guardar en UTF-16 o con BOM
(`\ufeff` al inicio): se detecta por los primeros bytes antes de leer el JSON.

**Ida y vuelta.** La prueba exporta una colección, la vuelve a importar y
compara campo por campo. Si algo se perdiera al exportar, ahí truena.

**Dónde.** `modulos/kraken/http/postman.py` (`import_file`, `export_collection`,
`export_environment`), `views/inicio.py` y `views/entornos.py`.


## 53. Variables de colores y autocompletar: cursor y TextSpan

**Pintar por pedazos: `TextSpan`.** Un `ft.Text` puede llevar `spans`: cada
pedazo con su propio estilo. `split_variables()` parte el texto con la misma
expresión regular que reemplaza las variables (`VARIABLE`) y cada `{{nombre}}`
se pinta azul (existe) o rojo subrayado (no existe):

```python
ft.Text(spans=[ft.TextSpan("{{base}}", style=ft.TextStyle(color=ft.Colors.BLUE)),
               ft.TextSpan("/api/users", style=ft.TextStyle(color=ft.Colors.OUTLINE))])
```

Un `TextField` NO acepta spans (su texto es de un solo estilo), por eso la
línea de colores va debajo del campo.

**¿Dónde está el cursor? `selection`.** En Flet 1.0 el campo sabe su cursor:
`campo.selection.extent_offset` (y avisa con `on_selection_change`). Con eso,
`variable_at_cursor()` mira lo que hay ANTES del cursor: si lo último es `{{`
seguido de letras sin cerrar, estás escribiendo una variable.

**Completar** = reemplazar `{{to` por `{{token}}` (quitando `}}` si ya estaban
después del cursor) y mover el cursor al final con
`campo.selection = ft.TextSelection(base_offset=n, extent_offset=n)`; el campo
debe tener el foco antes (`await campo.focus()`).

**Avisar al editor.** Escribir en `campo.value` desde código NO dispara
`on_change`; por eso, tras completar, se llama a mano con un evento falso
(`SimpleNamespace(control=campo, data=texto)`): el editor marca "sin guardar"
y recalcula las variables faltantes como si lo hubieras tecleado.

**Dónde.** `modulos/kraken/http/services.py` (`split_variables`,
`variable_at_cursor`, `suggest_variables`, `insert_variable`),
`views/variables.py` (`VariableAssist`), `comun.py` (`KeyValueEditor(asistente=…)`).


## Registro de cambios de estas notas

| Fecha | Versión app | Notas agregadas |
|---|---|---|
| 2026-09-29 | 0.9.0 – 0.13.1 | 1–23 (Desarrollo, calendario, deslizar, marcar desde Día, adjuntos, captura/grabación, Excel, bug de servicios en el celular) |
| 2026-09-29 | 0.14.0 | 24–26 (área segura del celular, menú con velo, pincel) |
| 2026-09-30 | 0.14.1 | 27–28 (arranque frágil / preferencias, rclone) |
| 2026-10-01 | 1.0.0 | 29 (APK: datos, firma y versiones) |
| 2026-10-02 | 1.1.0 | 30–33 (candado de la BD, catálogos/etapas, Kanban, pruebas en navegador) |
| 2026-10-14 | 1.2.0 | 34–36 (adjuntos únicos, verificar respaldo, avisos con la app cerrada) |
| 2026-10-14 | 1.2.1 | 36 (resultado de la prueba) y 37 (avisos de la Agenda) |
| 2026-10-14 | 1.3.0 | 38 (Notas: guardado automático, búsqueda, tarjetas) |
| 2026-10-14 | 1.4.0 | 39 (Memorias: fotos, un día como hoy, voz; verificar_flet) |
| 2026-10-14 | 1.5.0 | 40–42 (cliente HTTP async, cURL con shlex, SQLite solo lectura y archivos fuera del respaldo) |
| 2026-10-14 | 1.6.0 | 43–45 (sockets, ping sin root, puertos en paralelo, dispositivos; DNS, certificados, Whois, WoL; servidores falsos) |
| 2026-10-15 | 1.7.0 | 46–47 (SSH con paramiko, huella del servidor, sudo -S; panel en vivo con /proc) |
| 2026-10-15 | 1.8.0 | 48–51 (DB-API para tres motores, solo lectura del lado del servidor, túnel SSH, consola SSH) |
| 2026-10-15 | 1.8.1 | 52 (Postman Collection v2.1: importar, exportar, ida y vuelta) |
| 2026-10-15 | 1.8.2 | 53 (variables de colores con TextSpan y autocompletar con el cursor) |

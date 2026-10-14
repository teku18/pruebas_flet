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

**Dónde.** `pruebas/notificaciones/` (app de prueba aparte).

---

## Registro de cambios de estas notas

| Fecha | Versión app | Notas agregadas |
|---|---|---|
| 2026-09-29 | 0.9.0 – 0.13.1 | 1–23 (Desarrollo, calendario, deslizar, marcar desde Día, adjuntos, captura/grabación, Excel, bug de servicios en el celular) |
| 2026-09-29 | 0.14.0 | 24–26 (área segura del celular, menú con velo, pincel) |
| 2026-09-30 | 0.14.1 | 27–28 (arranque frágil / preferencias, rclone) |
| 2026-10-01 | 1.0.0 | 29 (APK: datos, firma y versiones) |
| 2026-10-02 | 1.1.0 | 30–33 (candado de la BD, catálogos/etapas, Kanban, pruebas en navegador) |
| 2026-10-14 | 1.2.0 | 34–36 (adjuntos únicos, verificar respaldo, avisos con la app cerrada) |

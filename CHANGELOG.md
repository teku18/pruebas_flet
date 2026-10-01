# Cambios de ControlKraken

## 0.14.1 — 2026-09-30

### Arreglos
- Al abrir la app desde el celular, Configuración podía quedarse esperando sus
  preferencias ("Timeout waiting for invoke method listener for
  SharedPreferences") y el respaldo no terminaba de cargar (no se podía
  restaurar). Ahora:
  - La herramienta de captura activa `enable_screenshots` hasta la primera
    captura (antes lo hacía al arrancar y el celular reconstruía la pantalla
    justo cuando se pedían las preferencias).
  - Las preferencias se leen con `pref_get()`/`pref_set()` (`core/ui.py`):
    reintentan y, si no responden, la app abre con los valores de fábrica en
    vez de tronar.

## 0.14.0 — 2026-09-29

### Nuevo
- **Pincel para marcar** en las capturas y grabaciones (4 colores, deshacer y
  borrar trazos):
  - Menú 📷 → **Marcar y capturar**: dibujas con el dedo y tocas *Capturar*; la
    foto sale con tus trazos (sin la barra de herramientas).
  - Grabando: botón **✏️** junto al ■ para encender el pincel; mientras está
    encendido la app no responde (estás dibujando). Apágalo para seguir usando
    la app. Los trazos salen en la grabación.

### Cambios
- El menú de captura ya no es una hoja pegada al borde: es una tarjeta flotante
  que respeta la barra de botones del celular (`page.media.padding`), un poco
  más abajo que el "+" de los módulos. El botón 📷 quedó a la misma altura que el "+".

## 0.13.1 — 2026-09-29

### Arreglos
- **Adjuntar desde el celular** fallaba con "Control with ID … is not registered":
  Flet daba de baja el `FilePicker` mientras elegías el archivo. Ahora los
  servicios (`FilePicker`, `UrlLauncher`) se piden con `service()` de
  `core/ui.py`, que los deja sujetos a la página. Aplicado en adjuntos de
  Desarrollo y Proyectos, respaldo, importar y exportar Excel.
- Desde el celular la ruta del archivo es del teléfono: ahora se pide también su
  contenido (`with_data=True`) y se guarda desde ahí.

### Documentación
- `docs/notas_tecnicas.md`: conceptos para estudiar (qué es, para qué lo usamos
  y dónde está en el código). Se irá actualizando con cada cambio.

## 0.13.0 — 2026-09-29

### Nuevo
- **Desarrollo: adjuntos en los pendientes** (archivos, imágenes, capturas y
  grabaciones). Miniatura de las imágenes; tocar = verla en grande (los GIF se
  animan) u abrir el archivo con su app. En la lista sale "📎 N".
- **Botón flotante 📷 en todas las pantallas** (esquina inferior izquierda):
  - *Capturar pantalla*: foto de la app (el botón se esconde para no salir).
  - *Grabar pantalla*: el botón se pone rojo con el contador (● 0:12); tócalo
    para detener. Se guarda como **GIF animado** (~2.5 cuadros/s, máx. 90 s).
  - Al terminar: aviso con **[Reportar]** → pendiente nuevo con la captura
    adjunta y el **módulo donde la tomaste ya elegido**.
  - Lo que no reportes queda en **Mis capturas** (Desarrollo → 🖼) para
    adjuntarlo después ("De mis capturas" en el formulario) o borrarlo.
- **Exportar a Excel** (Desarrollo → ▦): hoja *Resumen* (prioridad, barra de
  avance y conteos por prioridad con fórmulas; cada módulo es un vínculo a su
  hoja) + **una hoja por módulo** con sus pendientes: prioridad con color,
  estado, tipo, descripción, adjuntos y fechas (los hechos en gris).

### Base de datos
- 0010: tabla `dev_adjuntos`. Archivos en `data/desarrollo/<pendiente>/`,
  bandeja en `data/capturas/` (ambos entran en el respaldo).

### Dependencias
- `Pillow` (arma el GIF de las grabaciones): `pip install -r requirements.txt`.

## 0.12.0 — 2026-09-29

### Nuevo
- **Calendario → vista Día: marcar y desmarcar tareas** con el círculo, igual
  que en el chismoso (○ marca hecha, ✓ deshace; si es de un proyecto, ofrece
  registrar el avance en su bitácora).
  - Solo se marca la fecha que **toca ahorita**: en una recurrente, la de
    mañana se habilita cuando marcas la de hoy (el círculo tenue avisa
    "Primero marca la del …").
  - Solo se deshace la **última vez** que la marcaste (deshacer una vieja
    descuadraría las fechas de la recurrente).

## 0.11.0 — 2026-09-29

### Nuevo
- **Calendario: deslizar ← →** para ir al siguiente / anterior día, semana, mes
  o año (con el dedo, o arrastrando con el mouse en la compu). Basta un
  arrastre de ~60 px o un "flick" rápido.
- Animación tipo carrusel: el periodo actual sale hacia el lado del dedo y el
  nuevo entra por el otro. Las flechas ◀ ▶ usan la misma animación.
- Ícono de "deslizar" junto al resumen, como pista.

## 0.10.0 — 2026-09-29

### Nuevo
- **Agenda → pestaña Calendario**: cuántas tareas hay en un rango.
  - Vistas **Día**, **Semana**, **Mes** y **Año** (los 12 meses completos en
    miniatura). ◀ ▶ para moverte y **Hoy** para regresar.
  - Las recurrentes aparecen en **cada** fecha que les toca (la renta mensual
    sale en todos los meses, la diaria todos los días); lo ya hecho sale del
    historial en verde.
  - Resumen del rango: "38 tareas · 5 hechas · 2 vencidas".
  - Filtros: **tipo de proyecto** (Personal, Familiar, Trabajo, Sin proyecto) y
    **proyecto** (la lista se ajusta al tipo elegido).
  - Mes y Año se colorean por cantidad de tareas (más tareas = color más fuerte);
    tocar un día abre la vista Día, tocar un mes en Año abre ese Mes.
- `services.occurrences(inicio, fin, tipo, proyecto)`: expande las tareas en un
  rango de fechas (lo podrán usar otros reportes).

## 0.9.0 — 2026-09-29

### Nuevo
- **Desarrollo**: el roadmap de la propia app.
  - Cada **módulo** con nombre, descripción, **prioridad** (alta/media/baja) y
    **% de avance** (barra). Arranca con Finanzas 95 %, Proyectos 50 %,
    Agenda 50 % y Memorias 0 %.
  - Cada módulo tiene sus **pendientes**: tarea, error o comentario, cada uno
    con su propia prioridad. Tocar ○ lo marca hecho (guarda cuándo); en la
    pestaña **Hechos** del módulo tocar ✓ lo regresa.
  - Pestaña **Pendientes**: todo lo abierto de la app agrupado
    🔴 Alta → 🟡 Media → ⚪ Baja, para ver qué sigue de un vistazo.
  - Engrane del módulo: editar sus datos o eliminarlo (con sus pendientes).

### Base de datos
- 0009: tablas `dev_modulos` y `dev_pendientes` (+ los 4 módulos iniciales).

## 0.8.0 — 2026-09-29

### Nuevo
- **Agenda** (ya no dice "Próximamente"): tareas **con o sin proyecto**.
  - Fecha, horario opcional (sin hora = todo el día) y frecuencia: una vez,
    diario, lunes a viernes, cada semana o cada mes.
  - **Chismoso** (pestaña Hoy): 🔴 vencidas, 🟡 hoy, ⚪ mañana, 🟢 hechas hoy y
    los proyectos que llevan 14+ días sin avance.
  - Tocar ○ la marca hecha; una recurrente salta a su siguiente fecha **desde la
    que tocaba** (si debes dos rentas, marcar una vez solo paga la primera).
    Tocar ✓ en "Hechas hoy" lo deshace.
  - Si la tarea es de un proyecto, ofrece registrar el avance en su bitácora.
  - Pestaña **Todas**: todas las pendientes, de la más próxima a la más lejana.
  - En la tarea: [Marcar hecha] e **historial** ("28 sept (tocaba 25 sept)").
- `TimeField` en `core/ui.py`: campo de hora opcional, como `DateField`.
- Proyectos: la ficha muestra sus tareas pendientes; al borrar un proyecto
  también se borran sus tareas.

### Base de datos
- 0008: tablas `tareas` y `tarea_cumplimientos`.

## 0.7.2 — 2026-09-28

### Cambios
- **La app sube a Drive sola** (vía rclone): después de cada respaldo, y al abrir baja
  los respaldos recientes de otros equipos. Ya no depende de cron.
- Botón **Sincronizar** (antes Verificar): sube lo que falte, baja lo reciente y
  muestra la cuenta y el estado; si algo falla, dice por qué.

## 0.7.1 — 2026-09-28

### Cambios
- **Periodicidad del respaldo automático** (Configuración → Respaldo):
  "Respaldar cada [N] [Horas | Días | Semanas | Meses]" y **Próximo respaldo**
  (último + N × periodo). Antes era 2 min después de cada cambio.
  Solo respalda si hubo cambios; si la app estaba cerrada cuando tocaba, lo hace
  al abrirla. Por defecto: cada 1 día.

## 0.7.0 — 2026-09-27

### Nuevo
- **Proyectos: seguimiento**
  - Estado **Cancelado**, además de Activo, En pausa y Terminado.
  - **Fecha de fin**: aparece al pasar a Terminado/Cancelado (propone hoy); al
    regresar a Activo/En pausa se limpia sola.
  - **Destacado** ⭐: los proyectos que quieres en el resumen del año.
  - La lista muestra la **duración** ("3 meses") y, si un proyecto activo lleva
    14 días o más sin avance, **⚠ N días sin avance** en naranja.
  - Ficha del proyecto: cuánto duró / lleva, entradas, hitos y último avance.
- **Bitácora: tipo de entrada** — Avance, **Hito** ⭐, Problema o Cierre.
  Los hitos se resaltan en ámbar y el chip **Solo hitos** muestra la línea de tiempo.
- `modulos/proyectos/services.py`: duración, última actividad y días sin avance
  (calculados, no se guardan), más `stalled_projects()` para el futuro chismoso
  de la Agenda y `year_highlights(año)` para el futuro resumen del año.

### Base de datos
- 0007: `proyectos.fecha_fin`, `proyectos.destacado`, `proyectos.creado_en` y
  `proyecto_entradas.tipo`. Los terminados que ya existen toman como fecha fin
  su última entrada; todas las entradas existentes quedan como "Avance".

## 0.6.2 — 2026-09-27

### Nuevo
- Configuración → Respaldo muestra **a qué cuenta de Google Drive** sube rclone
  (correo y nombre) y si tus respaldos ya están arriba ("al día" / "N por subir").
  Se revisa al abrir, al respaldar y con [Verificar]. Nuevo `core/drive.py`.

## 0.6.1 — 2026-09-27

### Nuevo
- **Aviso de respaldo de otro equipo**: al abrir, si en la carpeta hay un respaldo
  de otro equipo más nuevo que lo último de aquí → [Restaurar] o [Este equipo es mi base].
  Marca ⚠ si este equipo también tiene cambios posteriores.
- Equipo nuevo: botón **Restaurar el más reciente** (muestra fecha y equipo).
- Nunca se borran los respaldos de las últimas 24 h (los que baja rclone).
- `docs/respaldo.md`: cron que también baja los respaldos de otros equipos y
  cómo cambiar de "base de operaciones".

## 0.6.0 — 2026-09-27

### Nuevo
- **Respaldo** (Configuración → Respaldo): zip con la BD, los adjuntos y un
  manifest (versión, migración, fecha, equipo).
  - Automático 2 min después de tu último cambio (y al abrir, si quedó algo sin respaldar).
  - Respaldar ahora / Restaurar… (valida el zip; guarda antes tu BD actual).
  - Se conservan los últimos 10 + uno por mes.
- **Equipo nuevo**: si no hay BD, la app ofrece restaurar un respaldo.
- **Copia automática antes de migrar** (al actualizar la app) en `respaldos/`.
- Guía `docs/respaldo.md`: subir a Google Drive con rclone y montar un equipo nuevo.

## 0.5.0 — 2026-09-26

### Nuevo
- **Cerrar periodo** (⚙ dentro del periodo): propone el siguiente ("Inversiones 2027"),
  muestra con qué saldos abrirá y crea el nuevo con un saldo inicial por
  concepto/plataforma. El cerrado queda 🔒 en solo lectura.
- **Solo cerrar** (sin abrir otro): queda 🔒 y sale del acumulado global; muestra sus
  "Saldos al cierre" para capturarlos a mano en el periodo que abras con +.
- **Reabrir periodo**, solo si no se abrió otro con su cierre.
- Varios periodos abiertos a la vez (p. ej. Inversiones y Gastos como libros separados).
- **Traspasos entre conceptos** (Vacaciones → Mio), además de entre plataformas.
  Con filtro de concepto, un traspaso que llega de otro concepto sí cuenta como entrada.

### Cambios
- Un periodo creado en la app abre en $0; "Abre con" = sus propios saldos iniciales.
- Acumulado global = suma de los periodos **abiertos** (los cerrados ya pasaron su saldo).
- Importador: saldo inicial = bloque de entradas con que empieza la hoja (una por
  concepto/plataforma); columna "Gasto" aceptada como concepto; detecta traspasos
  entre conceptos; ya no descarta saldos iniciales por historia previa.
- Reportes: los chips muestran solo los conceptos del periodo.

### Base de datos
- 0006: `periodos.cerrado` y `periodos.origen_id`.

## 0.4.0 — 2026-09-26

### Nuevo
- **Reportes** (ícono 📊 en Finanzas): por periodo y concepto.
  - Total al cierre con **meta** y cuánto falta.
  - Reparto por plataforma: pastel con todas las plataformas + tabla con monto y %.
  - Ahorro mensual: línea del acumulado (eje en pasos redondos: 25k, 50k…) + tabla.
- Meta opcional por concepto (Ajustes → Conceptos).
- Reportes también desde dentro de un periodo (📊 junto a ⇄): solo ese periodo y con
  el concepto que tengas filtrado.

### Base de datos
- 0005: `inversiones.meta`.

## 0.3.0 — 2026-09-26

### Nuevo
- **Plataforma e Inversión** son catálogos (modelos) en lugar de listas fijas.
  Se administran en Finanzas > engrane > Ajustes, y se pueden crear al vuelo
  con "+ Nueva…" desde el formulario de movimientos. Se archivan en lugar de borrarse.
- **Traspasos**: herramienta ⇄ que crea la salida y la entrada ligadas.
  No cuentan como ingreso ni gasto.
- Tipos de movimiento con signo: saldo inicial, depósito, rendimiento, retiro, traspaso.
- **Resumen por periodo** (abre con, ingresos, gastos, neto, cierra con) y
  **acumulado global** con desglose por plataforma.
- **Importador de Excel**: cada pestaña se vuelve un periodo; detecta saldo inicial,
  traspasos y rendimientos.
- **Filtro por concepto** en los movimientos: chips arriba de la lista; el resumen
  también se filtra (p. ej. cuánto llevas en "Casa").
- "Inversión" se muestra como **Concepto** (solo el texto; la tabla sigue igual).

### Base de datos
- 0004: tablas `plataformas` e `inversiones`; los movimientos pasan de texto a
  `plataforma_id` / `inversion_id`; nuevo `traspaso_grupo`.

## 0.2.0 — 2026-09-25

### Nuevo
- Ícono y logo de ControlKraken (`assets/icon.png`, `assets/logo.png`).
- Pantalla de inicio "ControlKraken" con una tarjeta por módulo.
- Módulo **Proyectos**: tipo (personal, familiar, trabajo), estado y bitácora
  de avances con fecha, notas y adjuntos como evidencia.
- Configuración con 12 colores para toda la app, además de claro/oscuro/sistema.
- Migraciones de base de datos con **Alembic**; se aplican solas al abrir la app.

### Cambios
- Estructura modular: `core/` (lo compartido) y `modulos/` (un folder por módulo).
- Métodos y funciones en inglés, marcados con `# propio`.
- Rutas de Finanzas bajo `/finanzas/...`.

### Base de datos
- 0002: tablas `proyectos`, `proyecto_entradas`, `proyecto_adjuntos`.
- 0003: `movimientos.periodo_id` obligatorio (NOT NULL).

## 0.1.0
- Finanzas: periodos y movimientos.

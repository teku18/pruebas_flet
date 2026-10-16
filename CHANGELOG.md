# Cambios de ControlKraken

## 1.8.0 — 2026-10-15

### Nuevo
- **Explorador de bases** (antes "Explorador SQLite"): además de archivos
  SQLite, ahora **servidores PostgreSQL y MySQL/MariaDB**.
  - "Agregar base" pregunta: Archivo SQLite, Servidor PostgreSQL o Servidor MySQL.
  - Conexión **directa** o **por túnel SSH** a través de uno de tus servidores
    de Kraken > SSH (no se abre ningún puerto: la base sigue escuchando solo
    en el servidor).
  - "Probar conexión" dice la versión y lista las bases para elegir una.
  - Tablas (con esquemas de PostgreSQL: `ventas.pedidos`), columnas, llaves,
    índices, datos por páginas con búsqueda y SQL libre con CSV.
  - **Solo lectura de verdad**: lo impone el propio servidor (no solo la app).
    "Permitir cambios" lo quita, con confirmación antes de cada cambio.
  - Cada consulta tiene **30 s** como máximo; el servidor la corta si tarda más.
  - Todo carga en segundo plano: un servidor lento ya no congela la pantalla.
  - Tablas enormes: conteo aproximado (~) para no tardar minutos.
  - Usuario y contraseña en texto normal y en el respaldo, como todo Kraken.
- **Consola SSH** (botón "Consola" en el panel del servidor): escribe
  **cualquier comando**, como desde una terminal de otra PC.
  - Recuerda la carpeta (`cd` funciona entre comandos).
  - `sudo` en cualquier parte del comando usa la contraseña guardada (y nunca
    se le pasa al comando: `sudo tee` no la escribe en el archivo).
  - Salida en vivo, **Ctrl+C** para cortar, **Tab** para completar archivos y
    comandos, flechas para repetir comandos anteriores (también con el teclado
    de la PC) y botones con comandos frecuentes.
  - vim, nano, htop, top, less… no se pueden (no hay pantalla de terminal):
    avisa qué usar en su lugar.
  - Cada comando queda en el historial de Red.

### Cambios
- El panel del servidor se **pausa** mientras tienes Logs o Consola encima
  (no se ve, no se lee) y lee al instante al volver.
- Migración 0019: `kt_sqlite_conexiones` suma tipo, host, puerto, base de
  datos, usuario, contraseña y servidor SSH. Respaldo: 31 tablas.
- Dependencias nuevas (puro Python): `pg8000==1.31.5` (con `scramp`,
  `asn1crypto`, `python-dateutil`, `six`) y `pymysql==1.2.3`.
- `verificar_kraken.py` prueba PostgreSQL y MySQL reales si defines
  `CK_TEST_PG` / `CK_TEST_MYSQL` (`host:puerto:usuario:clave`), el túnel SSH y
  la consola (cd, sudo, salida en vivo, Ctrl+C, Tab).

## 1.7.0 — 2026-10-15

### Nuevo
- **Kraken Tools · SSH** (la tarjeta "SSH" ya funciona): cuida tus servidores
  desde el celular.
  - **Servidores**: los mismos "Mis equipos" de Red con usuario, puerto y
    contraseña SSH (guardada en texto normal y respaldada, como todo Kraken).
  - **Panel en vivo, cada 5 s solo mientras lo ves** (se pausa si la app pasa a
    segundo plano y se detiene al salir):
    - sistema, tiempo encendido y carga
    - **CPU y RAM** en porcentaje, con color (verde/naranja/rojo) y gráfica de
      los últimos 5 minutos
    - **discos** por partición (rojo al pasar del 90 %)
    - red (bajada/subida), **servicios** (odoo, postgresql, nginx o los que
      elijas) y los procesos que más consumen
  - **Comandos guardados** con confirmación: vienen Reiniciar Odoo,
    Reiniciar PostgreSQL, Reiniciar Nginx y "¿Qué ocupa el disco?". Se pueden
    crear para todos los servidores o solo para uno. Los que empiezan con
    `sudo` usan la contraseña guardada.
  - **Logs**: últimas 100–1,000 líneas de cualquier archivo, con búsqueda,
    ERROR en rojo y WARNING en naranja, y opción "con sudo".
  - **Huella del servidor**: si un servidor cambia de llave, no se conecta y te
    pregunta (protege contra alguien que se haga pasar por él).
  - Cada comando y un "vistazo" por visita quedan en el historial de Red.
- `pruebas/ssh/`: app aparte que confirmó que SSH funciona dentro del APK.

### Cambios
- Migración 0018: `kt_equipos` suma los datos SSH; tabla nueva
  `kt_ssh_comandos`. Respaldo: 31 tablas.
- Red: el texto de ayuda del servidor DNS ya no sale cortado.
- Dependencias nuevas: `paramiko==5.0.0` con `cryptography==48.0.0`,
  `bcrypt==5.0.0`, `pynacl==1.6.2` y `cffi==2.0.0` (versiones que Flet tiene
  compiladas para Android).
- `verificar_kraken.py` prueba SSH contra un servidor SSH falso (con un `sudo`
  falso): más de 110 pruebas.

## 1.6.0 — 2026-10-14

### Nuevo
- **Kraken Tools · Red** (la tarjeta "Red" ya funciona):
  - **Mis equipos**: tus servidores, router o PC (IP o dominio, puertos que te
    importan, MAC). Tocar uno: ping, revisar sus puertos, certificado, DNS o
    encenderlo.
  - **Ping**: responde o no, tiempos y mín/prom/máx. Usa ICMP si el sistema lo
    deja; si no, "ping TCP" (lo dice en pantalla).
  - **Puertos**: abiertos, cerrados o filtrados, con el nombre del servicio
    (22 SSH, 5432 PostgreSQL, 8069 Odoo…). Botones Comunes, Web, Bases de
    datos, Remoto y 1-1024. Se va pintando mientras corre y se puede cancelar.
  - **DNS**: A, AAAA, CNAME, MX, TXT, NS (y PTR de una IP), preguntando al
    servidor que elijas (**1.1.1.1 por defecto, configurable**).
  - **Mi IP**: pública (con proveedor y ciudad), local y tu red.
  - **Certificado HTTPS**: válido o por qué no, para qué dominios, quién lo
    firmó y cuántos días le quedan.
  - **Whois**: registrador, fechas y **cuándo vence** el dominio (RDAP o WHOIS).
  - **Wake-on-LAN**: encender un equipo de tu red con su MAC.
  - **Dispositivos en mi red**: qué hay conectado a tu Wi-Fi (IP, nombre,
    puertos abiertos y qué parece ser); guardarlos en Mis equipos con un toque.
    Solo redes privadas.
  - **Historial de Red** con filtros por prueba; **cuántas se guardan es
    configurable** en Ajustes de Red.
- `scripts/verificar_kraken.py` prueba todo lo de Red contra servidores falsos
  (DNS, WHOIS, RDAP, HTTPS vencido/autofirmado, UDP) sin internet: más de 90 pruebas.

### Cambios
- Migración 0017: tablas `kt_equipos` y `kt_historial_red`; `kt_ajustes`
  suma `dns_servidor` (1.1.1.1) y `red_historial_max` (200). Respaldo: 30 tablas.
- Cliente HTTP: al salir del editor, un envío en curso se cancela desde el
  hilo correcto de asyncio.
- Dependencia nueva: `dnspython==2.8.0` (pyproject y requirements).

## 1.5.0 — 2026-10-14

### Nuevo
- **Kraken Tools** (módulo nuevo): herramientas de desarrollador en el celular.
  Pantalla de inicio con tarjetas; Red, SSH y Webhooks aparecen como "Próximamente".
- **Cliente HTTP (tipo Postman)**:
  - Método, URL y pestañas **Params**, **Headers**, **Body** (JSON, texto o
    formulario) y **Auth** (Bearer token o usuario y contraseña).
  - **Respuesta**: código con color, tiempo, tamaño; JSON bonito o tal cual;
    headers recibidos y lo que se envió de verdad. Copiar o guardar como archivo
    (sirve para imágenes y PDF).
  - **Colecciones** para guardar peticiones (duplicar, mover, renombrar).
    Una petición guardada se guarda sola al enviar y al salir.
  - **Entornos y variables** `{{base_url}}`, `{{token}}`: Globales + el entorno
    elegido (Local, Producción…). Avisa las variables sin definir.
  - **Historial** de envíos (tocar uno lo abre con su respuesta).
    **Configurable** en Ajustes: cuántos envíos guardar (50 a 1,000 o sin
    límite), cuánto de cada respuesta (64 KB a 20 MB o completa) y el tiempo de
    espera. En pantalla siempre se ve la respuesta completa.
  - **cURL**: copiar como cURL e **importar cURL** (también pegándolo en la URL).
  - El envío no congela la pantalla y se puede **cancelar**.
- **Explorador SQLite**:
  - La BD de ControlKraken, **siempre en solo lectura**.
  - Agregar cualquier `.db`: se **copia** a la app (el original no se toca).
    Por base: solo lectura (por defecto) o editable, y **respaldar sí/no**.
  - Pestañas **Tablas** (filas, columnas, PK/FK, índices, copiar CREATE),
    **Datos** (de 50 en 50, búsqueda en todas las columnas, tocar una celda la
    muestra completa) y **SQL** (varias sentencias, todo o nada; confirmar antes
    de cambiar datos; favoritas e historial; exportar a CSV).
  - Descargar una copia de la base.
- Todo (colecciones, entornos, historial, ajustes, conexiones y consultas) vive
  en la BD y entra en el respaldo.
- `scripts/verificar_kraken.py`: prueba el cliente HTTP contra un servidor
  local, el explorador y el respaldo opcional de bases, sin celular ni internet.

### Cambios
- Migración 0016: tablas `kt_ajustes`, `kt_colecciones`, `kt_peticiones`,
  `kt_entornos`, `kt_historial_http`, `kt_sqlite_conexiones`,
  `kt_sqlite_consultas`. "Kraken Tools" aparece en tu roadmap de Desarrollo.
- Respaldo: un módulo puede dejar archivos fuera del zip
  (`backup.register_exclusion`); al restaurar, esos archivos no se borran.
  `verificar_respaldo.py` pasa con 28 tablas.
- `confirm()` acepta otro texto para el botón (p. ej. "Ejecutar").
- Dependencia nueva: `httpx==0.28.1` (pyproject y requirements).

## 1.4.0 — 2026-10-14

### Nuevo
- **Memorias (rediseño)**: una bitácora de momentos importantes, no de pendientes.
  - Cada memoria: **fecha del suceso** (puede ser de hace años), título,
    relato, **varias fotos**, lugar, **etiquetas** (Viaje, Familia, Pareja,
    Logro, Amigos, Trabajo; se crean más) y un **ánimo** con emoji.
  - **Línea de tiempo** agrupada por año y mes, y **Galería** con todas las
    fotos (tocar una abre su memoria).
  - **"Un día como hoy"**: arriba de la línea de tiempo, lo que pasó en esta
    misma fecha en años anteriores ("Hace 3 años").
  - **Búsqueda** por texto (título, relato, lugar) y **filtros** por etiquetas
    y rango de fechas.
  - **Fotos copiadas a la app** (si la borras de la galería del celular, aquí
    sigue): giradas según el EXIF, reducidas a 3072 px de lado mayor en JPEG
    92 (no se nota la diferencia y pesan varias veces menos) y con miniatura
    para que la galería cargue rápido. Toca una foto para verla completa y
    pellizca para hacer zoom.
  - Si la primera foto trae fecha, se propone como fecha de la memoria.
  - Listo para el dictado por voz más adelante (campo `origen`; sin cambiar tablas).
- `scripts/verificar_flet.py`: revisa que todo lo que el código usa de Flet
  exista en la versión instalada (y avisa lo obsoleto).

### Cambios
- Migración 0015: `memorias`, `memoria_etiquetas`, `memoria_etiqueta_rel`; las
  fotos van en la tabla única `adjuntos`. La descripción de Memorias en
  Desarrollo ya no dice "Pensamientos por voz (próximamente)".
- `verificar_respaldo.py` también revisa la carpeta `data/memorias/` (21 tablas ✓).
- Notas: el editor usa `NoInputBorder()` (`InputBorder.NONE` se quita en Flet 1.3).

## 1.3.0 — 2026-10-14

### Nuevo
- **Módulo Notas**: notas de texto libre y listas con casillas (súper, ideas,
  pendientes sueltos).
  - **Captura rápida**: escribe en "Nota rápida" y Enter: queda guardada sin
    abrir nada. ☑ abre una lista nueva con el cursor en la primera casilla;
    Enter crea la siguiente.
  - **Se guarda solo** (sin botón Guardar); una nota vacía se descarta al salir.
  - **Fijar, archivar, color y etiqueta** (dejar presionada una tarjeta o el
    menú ⋮ del editor). Vienen las etiquetas Súper, Ideas y Pendientes; se crean
    más desde el mismo selector.
  - **Buscar** en títulos, textos y casillas; chips por etiqueta y Archivadas.
  - En el tablero las casillas se palomean sin abrir la lista; las hechas bajan
    a "Hechos".
  - Convertir una nota de texto en lista y al revés.
  - **Exportar a Excel**: hoja con todas las notas + una hoja por lista.
- Desarrollo: el módulo "Notas" aparece en tu roadmap para reportarle pendientes.

### Cambios
- Migración 0014: tablas `notas`, `nota_items`, `nota_etiquetas` (entran solas
  al respaldo: `verificar_respaldo.py` pasa con las 18 tablas).

## 1.2.1 — 2026-10-14

### Nuevo
- **Avisos de la Agenda con la app cerrada** (celular). Cada tarea elige en su
  formulario "Avisarme": a la hora, 5/15/30 min, 1 hora o 1 día antes, o sin
  aviso. Sin hora: a las 8:00 am de ese día (o un día antes). Las recurrentes
  avisan cada vez que tocan; lo ya hecho no avisa.
- Se programan los próximos 14 días al abrir la app y cada vez que creas,
  editas, marcas o borras una tarea (también desde Proyectos).
- **Configuración → Avisos**: estado del permiso, próximo aviso, "Probar
  aviso", "Permitir hora exacta" y consejo para Xiaomi/Redmi.

### Cambios
- Migración 0013: `tareas.aviso_min` (las tareas que ya tenías avisan a la hora).
- `core/avisos.py`: motor de avisos con "proveedores" (otros módulos podrán
  agregar recordatorios sin tocarlo).
- `scripts/build_apk.sh` aplica el parche de `flet-android-notifications` y
  revisa que el APK traiga los receptores de alarmas.
- Probado en Redmi Note 14 Pro+ 5G (HyperOS 3.0 / Android 16): llegan con la
  app cerrada y después de reiniciar.

## 1.2.0 — 2026-10-14

### Nuevo
- **Adjuntos en las tareas de proyecto**: el formulario de la tarea trae
  "Adjuntar archivo" y "De mis capturas" (igual que Desarrollo). La lista y el
  Kanban muestran 📎 n. Los archivos van a `data/tareas/<id>/`.
- **La bitácora gana "De mis capturas"**: usa la misma caja de adjuntos que
  Desarrollo (antes tenía su propia copia del código).
- **Excel de Finanzas · ¿Aportado o rendimiento?**: tabla con montos y % y una
  gráfica de dona, con los mismos colores de la app. Solo si el periodo tiene
  rendimientos.
- Excel de Finanzas: los % de las gráficas de pastel y dona salen con **2
  decimales** en cualquier programa (antes LibreOffice los redondeaba a "4%").
- `scripts/verificar_respaldo.py`: mete un registro en CADA tabla, respalda,
  restaura como en un equipo nuevo y compara tablas y archivos.
- `pruebas/notificaciones/`: app de prueba aparte para saber si los avisos
  con la app cerrada funcionan con Flet 1.0 (todavía no va en la Agenda).

### Cambios
- **Una sola tabla de adjuntos** para toda la app (`adjuntos`, como
  `ir.attachment` de Odoo): migración 0012. Lo que había en `dev_adjuntos` y
  `proyecto_adjuntos` se copia ahí; los archivos NO se mueven.
- La bandeja de capturas y la caja de adjuntos pasan a `core/` (las usan
  varios módulos).
- `CK_DATA_ROOT` (solo para pruebas): trabaja en otra carpeta sin tocar tu BD.

## 1.1.0 — 2026-10-02

### Nuevo
- **Proyectos en Kanban**: botón ☰/▥ para ver los proyectos en lista o en
  columnas por etapa. Las tarjetas se arrastran por la manija ⋮⋮ o con el menú
  ⋮ "Mover a…". Pasar a una etapa cerrada pone la fecha fin sola.
- **Etapas configurables** (Proyectos → engrane → Ajustes): etapas de proyecto
  (con su significado: en curso, en pausa, terminada, cancelada), etapas de
  tarea (con "cuenta como hecha") y tipos de entrada; con color, orden ▲▼ y
  borrado solo si nadie las usa. Cada proyecto elige qué etapas de tarea usa.
- **Tareas dentro del proyecto**: pestaña "Tareas" en lista agrupada o Kanban.
  Pueden ir sin fecha (solo viven en el proyecto) o con fecha (también salen en
  la Agenda). Llevarla a "Hecho" la marca hecha y ofrece registrar el avance.
- **Tipos de entrada como catálogo**: filtro por tipo en la bitácora (reemplaza
  "Solo hitos") y "+" en el formulario para crear un tipo sin salir.
- **Finanzas · ¿Aportado o rendimiento?**: dona en Reportes con cuánto del total
  pusiste tú (saldo inicial + depósitos − retiros ± traspasos) y cuánto generó
  el dinero, con montos y %. Solo aparece si el periodo tiene rendimientos.
- **Respaldo en el celular en un solo botón**: «Respaldar y mandar a Drive»
  crea el zip y abre el selector de Android. Muestra "Última copia en Drive" y
  avisa si llevas 7 días o más sin mandarlo.

### Cambios
- Lista de proyectos más clara: etapa con color, avance de tareas (✓ 3/5) y los
  cerrados ocultos (chip "Cerrados").
- Migración 0011: `proyectos.estado` → `etapa_id`, `proyecto_entradas.tipo` →
  `tipo_id`, `tareas.etapa_id`, fecha de tarea opcional.

### Arreglos
- **Candado de la BD**: si falta `ControlKraken.db` pero existe `movimientos.db`,
  se renombra en vez de crear una BD vacía (así se perdieron Desarrollo,
  Proyectos y Agenda en la compu el 1/oct al renombrar la BD).

## 1.0.1 — 2026-10-01

### Arreglos (celular)
- "Sincronizar" daba error (rclone no existe en Android). En el celular ahora
  es **«Guardar copia en…»**: manda el respaldo más reciente a donde elijas con
  el selector de Android (Google Drive, Descargas…), sin login.
- **Restaurar** acepta un zip elegido desde Drive u otra app (llega su
  contenido, no una ruta); se guarda una copia temporal y se borra al terminar.
- La carpeta se mostraba como `~/user/0/…/files~/Respaldos`: en el celular dice
  "Carpeta interna de la app" y "Cambiar" se oculta. En la compu, `~` solo
  reemplaza el inicio de la ruta.
- En el celular ya no se llama a rclone al abrir ni después de respaldar.
- "No se pudo respaldar: Permission denied '/storage/emulated/0/acc=2;doc=…'":
  en la 1.0.0 "Cambiar" guardaba el identificador que da Android (no es una
  carpeta). Ahora en el celular siempre se usa la carpeta interna y, si había
  otra guardada, se corrige sola al abrir.

## 1.0.0 — 2026-10-01 · Primera versión para el celular (APK)

### Nuevo
- **APK de Android**: `pyproject.toml` (configuración de `flet build`) y
  `scripts/build_apk.sh` (APK firmado con tu llave; versión desde
  `APP_VERSION`, número de build = número de commits). Guía: `docs/apk.md`.

### Cambios
- **Datos en el celular**: instalada en Android, la BD, `data/` y `respaldos/`
  viven en la carpeta privada de la app (no se borran al actualizar el APK).
  En la compu todo sigue junto a `main.py` (aunque `flet run` defina
  `FLET_APP_STORAGE_DATA`).
- Alembic encuentra las migraciones aunque el paquete traiga solo `.pyc`
  (`sourceless`).
- El APK NO incluye tus datos (`ControlKraken.db`, `data/`, `respaldos/`) ni
  `docs/` ni `scripts/`.
- `.gitignore`: llaves de firma (`*.jks`, `*.keystore`).
- La BD ahora se llama `ControlKraken.db` (antes `movimientos.db`). Restaurar
  acepta los respaldos viejos que la traen con el nombre anterior.

### Pendiente conocido
- En el celular no hay subida a Drive (rclone no existe en Android): los
  respaldos quedan dentro de la app. Siguiente paso: login con Google.

## 0.14.2 — 2026-10-01

### Cambios
- **Nuevo logo e ícono**: el pulpo con lentes en su tazón de ramen.
  - `assets/icon.png` (1024×1024, sin texto, esquinas transparentes): ícono de
    la app y del encabezado del inicio.
  - `assets/logo.png` (con el nombre ControlKraken): README.

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

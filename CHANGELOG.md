# Cambios de ControlKraken

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

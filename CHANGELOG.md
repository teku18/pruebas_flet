# Cambios de ControlKraken

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

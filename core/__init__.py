"""
Núcleo compartido por todos los módulos (como la base de Odoo sobre la que
se instalan los addons):
  database.py -> conexión SQLite + Base de los modelos
  mixins.py   -> CrudMixin (create, get, search, update, delete)
  ui.py       -> piezas de interfaz reutilizables
  themes.py   -> colores de la app
  home.py     -> pantalla de inicio (lanzador de módulos)
  storage.py  -> archivos fuera de la BD (adjuntos) en data/
  adjuntos.py    -> tabla ÚNICA de adjuntos de todos los módulos (como ir.attachment)
  adjuntos_ui.py -> caja de adjuntos para formularios (archivo + "De mis capturas")
  capturas.py    -> bandeja de capturas y grabaciones (botón flotante 📷)
  backup.py      -> respaldar / restaurar (BD completa + data/)
"""

# Versión de la app (ver CHANGELOG.md). Súbela en cada entrega:
#   0.2.0 -> 0.2.1 arreglos · 0.3.0 algo nuevo · 1.0.0 lista para usarse en serio
APP_VERSION = "1.4.0"

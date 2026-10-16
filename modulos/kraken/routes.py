"""Rutas de Kraken Tools."""
BASE = "/kraken"                        # tarjetas de las herramientas
HTTP = "/kraken/http"                   # colecciones e historial
PETICION = "/kraken/http/peticion"      # editor de una petición + respuesta
ENTORNOS = "/kraken/http/entornos"      # variables {{así}}
SQLITE = "/kraken/sqlite"               # bases: SQLite, PostgreSQL, MySQL
SQLITE_BASE = "/kraken/sqlite/base"     # una base: tablas, datos, SQL
RED = "/kraken/red"                      # Mis equipos + las pruebas
RED_PRUEBA = "/kraken/red/prueba"       # una prueba (ping, puertos, DNS…) y su resultado
RED_HISTORIAL = "/kraken/red/historial" # todas las pruebas que corriste
SSH = "/kraken/ssh"                      # tus servidores SSH
SSH_PANEL = "/kraken/ssh/panel"         # recursos en vivo (cada 5 s) + comandos
SSH_LOGS = "/kraken/ssh/logs"           # leer un log del servidor
SSH_CONSOLA = "/kraken/ssh/consola"     # escribir cualquier comando (como una terminal)

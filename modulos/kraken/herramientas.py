"""
Las herramientas de Kraken Tools (las tarjetas de su pantalla de inicio).

Para agregar una (Red en la 1.6, SSH en la 1.7…): súmala aquí con su ruta y
en KrakenModule.build_views su pantalla. `listo=False` = "Próximamente".
"""
from dataclasses import dataclass

import flet as ft

from modulos.kraken import routes


@dataclass(frozen=True)
class Herramienta:
    nombre: str
    descripcion: str
    icono: str
    color: str
    route: str | None = None
    listo: bool = True


HERRAMIENTAS = [
    Herramienta("Cliente HTTP", "Peticiones a APIs, como Postman", ft.Icons.HTTP,
                ft.Colors.ORANGE, routes.HTTP),
    Herramienta("Explorador SQLite", "Tablas, datos y SQL de bases .db", ft.Icons.STORAGE,
                ft.Colors.BLUE, routes.SQLITE),
    Herramienta("Red", "Ping, puertos, DNS, IP, certificados, whois", ft.Icons.LAN,
                ft.Colors.TEAL, routes.RED),
    Herramienta("SSH", "Recursos de tus servidores y comandos", ft.Icons.TERMINAL,
                ft.Colors.PURPLE, routes.SSH),
    Herramienta("Webhooks", "Recibir y ver peticiones", ft.Icons.WEBHOOK, ft.Colors.PINK,
                listo=False),
]

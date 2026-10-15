"""
Las pruebas de Red (tarjetas de /kraken/red y su formulario).

  entrada: qué se escribe arriba
    "host"     IP o dominio (y se puede elegir de Mis equipos)
    "dominio"  solo dominio (Whois)
    "mac"      MAC de un equipo (Wake-on-LAN)
    "red"      una red, p. ej. 192.168.1.0/24 (se llena sola con la tuya)
    None       nada (Mi IP)
"""
from dataclasses import dataclass

import flet as ft


@dataclass(frozen=True)
class Prueba:
    clave: str
    nombre: str
    descripcion: str
    icono: str
    color: str
    entrada: str | None
    ejemplo: str = ""


PRUEBAS = [
    Prueba("ping", "Ping", "¿Responde? ¿Cuánto tarda?", ft.Icons.NETWORK_PING, ft.Colors.GREEN,
           "host", "192.168.1.1 o google.com"),
    Prueba("puertos", "Puertos", "Qué puertos están abiertos", ft.Icons.SETTINGS_ETHERNET,
           ft.Colors.ORANGE, "host", "192.168.1.10"),
    Prueba("dns", "DNS", "A dónde apunta un dominio", ft.Icons.TRAVEL_EXPLORE, ft.Colors.BLUE,
           "host", "ejemplo.com (o una IP)"),
    Prueba("mi_ip", "Mi IP", "Pública, local y proveedor", ft.Icons.MY_LOCATION,
           ft.Colors.PURPLE, None),
    Prueba("cert", "Certificado", "HTTPS: de quién es y cuándo vence", ft.Icons.VERIFIED_USER,
           ft.Colors.TEAL, "host", "ejemplo.com o ejemplo.com:8443"),
    Prueba("whois", "Whois", "De quién es un dominio y cuándo vence", ft.Icons.PERSON_SEARCH,
           ft.Colors.INDIGO, "dominio", "ejemplo.com.mx"),
    Prueba("dispositivos", "Dispositivos", "Qué hay conectado a tu red", ft.Icons.DEVICES_OTHER,
           ft.Colors.BROWN, "red", "192.168.1.0/24"),
    Prueba("wol", "Wake-on-LAN", "Encender un equipo de tu red", ft.Icons.POWER_SETTINGS_NEW,
           ft.Colors.RED, "mac", "AA:BB:CC:DD:EE:FF"),
]
POR_CLAVE = {p.clave: p for p in PRUEBAS}

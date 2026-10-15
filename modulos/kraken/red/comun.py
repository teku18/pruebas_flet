"""Cosas que usan varias pruebas de red."""
import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlsplit


def clean_host(texto: str) -> str:  # propio
    """
    Lo que escribiste -> solo el host:
      'https://www.ejemplo.com/ruta' -> 'www.ejemplo.com'
      'ejemplo.com:8069'             -> 'ejemplo.com'
      '192.168.1.10'                 -> '192.168.1.10'
    """
    t = (texto or "").strip()
    if not t:
        raise ValueError("Escribe una IP o un dominio")
    if "://" in t:
        t = urlsplit(t).hostname or ""
    else:
        t = t.split("/")[0]
        if t.count(":") == 1:  # host:puerto (una IPv6 tiene varios ':')
            t = t.split(":")[0]
    t = t.strip("[]").strip().lower()
    if not t or " " in t or not re.match(r"^[\w.\-:]+$", t):
        raise ValueError(f"No parece una IP o un dominio: {texto}")
    return t


def is_ip(texto: str) -> bool:  # propio
    try:
        ipaddress.ip_address(texto)
        return True
    except ValueError:
        return False


async def resolve(host: str) -> str:  # propio
    """Dominio -> IP (prefiere IPv4). Lanza ValueError si no existe."""
    if is_ip(host):
        return host
    loop = asyncio.get_running_loop()
    try:
        datos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as ex:
        raise ValueError(f"No se encontró «{host}» (¿bien escrito? ¿hay internet?)") from ex
    ipv4 = [d[4][0] for d in datos if d[0] == socket.AF_INET]
    return ipv4[0] if ipv4 else datos[0][4][0]


def ms(segundos: float) -> float:  # propio
    return round(segundos * 1000, 1)

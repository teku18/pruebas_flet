"""
Wake-on-LAN: encender un equipo de tu red desde el celular.

Se manda un "paquete mágico" por UDP a toda la red (broadcast): 6 bytes 0xFF y
luego la MAC del equipo repetida 16 veces (102 bytes). La tarjeta de red del
equipo apagado lo escucha y lo prende.

Para que funcione, en el equipo:
  - BIOS/UEFI: activar "Wake on LAN" / "Power on by PCI-E"
  - Linux:  sudo ethtool -s <interfaz> wol g   (ver con: ethtool <interfaz>)
  - Windows: Administrador de dispositivos → tarjeta → Administración de
    energía → "Permitir que este dispositivo reactive el equipo"
  - Casi siempre solo por CABLE, y el celular en la MISMA red (Wi-Fi de casa).
"""
import re
import socket
import time
from dataclasses import asdict, dataclass

PUERTOS = (9, 7)


@dataclass
class WolResultado:
    mac: str
    destino: str = "255.255.255.255"
    enviados: int = 0
    error: str | None = None
    tiempo_ms: int = 0

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        return f"Paquete mágico enviado a {self.mac}", True


def normalize_mac(texto: str) -> str:  # propio
    """'aa-bb-cc-dd-ee-ff' / 'AABBCCDDEEFF' -> 'AA:BB:CC:DD:EE:FF'."""
    limpio = re.sub(r"[^0-9A-Fa-f]", "", texto or "")
    if len(limpio) != 12:
        raise ValueError("La MAC tiene 12 caracteres hexadecimales: AA:BB:CC:DD:EE:FF")
    return ":".join(limpio[i:i + 2] for i in range(0, 12, 2)).upper()


def magic_packet(mac: str) -> bytes:  # propio
    return b"\xff" * 6 + bytes.fromhex(normalize_mac(mac).replace(":", "")) * 16


def wake(mac: str, destino: str = "255.255.255.255",  # propio
         puertos: tuple[int, ...] = PUERTOS) -> WolResultado:
    """Manda el paquete a cada puerto (9 y 7: los equipos escuchan uno u otro)."""
    inicio = time.perf_counter()
    try:
        mac = normalize_mac(mac)
    except ValueError as ex:
        return WolResultado(mac=mac, error=str(ex))
    r = WolResultado(mac=mac, destino=destino)
    paquete = magic_packet(mac)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            for puerto in puertos:
                s.sendto(paquete, (destino, puerto))
                r.enviados += 1
    except OSError as ex:
        r.error = f"No se pudo enviar (¿estás conectado a la red?): {ex}"
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r

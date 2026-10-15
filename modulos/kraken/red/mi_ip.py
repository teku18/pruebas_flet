"""
Mi IP:

  local    la IP de este equipo en tu red (192.168.x.x). Truco: se "conecta" un
           socket UDP hacia afuera (UDP no manda nada al conectar) y se le
           pregunta al sistema qué IP usaría para salir.
  pública  la IP con la que te ve internet (la de tu módem o la de tus datos
           móviles). Hay que preguntársela a un servicio de afuera: ipinfo.io
           (también dice ciudad y proveedor) y, si falla, api.ipify.org.
"""
import ipaddress
import socket
import time
from dataclasses import asdict, dataclass

import httpx

SERVICIO_INFO = "https://ipinfo.io/json"
SERVICIO_IP = "https://api.ipify.org?format=json"


@dataclass
class MiIpResultado:
    local: str | None = None
    red: str | None = None          # "192.168.1.0/24" (para buscar dispositivos)
    equipo: str = ""                # nombre de este equipo
    publica: str | None = None
    proveedor: str | None = None    # "AS8151 Uninet" / Telmex…
    ciudad: str | None = None
    error_publica: str | None = None
    tiempo_ms: int = 0

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        partes = [f"Pública {self.publica}" if self.publica else "Sin IP pública",
                  f"local {self.local}" if self.local else "sin red local"]
        return " · ".join(partes), bool(self.publica or self.local)


def local_ip() -> str | None:  # propio
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("1.1.1.1", 80))   # no sale ningún paquete
            ip = s.getsockname()[0]
        except OSError:
            return None
    return None if ip.startswith("0.") else ip


def network_of(ip: str | None) -> str | None:  # propio
    """'192.168.1.37' -> '192.168.1.0/24' (lo normal en casa)."""
    if not ip:
        return None
    return str(ipaddress.ip_network(f"{ip}/24", strict=False))


async def my_ip(servicio_info: str = SERVICIO_INFO, servicio_ip: str = SERVICIO_IP,  # propio
                timeout: float = 8.0) -> MiIpResultado:
    inicio = time.perf_counter()
    r = MiIpResultado(local=local_ip(), equipo=socket.gethostname())
    r.red = network_of(r.local)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cliente:
        try:
            datos = (await cliente.get(servicio_info)).json()
            r.publica = datos.get("ip")
            r.proveedor = datos.get("org")
            r.ciudad = ", ".join(x for x in (datos.get("city"), datos.get("region"),
                                             datos.get("country")) if x) or None
        except (httpx.HTTPError, ValueError):
            try:
                r.publica = (await cliente.get(servicio_ip)).json().get("ip")
            except (httpx.HTTPError, ValueError) as ex:
                r.error_publica = f"No se pudo consultar (¿hay internet?): {type(ex).__name__}"
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r

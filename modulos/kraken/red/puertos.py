"""
Puertos: ¿qué puertos de un equipo están abiertos?

Por cada puerto se intenta conectar (TCP), muchos a la vez (asyncio.Semaphore
limita cuántos al mismo tiempo, para no saturar la red del celular):

  abierto   alguien escucha ahí (SSH, una web, Postgres…)
  cerrado   el equipo contestó "aquí no hay nadie"
  filtrado  nadie contestó a tiempo (un firewall lo tira, o el equipo no existe)
  sin ruta  la red ni siquiera sabe cómo llegar

Úsalo con TUS equipos: escanear equipos ajenos puede verse como un ataque.
"""
import asyncio
import time
from dataclasses import asdict, dataclass, field

from modulos.kraken.models import parse_ports
from modulos.kraken.red.comun import clean_host, resolve
from modulos.kraken.red.ping import tcp_connect

# Para el botón "Comunes" (y el nombre de cada uno: Android no trae /etc/services)
SERVICIOS = {
    20: "FTP datos", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS", 80: "HTTP",
    110: "POP3", 123: "NTP", 143: "IMAP", 161: "SNMP", 389: "LDAP", 443: "HTTPS",
    445: "SMB (Windows)", 465: "SMTP SSL", 548: "AFP", 587: "SMTP envío", 631: "Impresoras",
    993: "IMAP SSL", 995: "POP3 SSL", 1433: "SQL Server", 1521: "Oracle", 1883: "MQTT",
    2049: "NFS", 3000: "Dev (Node…)", 3306: "MySQL", 3389: "Escritorio remoto",
    5000: "Dev (Flask…)", 5432: "PostgreSQL", 5672: "RabbitMQ", 5900: "VNC",
    6379: "Redis", 8000: "Dev (Django…)", 8069: "Odoo", 8072: "Odoo longpolling",
    8080: "HTTP alterno", 8443: "HTTPS alterno", 8550: "Flet", 9000: "Dev / Portainer",
    9090: "Prometheus", 9200: "Elasticsearch", 11434: "Ollama", 27017: "MongoDB",
}
COMUNES = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 587, 993, 995, 1433, 3000, 3306,
           3389, 5000, 5432, 5900, 6379, 8000, 8069, 8080, 8443, 9000, 27017]
MAX_PUERTOS = 5000


@dataclass
class PuertosResultado:
    host: str
    ip: str = ""
    puertos: list[dict] = field(default_factory=list)  # {puerto, estado, servicio, ms}
    revisados: int = 0
    total: int = 0
    cancelado: bool = False
    error: str | None = None

    @property
    def abiertos(self) -> list[dict]:  # propio
        return [p for p in self.puertos if p["estado"] == "abierto"]

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        n = len(self.abiertos)
        lista = ", ".join(str(p["puerto"]) for p in self.abiertos[:8])
        texto = f"{n} abierto{'s' if n != 1 else ''} de {self.revisados}"
        if lista:
            texto += f": {lista}" + ("…" if n > 8 else "")
        if self.cancelado:
            texto += " (cancelado)"
        return texto, True


async def scan(objetivo: str, puertos: str | list[int], timeout: float = 1.0,  # propio
               concurrencia: int = 100, on_progress=None) -> PuertosResultado:
    """on_progress(resultado) cada vez que termina un puerto."""
    try:
        host = clean_host(objetivo)
        lista = parse_ports(puertos) if isinstance(puertos, str) else list(puertos)
    except ValueError as ex:
        return PuertosResultado(host=objetivo, error=str(ex))
    if not lista:
        return PuertosResultado(host=host, error="Escribe al menos un puerto")
    if len(lista) > MAX_PUERTOS:
        return PuertosResultado(host=host, error=f"Máximo {MAX_PUERTOS:,} puertos a la vez")
    r = PuertosResultado(host=host, total=len(lista))
    try:
        r.ip = await resolve(host)
    except ValueError as ex:
        r.error = str(ex)
        return r

    limite = asyncio.Semaphore(concurrencia)
    ultimo_aviso = [0.0]

    async def one(puerto: int):  # propio
        async with limite:
            estado, tiempo = await tcp_connect(r.ip, puerto, timeout)
        r.puertos.append({"puerto": puerto, "estado": estado, "ms": tiempo,
                          "servicio": SERVICIOS.get(puerto, "")})
        r.revisados += 1
        ahora = time.monotonic()  # avisar a la pantalla, pero no más de ~5 veces por segundo
        if on_progress and (ahora - ultimo_aviso[0] > 0.2 or r.revisados == r.total):
            ultimo_aviso[0] = ahora
            on_progress(r)

    try:
        await asyncio.gather(*(one(p) for p in lista))
    except asyncio.CancelledError:
        r.cancelado = True
        r.puertos.sort(key=lambda p: p["puerto"])
        raise
    r.puertos.sort(key=lambda p: p["puerto"])
    return r

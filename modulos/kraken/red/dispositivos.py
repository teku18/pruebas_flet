"""
Dispositivos en mi red: ¿qué hay conectado a mi Wi-Fi?

Cómo funciona (sin permisos especiales):
  1. Tu red sale de tu IP local: 192.168.1.37 -> 192.168.1.0/24 (254 direcciones).
  2. A cada dirección se le "toca la puerta" en unos cuantos puertos comunes,
     muchas a la vez (asyncio + Semaphore). Si contesta en cualquiera, aunque
     sea "cerrado", ahí hay un aparato vivo.
  3. A los vivos se les pregunta su nombre (DNS inverso; el router a veces lo sabe).
  4. Por los puertos abiertos se adivina qué son: 62078 = iPhone/iPad,
     8009 = Chromecast/Google TV, 9100 = impresora, 22 = Linux/servidor…

Límites (de Android, no del código): desde Android 10 las apps no pueden leer
la MAC ni el fabricante de los demás aparatos (en la PC con Linux sí se lee de
/proc/net/arp). Un celular dormido puede no contestar a nada.
"""
import asyncio
import ipaddress
import socket
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from modulos.kraken.red.mi_ip import local_ip, network_of
from modulos.kraken.red.ping import tcp_connect
from modulos.kraken.red.puertos import SERVICIOS

# Puertos para "tocar la puerta" (y qué sugieren si están abiertos)
PUERTOS = {
    80: "Web", 443: "Web", 22: "Linux / servidor", 445: "Compartir archivos", 8080: "Web",
    62078: "iPhone / iPad", 8009: "Chromecast / Google TV", 9100: "Impresora",
    554: "Cámara", 5000: "NAS", 8069: "Odoo", 3389: "Escritorio remoto",
}
MAX_EQUIPOS = 1024  # una red /22 como mucho


@dataclass
class DispositivosResultado:
    red: str = ""
    propia: str | None = None                 # la IP de este equipo
    # {ip, nombre, parece, puertos, servicios, mac, ms, este}
    dispositivos: list[dict] = field(default_factory=list)
    metodo: str = ""
    revisados: int = 0
    total: int = 0
    cancelado: bool = False
    aviso: str | None = None
    error: str | None = None
    tiempo_ms: int = 0

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        n = len(self.dispositivos)
        texto = f"{n} dispositivo{'s' if n != 1 else ''} en {self.red}"
        return texto + (" (cancelado)" if self.cancelado else ""), n > 0


def guess(ip: str, abiertos: list[int]) -> str:  # propio
    """Por sus puertos abiertos (y su IP), qué parece ser."""
    for puerto in (62078, 8009, 9100, 554, 5000, 3389, 445, 22, 8069):
        if puerto in abiertos:
            return PUERTOS[puerto]
    if ip.endswith((".1", ".254")):  # el router casi siempre es la .1 (o la .254)
        return "Probablemente tu router"
    if any(p in abiertos for p in (80, 443, 8080)):
        return "Con página web (router, cámara, impresora…)"
    return ""


def parse_network(texto: str | None) -> ipaddress.IPv4Network:  # propio
    """
    '192.168.1.0/24' -> esa red · '192.168.1.37' -> 192.168.1.0/24 ·
    vacío/None -> la red de este equipo. Lanza ValueError si no se puede.
    """
    t = (texto or "").strip() or network_of(local_ip())
    if not t:
        raise ValueError("No estás conectado a una red (Wi-Fi o cable)")
    try:
        rango = ipaddress.ip_network(t if "/" in t else network_of(t), strict=False)
    except ValueError as ex:
        raise ValueError(f"Red no válida: {t} (así: 192.168.1.0/24)") from ex
    if rango.version != 4:
        raise ValueError("Solo redes IPv4 (192.168.x.x)")
    if not rango.is_private:  # nunca barrer direcciones de internet por error
        raise ValueError("Solo redes privadas: 192.168.x.x, 10.x.x.x o 172.16–31.x.x")
    if rango.num_addresses - 2 > MAX_EQUIPOS:
        raise ValueError(f"Red muy grande ({rango.num_addresses - 2:,} direcciones). "
                         f"Máximo {MAX_EQUIPOS:,} (/22).")
    return rango


def read_arp() -> dict[str, str]:  # propio
    """IP -> MAC de la tabla ARP (Linux). En Android 10+ está bloqueada: regresa {}."""
    try:
        lineas = Path("/proc/net/arp").read_text().splitlines()[1:]
    except OSError:
        return {}
    tabla = {}
    for linea in lineas:
        partes = linea.split()
        if len(partes) >= 4 and partes[3] != "00:00:00:00:00:00":
            tabla[partes[0]] = partes[3].upper()
    return tabla


async def _name(ip: str) -> str | None:  # propio
    loop = asyncio.get_running_loop()
    try:
        nombre, _ = await asyncio.wait_for(loop.getnameinfo((ip, 0), socket.NI_NAMEREQD), 1.5)
    except (OSError, asyncio.TimeoutError):
        return None
    return None if nombre == ip else nombre


async def discover(red: str | None = None, puertos: list[int] | None = None,  # propio
                   timeout: float = 0.7, concurrencia: int = 256,
                   on_progress=None) -> DispositivosResultado:
    """red: '192.168.1.0/24' o vacío (= la red de este equipo)."""
    inicio = time.perf_counter()
    r = DispositivosResultado(propia=local_ip())
    try:
        rango = parse_network(red)
    except ValueError as ex:
        r.error = str(ex)
        return r
    equipos = [str(ip) for ip in (rango.hosts() if rango.num_addresses > 2 else rango)]
    r.red, r.total = str(rango), len(equipos)
    lista_puertos = puertos or list(PUERTOS)
    r.metodo = f"TCP a {len(lista_puertos)} puertos comunes"
    limite = asyncio.Semaphore(concurrencia)
    ultimo_aviso = [0.0]

    async def knock(ip: str, puerto: int):  # propio
        async with limite:
            return puerto, *(await tcp_connect(ip, puerto, timeout))

    async def one(ip: str):  # propio
        respuestas = await asyncio.gather(*(knock(ip, p) for p in lista_puertos))
        vivos = [(p, e, t) for p, e, t in respuestas if e in ("abierto", "cerrado")]
        if vivos or ip == r.propia:
            abiertos = sorted(p for p, e, _ in vivos if e == "abierto")
            r.dispositivos.append({
                "ip": ip, "nombre": None, "parece": guess(ip, abiertos), "puertos": abiertos,
                "servicios": [SERVICIOS.get(p, PUERTOS.get(p, "")) for p in abiertos],
                "mac": None, "este": ip == r.propia,
                "ms": min((t for _, _, t in vivos if t is not None), default=None)})
        r.revisados += 1
        ahora = time.monotonic()
        if on_progress and (ahora - ultimo_aviso[0] > 0.3 or r.revisados == r.total):
            ultimo_aviso[0] = ahora
            _sort(r)
            on_progress(r)

    try:
        await asyncio.gather(*(one(ip) for ip in equipos))
        nombres = await asyncio.gather(*(_name(d["ip"]) for d in r.dispositivos))
        arp = read_arp()
        for d, nombre in zip(r.dispositivos, nombres):
            d["nombre"] = nombre or (socket.gethostname() if d["este"] else None)
            d["mac"] = arp.get(d["ip"])
            if d["este"]:
                d["parece"] = "Este equipo"
    except asyncio.CancelledError:
        r.cancelado = True
        _sort(r)
        raise
    _sort(r)
    sin_abiertos = [d for d in r.dispositivos if not d["puertos"] and not d["este"]]
    if r.total >= 16 and len(sin_abiertos) > 0.5 * r.total:
        r.aviso = ("Más de la mitad de las direcciones «contestaron» sin ningún puerto abierto: "
                   "parece un firewall respondiendo por ellas. Estos resultados no son reales; "
                   "prueba conectado a tu Wi-Fi de casa.")
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r


def _sort(r: DispositivosResultado):  # propio
    r.dispositivos.sort(key=lambda d: ipaddress.ip_address(d["ip"]))

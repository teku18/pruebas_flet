"""
Ping: ¿el equipo responde? y cuánto tarda.

Tres maneras, se usa la primera que funcione:
  1. "icmp"    el ping de verdad, con un socket ICMP de tipo DATAGRAMA: Linux y
               Android dejan usarlo sin ser administrador si el sistema lo
               permite (net.ipv4.ping_group_range). El sistema pone el
               identificador y la suma de verificación.
  2. "sistema" el programa `ping` del equipo (si existe).
  3. "tcp"     "ping TCP": cuánto tarda en conectar a un puerto (443, luego 80).
               Si el equipo contesta, aunque sea "cerrado", está vivo.

El resultado dice qué manera se usó: el TCP mide algo parecido, no igual.
"""
import asyncio
import os
import re
import shutil
import socket
import struct
import time
from dataclasses import asdict, dataclass, field

from modulos.kraken.red.comun import clean_host, is_ip, ms, resolve

METODOS = {"icmp": "ICMP", "sistema": "ping del sistema", "tcp": "TCP"}
PUERTOS_TCP = (443, 80)


@dataclass
class PingResultado:
    host: str
    ip: str = ""
    metodo: str = ""
    puerto_tcp: int | None = None
    tiempos: list[float | None] = field(default_factory=list)   # None = perdido
    error: str | None = None

    @property
    def enviados(self) -> int:  # propio
        return len(self.tiempos)

    @property
    def recibidos(self) -> list[float]:  # propio
        return [t for t in self.tiempos if t is not None]

    def stats(self) -> tuple[float, float, float] | None:  # propio
        r = self.recibidos
        return (min(r), round(sum(r) / len(r), 1), max(r)) if r else None

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        s = self.stats()
        if not s:
            return f"Sin respuesta (0/{self.enviados})", False
        return f"{len(self.recibidos)}/{self.enviados} · {s[1]} ms", True


# ============================================================================
def _icmp_available() -> bool:  # propio
    try:
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP).close()
        return True
    except OSError:
        return False


def _system_ping() -> str | None:  # propio
    return shutil.which("ping") or next(
        (p for p in ("/system/bin/ping", "/bin/ping", "/usr/bin/ping")
         if os.path.exists(p)), None)


def choose_method() -> str:  # propio
    if _icmp_available():
        return "icmp"
    if _system_ping():
        return "sistema"
    return "tcp"


async def _icmp_once(ip: str, seq: int, timeout: float) -> float | None:  # propio
    loop = asyncio.get_running_loop()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP) as s:
        s.setblocking(False)
        paquete = struct.pack("!BBHHH", 8, 0, 0, 0, seq) + b"ControlKraken"  # 8 = echo
        inicio = time.perf_counter()
        await loop.sock_sendto(s, paquete, (ip, 0))
        limite = inicio + timeout
        while (resta := limite - time.perf_counter()) > 0:
            try:
                datos, _ = await asyncio.wait_for(loop.sock_recvfrom(s, 1024), resta)
            except asyncio.TimeoutError:
                return None
            # respuesta: tipo 0 (echo reply) con nuestro número de secuencia
            if len(datos) >= 8 and datos[0] == 0 and struct.unpack("!H", datos[6:8])[0] == seq:
                return ms(time.perf_counter() - inicio)
        return None


TIEMPO = re.compile(r"time[=<]\s*([\d.]+)\s*ms")


async def _system_once(ip: str, timeout: float) -> float | None:  # propio
    proceso = await asyncio.create_subprocess_exec(
        _system_ping(), "-c", "1", "-W", str(max(1, round(timeout))), ip,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        salida, _ = await asyncio.wait_for(proceso.communicate(), timeout + 2)
    except asyncio.TimeoutError:
        proceso.kill()
        return None
    m = TIEMPO.search(salida.decode(errors="ignore"))
    return float(m.group(1)) if m else None


async def tcp_connect(ip: str, puerto: int, timeout: float) -> tuple[str, float | None]:  # propio
    """('abierto' | 'cerrado' | 'filtrado' | 'sin ruta', ms o None). Lo usa puertos.py."""
    inicio = time.perf_counter()
    try:
        _, escritor = await asyncio.wait_for(asyncio.open_connection(ip, puerto), timeout)
        tiempo = ms(time.perf_counter() - inicio)
        escritor.close()
        try:
            await escritor.wait_closed()
        except OSError:
            pass
        return "abierto", tiempo
    except ConnectionRefusedError:  # el equipo contestó "aquí no hay nadie": está vivo
        return "cerrado", ms(time.perf_counter() - inicio)
    except asyncio.TimeoutError:
        return "filtrado", None
    except OSError:
        return "sin ruta", None


async def _tcp_once(ip: str, timeout: float, puerto: int) -> float | None:  # propio
    estado, tiempo = await tcp_connect(ip, puerto, timeout)
    return tiempo if estado in ("abierto", "cerrado") else None


async def ping(objetivo: str, veces: int = 4, timeout: float = 2.0, pausa: float = 0.5,  # propio
               metodo: str | None = None, on_progress=None) -> PingResultado:
    """
    on_progress(resultado) se llama después de cada intento (para ir pintando).
    `metodo` fuerza una manera (lo usan las pruebas); si no, se elige sola.
    """
    try:
        host = clean_host(objetivo)
    except ValueError as ex:
        return PingResultado(host=objetivo, error=str(ex))
    r = PingResultado(host=host)
    try:
        r.ip = await resolve(host)
    except ValueError as ex:
        r.error = str(ex)
        return r
    if not is_ip(r.ip) or ":" in r.ip:
        metodo = metodo or "tcp"   # IPv6: el ICMP de aquí es solo IPv4
    r.metodo = metodo or choose_method()
    if r.metodo == "tcp":
        r.puerto_tcp = PUERTOS_TCP[0]
        estado, _ = await tcp_connect(r.ip, PUERTOS_TCP[0], timeout)
        if estado not in ("abierto", "cerrado"):
            r.puerto_tcp = PUERTOS_TCP[1]
    for k in range(veces):
        try:
            if r.metodo == "icmp":
                tiempo = await _icmp_once(r.ip, k + 1, timeout)
            elif r.metodo == "sistema":
                tiempo = await _system_once(r.ip, timeout)
            else:
                tiempo = await _tcp_once(r.ip, timeout, r.puerto_tcp)
        except PermissionError:   # el sistema no dejó usar ICMP: se cambia a TCP
            r.metodo, r.puerto_tcp = "tcp", PUERTOS_TCP[0]
            tiempo = await _tcp_once(r.ip, timeout, r.puerto_tcp)
        except OSError as ex:
            r.error = f"Error de red: {ex}"
            return r
        r.tiempos.append(tiempo)
        if on_progress:
            on_progress(r)
        if k < veces - 1:
            await asyncio.sleep(pausa)
    return r

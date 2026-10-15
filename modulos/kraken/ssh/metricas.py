"""
Métricas del servidor con UN solo comando (rápido: una ida y vuelta).

Se lee /proc y unos cuantos comandos con LC_ALL=C (formato fijo, en inglés):
así se entiende igual un servidor en español que uno en inglés. Cada sección
empieza con una marca "@@nombre".

CPU % y velocidad de red salen de COMPARAR dos lecturas (el panel lee cada 5 s):
/proc/stat dice cuánto tiempo lleva el CPU trabajando desde que prendió; la
diferencia entre dos lecturas, dividida entre el tiempo total, es el % de uso.
"""
import shlex
from dataclasses import asdict, dataclass, field

SCRIPT = r"""export LC_ALL=C
echo @@os; (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || uname -s; hostname; uname -r
echo @@uptime; cat /proc/uptime
echo @@load; cat /proc/loadavg; nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo
echo @@cpu; head -1 /proc/stat
echo @@mem; grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
echo @@df; df -P -k -x tmpfs -x devtmpfs -x squashfs -x overlay -x efivarfs 2>/dev/null
echo @@net; cat /proc/net/dev
echo @@ps; ps -eo pid=,pcpu=,pmem=,rss=,comm= --sort=-pcpu 2>/dev/null | head -8
echo @@svc; for s in {servicios}; do echo "$s $(systemctl is-active "$s" 2>/dev/null || true)"; done
echo @@fin
"""


def script(servicios: list[str]) -> str:  # propio
    nombres = " ".join(shlex.quote(s) for s in servicios) or "''"
    return SCRIPT.replace("{servicios}", nombres)


@dataclass
class Muestra:
    """Una lectura del servidor (y lo calculado contra la anterior)."""
    sistema: str = ""
    nombre: str = ""
    kernel: str = ""
    encendido_s: float = 0
    carga: tuple[float, float, float] = (0, 0, 0)
    nucleos: int = 1
    cpu_total: int = 0           # contadores crudos de /proc/stat
    cpu_ocupado: int = 0
    cpu: float | None = None     # % (None en la primera lectura)
    ram_total: int = 0           # KB
    ram_disponible: int = 0
    swap_total: int = 0
    swap_libre: int = 0
    discos: list[dict] = field(default_factory=list)   # {montaje, total, usado, pct}
    red_rx: int = 0              # bytes acumulados (sin lo)
    red_tx: int = 0
    rx_s: float | None = None    # bytes por segundo
    tx_s: float | None = None
    procesos: list[dict] = field(default_factory=list)  # {pid, cpu, mem, rss, nombre}
    servicios: dict[str, str] = field(default_factory=dict)  # odoo -> active
    momento: float = 0           # time.monotonic() de la lectura

    @property
    def ram_pct(self) -> float:  # propio
        return round(100 * (1 - self.ram_disponible / self.ram_total), 1) if self.ram_total else 0

    @property
    def ram_usada(self) -> int:  # propio
        return self.ram_total - self.ram_disponible

    @property
    def swap_pct(self) -> float:  # propio
        return round(100 * (1 - self.swap_libre / self.swap_total), 1) if self.swap_total else 0

    @property
    def disco_max(self) -> float:  # propio
        return max((d["pct"] for d in self.discos), default=0)

    def summary(self) -> str:  # propio
        cpu = f"CPU {self.cpu:.0f}%" if self.cpu is not None else "CPU —"
        return f"{cpu} · RAM {self.ram_pct:.0f}% · disco {self.disco_max:.0f}%"

    def to_dict(self) -> dict:  # propio
        return asdict(self)


def _sections(texto: str) -> dict[str, list[str]]:  # propio
    secciones, actual = {}, None
    for linea in texto.splitlines():
        if linea.startswith("@@"):
            actual = linea[2:].strip()
            secciones[actual] = []
        elif actual:
            secciones[actual].append(linea)
    return secciones


def parse(texto: str, momento: float, anterior: "Muestra | None" = None) -> Muestra:  # propio
    s = _sections(texto)
    if "fin" not in s:
        raise ValueError("El servidor no regresó todos los datos (¿no es Linux?)")
    m = Muestra(momento=momento)
    os_ = s.get("os", [])
    m.sistema, m.nombre, m.kernel = (os_ + ["", "", ""])[:3]
    if s.get("uptime"):
        m.encendido_s = float(s["uptime"][0].split()[0])
    if s.get("load"):
        partes = s["load"][0].split()
        m.carga = (float(partes[0]), float(partes[1]), float(partes[2]))
        if len(s["load"]) > 1 and s["load"][1].strip().isdigit():
            m.nucleos = int(s["load"][1])
    if s.get("cpu"):  # cpu user nice system idle iowait irq softirq steal
        valores = [int(v) for v in s["cpu"][0].split()[1:9]]
        inactivo = valores[3] + (valores[4] if len(valores) > 4 else 0)
        m.cpu_total, m.cpu_ocupado = sum(valores), sum(valores) - inactivo
    mem = {}
    for linea in s.get("mem", []):
        clave, _, valor = linea.partition(":")
        mem[clave] = int(valor.split()[0])
    m.ram_total, m.ram_disponible = mem.get("MemTotal", 0), mem.get("MemAvailable", 0)
    m.swap_total, m.swap_libre = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
    for linea in s.get("df", [])[1:]:  # Filesystem 1024-blocks Used Available Capacity Mounted
        partes = linea.split()
        if len(partes) >= 6 and partes[1].isdigit() and int(partes[1]) > 0:
            total, usado = int(partes[1]), int(partes[2])
            if partes[5].startswith(("/snap", "/boot/efi")):
                continue
            m.discos.append({"montaje": " ".join(partes[5:]), "dispositivo": partes[0],
                             "total": total, "usado": usado,
                             "pct": round(100 * usado / total, 1)})
    for linea in s.get("net", [])[2:]:
        nombre, _, datos = linea.partition(":")
        if nombre.strip() == "lo" or not datos.split():
            continue
        campos = datos.split()
        m.red_rx += int(campos[0])
        m.red_tx += int(campos[8])
    for linea in s.get("ps", []):
        partes = linea.split(None, 4)
        if len(partes) == 5:
            m.procesos.append({"pid": int(partes[0]), "cpu": float(partes[1]),
                               "mem": float(partes[2]), "rss": int(partes[3]),
                               "nombre": partes[4]})
    for linea in s.get("svc", []):
        nombre, _, estado = linea.partition(" ")
        if nombre:
            m.servicios[nombre] = estado.strip() or "no existe"
    if anterior is not None and anterior.cpu_total:
        dt = m.cpu_total - anterior.cpu_total
        if dt > 0:
            m.cpu = round(100 * (m.cpu_ocupado - anterior.cpu_ocupado) / dt, 1)
        segundos = m.momento - anterior.momento
        if segundos > 0:
            m.rx_s = max(0.0, (m.red_rx - anterior.red_rx) / segundos)
            m.tx_s = max(0.0, (m.red_tx - anterior.red_tx) / segundos)
    return m


def uptime_text(segundos: float) -> str:  # propio
    """266580 -> '3 días, 2 h'."""
    dias, resto = divmod(int(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return f"{dias} día{'s' if dias != 1 else ''}, {horas} h"
    if horas:
        return f"{horas} h {minutos} min"
    return f"{minutos} min"


def kb_text(kb: int) -> str:  # propio
    """KB -> '31.2 GB'."""
    valor = float(kb)
    for unidad in ("KB", "MB", "GB", "TB"):
        if valor < 1024 or unidad == "TB":
            return f"{valor:.0f} {unidad}" if unidad == "KB" else f"{valor:.1f} {unidad}"
        valor /= 1024
    return ""

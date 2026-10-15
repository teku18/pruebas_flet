"""
Lo que se hace en un servidor además de mirar:

  run_command()  un comando guardado ("Reiniciar Odoo"), con sudo si lo trae
  read_log()     las últimas N líneas de un archivo de log (con búsqueda)

Ambos se anotan en el historial de Red (herramienta "ssh").
"""
import shlex
from dataclasses import asdict, dataclass

from modulos.kraken.ssh.conexion import Salida, Sesion

MAX_SALIDA = 64_000  # lo que se guarda en el historial de cada comando


@dataclass
class ComandoResultado:
    servidor: str
    nombre: str
    comando: str
    codigo: int | None = None
    salida: str = ""
    errores: str = ""
    tiempo_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:  # propio
        d = asdict(self)
        d["salida"], d["errores"] = d["salida"][:MAX_SALIDA], d["errores"][:MAX_SALIDA]
        return d

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return f"{self.nombre}: {self.error}"[:255], False
        if self.codigo == 0:
            return f"{self.nombre}: listo ({self.tiempo_ms} ms)"[:255], True
        return f"{self.nombre}: terminó con error {self.codigo}"[:255], False


def run_command(sesion: Sesion, nombre: str, comando: str,  # propio
                timeout: float = 120) -> ComandoResultado:
    r = ComandoResultado(servidor=sesion.equipo.nombre, nombre=nombre, comando=comando)
    try:
        s: Salida = sesion.run(comando, timeout=timeout)
    except Exception as ex:  # noqa: BLE001  (red, tiempo, permisos)
        r.error = f"{type(ex).__name__}: {ex}"
        return r
    r.codigo, r.salida, r.errores, r.tiempo_ms = s.codigo, s.texto, s.errores, s.tiempo_ms
    return r


def log_command(ruta: str, lineas: int, buscar: str = "", con_sudo: bool = False) -> str:  # propio
    """`tail -n 300 /var/log/…` (filtrando si hay búsqueda: grep sin distinguir mayúsculas)."""
    base = f"tail -n {int(lineas)} {shlex.quote(ruta)}"
    if buscar.strip():
        base = (f"grep -i -F -- {shlex.quote(buscar.strip())} {shlex.quote(ruta)} "
                f"| tail -n {int(lineas)}")
        if con_sudo:  # el sudo va en el grep (es quien abre el archivo)
            return "sudo " + base
        return base
    return ("sudo " if con_sudo else "") + base


def read_log(sesion: Sesion, ruta: str, lineas: int = 200, buscar: str = "",  # propio
             con_sudo: bool = False) -> Salida:
    return sesion.run(log_command(ruta, lineas, buscar, con_sudo), timeout=30)

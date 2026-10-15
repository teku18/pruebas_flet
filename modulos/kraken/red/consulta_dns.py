"""
DNS: ¿a dónde apunta un dominio?

Se le pregunta a UN servidor DNS que tú eliges en Ajustes (1.1.1.1 de
Cloudflare por defecto), no al del celular: así ves lo que ve "internet" y no
una respuesta guardada de tu red. Con dnspython (puro Python).

  A / AAAA  la IP (v4 / v6)            MX   quién recibe el correo
  CNAME     "es otro nombre de…"       TXT  verificaciones, SPF, DKIM…
  NS        quién administra el dominio
  PTR       al revés: de una IP a su nombre
"""
import time
from dataclasses import asdict, dataclass, field

import dns.asyncresolver
import dns.exception
import dns.rdatatype
import dns.resolver
import dns.reversename

from modulos.kraken.red.comun import clean_host, is_ip

TIPOS = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]


@dataclass
class DnsResultado:
    nombre: str
    servidor: str = ""
    registros: dict[str, list[dict]] = field(default_factory=dict)  # tipo -> [{valor, ttl}]
    tiempo_ms: int = 0
    avisos: list[str] = field(default_factory=list)   # un tipo falló, los demás sí
    error: str | None = None

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        principales = (self.registros.get("A") or self.registros.get("AAAA")
                       or self.registros.get("PTR") or self.registros.get("CNAME") or [])
        if not any(self.registros.values()):
            return "Sin registros", False
        texto = ", ".join(r["valor"] for r in principales[:3]) or "Sin A/AAAA"
        tipos = [t for t, v in self.registros.items() if v]
        return f"{texto} · {len(tipos)} tipo{'s' if len(tipos) != 1 else ''}", True


def parse_server(texto: str) -> tuple[str, int]:  # propio
    """'1.1.1.1' -> ('1.1.1.1', 53) · '127.0.0.1:5353' -> ('127.0.0.1', 5353)."""
    t = (texto or "").strip()
    puerto = 53
    if t.count(":") == 1:
        t, _, p = t.partition(":")
        if not p.isdigit():
            raise ValueError(f"Puerto no válido: {p}")
        puerto = int(p)
    if not is_ip(t):
        raise ValueError("El servidor DNS debe ser una IP, p. ej. 1.1.1.1")
    return t, puerto


def _value(rdata, tipo: str) -> str:  # propio
    if tipo == "MX":
        return f"{rdata.preference} {rdata.exchange.to_text(omit_final_dot=True)}"
    if tipo == "TXT":
        return "".join(p.decode(errors="replace") for p in rdata.strings)
    if tipo in ("CNAME", "NS", "PTR"):
        return rdata.target.to_text(omit_final_dot=True)
    return rdata.to_text()


async def lookup(objetivo: str, servidor: str, tipos: list[str] | None = None,  # propio
                 timeout: float = 5.0) -> DnsResultado:
    try:
        nombre = clean_host(objetivo)
        ip_servidor, puerto = parse_server(servidor)
    except ValueError as ex:
        return DnsResultado(nombre=objetivo, servidor=servidor, error=str(ex))
    r = DnsResultado(nombre=nombre, servidor=servidor)
    resolver = dns.asyncresolver.Resolver(configure=False)  # no lee la config del equipo
    resolver.nameservers = [ip_servidor]
    resolver.port = puerto
    resolver.lifetime = timeout

    if is_ip(nombre):  # una IP: se pregunta su nombre (PTR)
        consultas = [("PTR", dns.reversename.from_address(nombre))]
    else:
        consultas = [(t, nombre) for t in (tipos or TIPOS)]

    inicio = time.perf_counter()
    for tipo, pregunta in consultas:
        try:
            respuesta = await resolver.resolve(pregunta, tipo, raise_on_no_answer=False)
            ttl = respuesta.rrset.ttl if respuesta.rrset is not None else None
            r.registros[tipo] = [{"valor": _value(d, tipo), "ttl": ttl}
                                 for d in (respuesta.rrset or [])]
        except dns.resolver.NXDOMAIN:
            r.error = f"El dominio «{nombre}» no existe"
            break
        except dns.exception.Timeout:
            r.error = f"El servidor DNS {servidor} no contestó (¿hay internet?)"
            break
        except dns.resolver.NoNameservers as ex:
            r.error = f"El servidor DNS rechazó la consulta: {ex}"
            break
        except dns.exception.DNSException as ex:
            r.registros[tipo] = []
            r.avisos.append(f"{tipo}: {ex}")
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r

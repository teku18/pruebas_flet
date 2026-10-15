"""
Whois: de quién es un dominio, con qué registrador y CUÁNDO VENCE.

Dos maneras, se usa la primera que funcione:
  1. RDAP   el "whois moderno": una API web que regresa JSON (rdap.org te
            manda al servidor correcto del dominio). Fácil de leer, pero no
            todos los dominios lo tienen (varios .mx, por ejemplo).
  2. WHOIS  el de siempre: se abre una conexión TCP al puerto 43 y se manda el
            dominio. Primero se pregunta a whois.iana.org QUIÉN lleva esa
            terminación (.com, .mx…) y luego a ese servidor. Regresa texto
            libre, distinto en cada país: se buscan las líneas conocidas
            ("Expiration Date:", "Registrar:"…).
"""
import asyncio
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

import httpx

from modulos.kraken.red.comun import clean_host, is_ip

RDAP = "https://rdap.org/domain/"
IANA = "whois.iana.org"
TEXTO_MAX = 20_000

CAMPOS = {
    "registrador": r"(?:Registrar|Sponsoring Registrar|Registrar Name|registrar)",
    "creado": r"(?:Creation Date|Created On|Created|created|Registered on|Registration Time|"
              r"Fecha de Creaci[oó]n)",
    "vence": r"(?:Registry Expiry Date|Registrar Registration Expiration Date|Expiration Date|"
             r"Expiry Date|Expires On|Expiration Time|paid-till|expires|Fecha de Expiraci[oó]n)",
    "actualizado": r"(?:Updated Date|Last Modified|Last Updated On|changed|Last updated)",
}
FECHA = [(r"(\d{4})-(\d{2})-(\d{2})", "ymd"), (r"(\d{4})\.(\d{2})\.(\d{2})", "ymd"),
         (r"(\d{4})/(\d{2})/(\d{2})", "ymd"), (r"(\d{2})-(\w{3})-(\d{4})", "dmy_txt"),
         (r"(\d{2})/(\d{2})/(\d{4})", "dmy")]
MESES = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                     "sep", "oct", "nov", "dec"], start=1)}


@dataclass
class WhoisResultado:
    dominio: str
    fuente: str = ""                  # "RDAP" | "WHOIS"
    registrador: str | None = None
    creado: str | None = None         # AAAA-MM-DD
    vence: str | None = None
    actualizado: str | None = None
    dias_restantes: int | None = None
    estado: list[str] = field(default_factory=list)
    servidores: list[str] = field(default_factory=list)   # name servers
    texto: str = ""                   # la respuesta tal cual (WHOIS) o resumida
    error: str | None = None
    tiempo_ms: int = 0

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        if self.dias_restantes is None:
            return (f"{self.registrador or 'Registrador ?'} · sin fecha de vencimiento")[:255], True
        if self.dias_restantes < 0:
            return f"Venció hace {-self.dias_restantes} días", False
        return f"Vence {self.vence} (en {self.dias_restantes} días)"[:255], True


def to_date(texto: str | None) -> str | None:  # propio
    """'2026-03-15T04:00:00Z' / '15-mar-2026' / '2026.03.15' -> '2026-03-15'."""
    if not texto:
        return None
    for patron, forma in FECHA:
        m = re.search(patron, texto)
        if not m:
            continue
        try:
            if forma == "ymd":
                d = date(int(m[1]), int(m[2]), int(m[3]))
            elif forma == "dmy":
                d = date(int(m[3]), int(m[2]), int(m[1]))
            else:
                d = date(int(m[3]), MESES[m[2][:3].lower()], int(m[1]))
            return d.isoformat()
        except (ValueError, KeyError):
            continue
    return None


def _days_left(r: WhoisResultado):  # propio
    if r.vence:
        r.dias_restantes = (date.fromisoformat(r.vence) - date.today()).days


# ============================================================================
# RDAP
# ============================================================================
def parse_rdap(datos: dict, r: WhoisResultado):  # propio
    for e in datos.get("events", []):
        accion, cuando = e.get("eventAction", ""), to_date(e.get("eventDate"))
        if accion == "registration":
            r.creado = cuando
        elif accion == "expiration":
            r.vence = cuando
        elif accion in ("last changed", "last update of RDAP database") and not r.actualizado:
            r.actualizado = cuando
    for ent in datos.get("entities", []):
        if "registrar" in ent.get("roles", []):
            for campo in (ent.get("vcardArray") or [None, []])[1]:
                if campo and campo[0] == "fn":
                    r.registrador = campo[3]
    r.servidores = [ns.get("ldhName", "").lower() for ns in datos.get("nameservers", [])
                    if ns.get("ldhName")]
    r.estado = list(datos.get("status", []))
    r.texto = "\n".join(filter(None, [
        f"Registrador: {r.registrador}" if r.registrador else "",
        f"Creado: {r.creado}" if r.creado else "", f"Vence: {r.vence}" if r.vence else "",
        f"Actualizado: {r.actualizado}" if r.actualizado else "",
        "Estado: " + ", ".join(r.estado) if r.estado else "",
        "Servidores DNS: " + ", ".join(r.servidores) if r.servidores else ""]))


async def _rdap(dominio: str, base: str, timeout: float) -> dict | None:  # propio
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cliente:
        respuesta = await cliente.get(base + dominio,
                                      headers={"Accept": "application/rdap+json"})
        if respuesta.status_code != 200:
            return None
        return respuesta.json()


# ============================================================================
# WHOIS (puerto 43)
# ============================================================================
async def whois_query(servidor: str, pregunta: str, puerto: int = 43,  # propio
                      timeout: float = 10.0) -> str:
    lector, escritor = await asyncio.wait_for(asyncio.open_connection(servidor, puerto), timeout)
    try:
        escritor.write(pregunta.encode("idna") + b"\r\n")
        await escritor.drain()
        datos = await asyncio.wait_for(lector.read(200_000), timeout)
        resto = datos
        while resto:  # algunos servidores mandan en varios pedazos
            resto = await asyncio.wait_for(lector.read(200_000), timeout)
            datos += resto
    finally:
        escritor.close()
    return datos.decode("utf-8", errors="replace")


def parse_whois(texto: str, r: WhoisResultado):  # propio
    for campo, etiqueta in CAMPOS.items():
        m = re.search(rf"^\s*{etiqueta}\s*:\s*(.+?)\s*$", texto, re.M | re.I)
        if m and m.group(1).strip():
            valor = m.group(1).strip()
            setattr(r, campo, valor if campo == "registrador" else to_date(valor))
    r.servidores = sorted({m.lower().rstrip(".") for m in re.findall(
        r"^\s*(?:Name Server|nserver|DNS|Nameservers?)\s*:\s*(\S+)", texto, re.M | re.I)})
    r.estado = re.findall(r"^\s*(?:Domain Status|Status|state)\s*:\s*(\S+)", texto, re.M | re.I)


async def _whois(dominio: str, iana: str, puerto: int, timeout: float) -> str:  # propio
    tld = dominio.rsplit(".", 1)[-1]
    respuesta_iana = await whois_query(iana, tld, puerto, timeout)
    m = re.search(r"^(?:refer|whois):\s*(\S+)", respuesta_iana, re.M | re.I)
    if not m:
        raise ValueError(f"No encontré quién administra los dominios .{tld}")
    texto = await whois_query(m.group(1), dominio, puerto, timeout)
    # .com/.net: el registro solo da lo básico; el registrador tiene el detalle
    m2 = re.search(r"Registrar WHOIS Server:\s*(\S+)", texto, re.I)
    if m2 and m2.group(1).lower() not in (m.group(1).lower(), ""):
        try:
            texto += "\n\n" + await whois_query(m2.group(1), dominio, puerto, timeout)
        except (OSError, asyncio.TimeoutError):
            pass
    return texto


# ============================================================================
async def lookup(objetivo: str, rdap: str = RDAP, iana: str = IANA, puerto: int = 43,  # propio
                 timeout: float = 10.0) -> WhoisResultado:
    try:
        dominio = clean_host(objetivo)
    except ValueError as ex:
        return WhoisResultado(dominio=objetivo, error=str(ex))
    if is_ip(dominio):
        return WhoisResultado(dominio=dominio, error="Whois aquí es para dominios (ejemplo.com)")
    if dominio.startswith("www."):
        dominio = dominio[4:]
    if "." not in dominio:
        return WhoisResultado(dominio=dominio, error="Escribe el dominio completo (ejemplo.com)")
    r = WhoisResultado(dominio=dominio)
    inicio = time.perf_counter()
    try:
        datos = await _rdap(dominio, rdap, timeout) if rdap else None
    except (httpx.HTTPError, ValueError):
        datos = None
    if datos:
        r.fuente = "RDAP"
        parse_rdap(datos, r)
    else:
        try:
            r.texto = (await _whois(dominio, iana, puerto, timeout))[:TEXTO_MAX]
            r.fuente = "WHOIS"
            if re.search(r"no match|not found|no entries found|no data found|"
                         r"no se encontr|object does not exist", r.texto, re.I):
                r.error = f"«{dominio}» no está registrado (¿está libre?)"
            else:
                parse_whois(r.texto, r)
        except (OSError, asyncio.TimeoutError) as ex:
            r.error = f"No se pudo consultar (¿hay internet?): {type(ex).__name__}"
        except ValueError as ex:
            r.error = str(ex)
    _days_left(r)
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r


def now_iso() -> str:  # propio
    return datetime.now().isoformat(timespec="seconds")

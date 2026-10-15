"""
Certificado HTTPS: de quién es, quién lo firmó y cuándo vence.

Primero se conecta "en serio" (verificando, como un navegador). Si la
verificación falla (vencido, autofirmado, de otro dominio…) se dice por qué y
se vuelve a conectar SIN verificar solo para leer sus datos.

Para leer un certificado sin verificarlo se usa ssl._ssl._test_decode_cert:
es interna de Python (por eso el guion bajo), pero evita instalar una
librería grande solo para esto. Si un día desaparece, solo se pierde ese
detalle; el resultado de la verificación sigue.
"""
import asyncio
import os
import socket
import ssl
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from modulos.kraken.red.comun import clean_host


@dataclass
class CertResultado:
    host: str
    puerto: int = 443
    valido: bool = False
    motivo: str | None = None          # por qué no es válido
    para: str | None = None            # CN del certificado
    nombres: list[str] = field(default_factory=list)   # dominios que cubre (SAN)
    emisor: str | None = None          # quién lo firmó (Let's Encrypt…)
    desde: str | None = None           # ISO
    hasta: str | None = None
    dias_restantes: int | None = None
    tls: str | None = None             # TLSv1.3
    error: str | None = None
    tiempo_ms: int = 0

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    def summary(self) -> tuple[str, bool]:  # propio
        if self.error:
            return self.error[:255], False
        if self.dias_restantes is None:
            return ("Válido" if self.valido else f"No válido: {self.motivo}")[:255], self.valido
        if self.dias_restantes < 0:
            return f"Venció hace {-self.dias_restantes} días", False
        texto = f"Vence en {self.dias_restantes} días"
        if not self.valido:
            texto += f" · No válido: {self.motivo}"
        return texto[:255], self.valido


def _name(partes) -> str | None:  # propio
    """(( ('commonName', 'x'), ), ...) -> 'x' (CN, o la organización)."""
    datos = {k: v for grupo in partes or () for k, v in grupo}
    return datos.get("commonName") or datos.get("organizationName")


def _iso(texto: str | None) -> str | None:  # propio
    if not texto:
        return None
    return datetime.fromtimestamp(ssl.cert_time_to_seconds(texto), timezone.utc).isoformat()


def _decode_der(der: bytes) -> dict:  # propio
    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as f:
        f.write(ssl.DER_cert_to_PEM_cert(der))
        ruta = f.name
    try:
        return ssl._ssl._test_decode_cert(ruta)
    finally:
        os.unlink(ruta)


def _fill(r: CertResultado, cert: dict):  # propio
    r.para = _name(cert.get("subject"))
    r.emisor = _name(cert.get("issuer"))
    r.nombres = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"]
    r.desde, r.hasta = _iso(cert.get("notBefore")), _iso(cert.get("notAfter"))
    if cert.get("notAfter"):
        segundos = ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()
        r.dias_restantes = int(segundos // 86400)


def _check(host: str, puerto: int, timeout: float) -> CertResultado:  # propio
    r = CertResultado(host=host, puerto=puerto)
    inicio = time.perf_counter()
    try:
        contexto = ssl.create_default_context()
        try:
            with socket.create_connection((host, puerto), timeout) as s, \
                    contexto.wrap_socket(s, server_hostname=host) as tls:
                r.valido, r.tls = True, tls.version()
                _fill(r, tls.getpeercert())
        except ssl.SSLCertVerificationError as ex:
            r.motivo = _reason(ex)
            sin_verificar = ssl.create_default_context()
            sin_verificar.check_hostname = False
            sin_verificar.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, puerto), timeout) as s, \
                    sin_verificar.wrap_socket(s, server_hostname=host) as tls:
                r.tls = tls.version()
                der = tls.getpeercert(binary_form=True)
            try:
                _fill(r, _decode_der(der))
            except (AttributeError, ssl.SSLError, OSError):
                pass  # sin detalle: queda el motivo
    except socket.timeout:
        r.error = f"No contestó a tiempo ({host}:{puerto})"
    except ConnectionRefusedError:
        r.error = f"El puerto {puerto} está cerrado en {host}"
    except ssl.SSLError as ex:
        r.error = f"No habla HTTPS en el puerto {puerto}: {ex.reason or ex}"
    except socket.gaierror:
        r.error = f"No se encontró «{host}»"
    except OSError as ex:
        r.error = f"Error de red: {ex}"
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    return r


def _reason(ex: ssl.SSLCertVerificationError) -> str:  # propio
    texto = (ex.verify_message or str(ex)).lower()
    if "expired" in texto:
        return "está vencido"
    if "self-signed" in texto or "self signed" in texto:
        return "es autofirmado (no lo firmó una autoridad)"
    if "hostname mismatch" in texto or "doesn't match" in texto or "not valid for" in texto:
        return "es de otro dominio"
    if "unable to get local issuer" in texto:
        return "falta la cadena de la autoridad que lo firmó"
    return ex.verify_message or str(ex)


async def check(objetivo: str, puerto: int = 443, timeout: float = 8.0) -> CertResultado:  # propio
    try:
        host = clean_host(objetivo)
    except ValueError as ex:
        return CertResultado(host=objetivo, error=str(ex))
    if ":" in objetivo.split("//")[-1].split("/")[0] and objetivo.count(":") <= 2:
        try:  # ejemplo.com:8443 -> ese puerto
            puerto = int(objetivo.split("//")[-1].split("/")[0].rsplit(":", 1)[1])
        except ValueError:
            pass
    return await asyncio.to_thread(_check, host, puerto, timeout)

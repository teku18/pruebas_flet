"""
Túneles públicos por SSH: lo mismo que escribir `ngrok http 8069` en la
terminal de tu PC, pero lo hace la app.

  start()    arranca ngrok / cloudflared EN EL EQUIPO (en segundo plano: sigue
             aunque cierres la app) y espera a que diga su URL https://…
  status()   ¿sigue vivo? y su URL
  stop()     lo cierra
  install()  si el equipo no tiene ngrok / cloudflared, lo baja a
             ~/.controlkraken/bin (sin sudo)

ngrok necesita tu authtoken: si el equipo ya lo tiene configurado (como tu PC)
se usa ese; si no, se le pone el que guardaste en la app. Cloudflare no pide
cuenta, pero su URL cambia cada vez que arranca.

Todo es bloqueante (SSH): las pantallas lo llaman con asyncio.to_thread.
"""
import re
import shlex
import time
from dataclasses import dataclass

from modulos.kraken.models import Ajustes, TunelPublico
from modulos.kraken.ssh.conexion import Sesion

# ¿sigue vivo ese pid? (un proceso muerto sin recoger, "zombi", no cuenta)
VIVO = ('vivo() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null && '
        '[ "$(cut -d" " -f3 /proc/"$1"/stat 2>/dev/null || echo R)" != Z ]; }; ')

BIN = ".controlkraken/bin"
ESPERA_URL_S = 20
NGROK_DESCARGA = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-{arch}.tgz"
CLOUDFLARE_DESCARGA = ("https://github.com/cloudflare/cloudflared/releases/latest/download/"
                       "cloudflared-linux-{arch}")
TOKEN_AYUDA = "https://dashboard.ngrok.com/get-started/your-authtoken"

URL_NGROK = re.compile(r'url[=":\s]+"?(https?://[^\s"]+)')
URL_CLOUDFLARE = re.compile(r"(https://[a-z0-9-]+\.trycloudflare\.com)")
ERRORES_NGROK = {
    "ERR_NGROK_108": "Tu cuenta de ngrok ya tiene el máximo de túneles abiertos a la vez "
                     "(la gratis: uno). Cierra el otro o usa Cloudflare.",
    "ERR_NGROK_4018": "ngrok necesita tu authtoken.",
    "ERR_NGROK_105": "El authtoken de ngrok no es válido: cópialo de nuevo de tu cuenta.",
    "ERR_NGROK_107": "El authtoken de ngrok no es válido: cópialo de nuevo de tu cuenta.",
    "ERR_NGROK_313": "Ese dominio fijo no es de tu cuenta de ngrok (revísalo en su panel).",
    "ERR_NGROK_15013": "Ese dominio fijo no es de tu cuenta de ngrok (revísalo en su panel).",
    "ERR_NGROK_334": "Ese dominio ya está abierto en otro túnel de ngrok.",
}


class FaltaToken(Exception):
    """ngrok no tiene authtoken en el equipo ni en la app: hay que pedirlo."""


class FaltaPrograma(Exception):
    """El equipo no tiene ngrok / cloudflared (se puede instalar)."""

    def __init__(self, servicio: str):
        super().__init__(servicio)
        self.servicio = servicio


@dataclass
class Estado:
    activo: bool
    url: str | None = None
    error: str | None = None

    @property
    def texto(self) -> str:  # propio
        return "Abierto" if self.activo else "Cerrado"


def arch(uname: str) -> str:  # propio
    """`uname -m` -> el nombre que usan las descargas de ngrok y cloudflared."""
    u = uname.strip().lower()
    if u in ("x86_64", "amd64"):
        return "amd64"
    if u in ("aarch64", "arm64", "armv8l"):
        return "arm64"
    if u.startswith("armv7") or u == "armhf":
        return "arm"
    if u in ("i386", "i686", "386"):
        return "386"
    raise ValueError(f"No sé qué versión bajar para este procesador ({uname.strip()})")


def parse_log(texto: str, servicio: str) -> tuple[str | None, str | None]:  # propio
    """(url, error) de lo que escribió ngrok / cloudflared."""
    if servicio == "cloudflare":
        m = URL_CLOUDFLARE.search(texto)
        if m:
            return m.group(1), None
        for renglon in reversed(texto.splitlines()):
            if " ERR " in renglon or "failed" in renglon.lower():
                return None, renglon.strip()[-300:]
        return None, None
    for codigo, mensaje in ERRORES_NGROK.items():
        if codigo in texto:
            return None, mensaje
    if "unknown flag" in texto and "--url" in texto:
        return None, "Tu ngrok es viejo y no conoce --url: actualízalo con  ngrok update"
    for renglon in texto.splitlines():
        if "started tunnel" in renglon or '"url"' in renglon or " url=" in renglon:
            m = URL_NGROK.search(renglon)
            if m and "localhost" not in m.group(1) and "127.0.0.1" not in m.group(1):
                return m.group(1), None
    for renglon in reversed(texto.splitlines()):
        if "lvl=eror" in renglon or '"lvl":"eror"' in renglon or "ERROR" in renglon:
            return None, renglon.strip()[-300:]
    return None, None


# ============================================================================
# El programa en el equipo
# ============================================================================
def _program(sesion: Sesion, servicio: str) -> str | None:  # propio
    nombre = "ngrok" if servicio == "ngrok" else "cloudflared"
    s = sesion.run(f'command -v {nombre} || {{ [ -x "$HOME/{BIN}/{nombre}" ] && '
                   f'echo "$HOME/{BIN}/{nombre}"; }}', timeout=15)
    ruta = s.texto.strip().splitlines()[-1].strip() if s.texto.strip() else ""
    return ruta or None


def install(sesion: Sesion, servicio: str) -> str:  # propio
    """Baja ngrok / cloudflared a ~/.controlkraken/bin. Devuelve su ruta."""
    a = arch(sesion.run("uname -m", timeout=15).texto)
    bajar = ('if command -v curl >/dev/null; then curl -fsSL -o "$1" "$2"; '
             'elif command -v wget >/dev/null; then wget -q -O "$1" "$2"; '
             'else echo "SIN_DESCARGADOR"; exit 9; fi')
    d = f'"$HOME"/{BIN}'
    if servicio == "ngrok":
        url = NGROK_DESCARGA.format(arch=a)
        cmd = (f"mkdir -p {d} && cd {d} && bajar() {{ {bajar}; }} && "
               f"bajar ngrok.tgz {shlex.quote(url)} && tar -xzf ngrok.tgz ngrok && "
               "rm -f ngrok.tgz && chmod +x ngrok && ./ngrok version")
    else:
        url = CLOUDFLARE_DESCARGA.format(arch=a)
        cmd = (f"mkdir -p {d} && cd {d} && bajar() {{ {bajar}; }} && "
               f"bajar cloudflared {shlex.quote(url)} && chmod +x cloudflared && "
               "./cloudflared --version")
    s = sesion.run(cmd, timeout=180)
    if "SIN_DESCARGADOR" in s.texto:
        raise ValueError("El equipo no tiene curl ni wget para bajarlo")
    if not s.ok:
        raise ValueError("No se pudo bajar: " + (s.errores or s.texto).strip()[-300:])
    return _program(sesion, servicio) or ""


def _ngrok_token(sesion: Sesion, ngrok: str) -> None:  # propio
    """Que ngrok tenga authtoken: el del equipo, o el que guardaste en la app."""
    s = sesion.run(f"{shlex.quote(ngrok)} config check 2>&1", timeout=20)
    m = re.search(r"(/\S+\.yml)", s.texto)
    if m and "TIENE" in sesion.run(f"grep -qs authtoken {shlex.quote(m.group(1))} && "
                                   "echo TIENE || echo NO", timeout=15).texto:
        return
    token = (Ajustes.current().ngrok_token or "").strip()
    if not token:
        raise FaltaToken()
    s = sesion.run(f"{shlex.quote(ngrok)} config add-authtoken {shlex.quote(token)} 2>&1",
                   timeout=20)
    if not s.ok:
        raise ValueError("ngrok no aceptó el authtoken: " + s.texto.strip()[-200:])


# ============================================================================
# Abrir / cerrar
# ============================================================================
def _dir(t: TunelPublico) -> str:  # propio
    return f'"$HOME"/{shlex.quote(t.carpeta)}'


def start(sesion: Sesion, t: TunelPublico) -> Estado:  # propio
    actual = status(sesion, t)
    if actual.activo and actual.url:
        return actual
    programa = _program(sesion, t.servicio)
    if not programa:
        raise FaltaPrograma(t.servicio)
    if t.servicio == "ngrok":
        _ngrok_token(sesion, programa)
        extra = f" --url {shlex.quote('https://' + t.dominio)}" if t.dominio else ""
        orden = (f"{shlex.quote(programa)} http {int(t.puerto)} --log stdout "
                 f"--log-format logfmt{extra}")
    else:
        orden = (f"{shlex.quote(programa)} tunnel --no-autoupdate "
                 f"--url http://localhost:{int(t.puerto)}")
    d = _dir(t)
    s = sesion.run(f"mkdir -p {d} && cd {d} && rm -f tunel.log tunel.pid && "
                   f"(setsid nohup {orden} </dev/null >tunel.log 2>&1 & echo $! > tunel.pid)",
                   timeout=20)
    if not s.ok:
        raise ValueError("No se pudo arrancar: " + s.errores.strip()[-300:])
    limite = time.monotonic() + ESPERA_URL_S
    while time.monotonic() < limite:
        time.sleep(1)
        estado = status(sesion, t)
        if estado.url or estado.error or not estado.activo:
            break
    if estado.error or not estado.activo:
        stop(sesion, t)
        raise ValueError(estado.error or "El túnel se cerró al arrancar (revisa tunel.log)")
    if not estado.url:
        raise ValueError("El túnel arrancó pero no dio su URL todavía: toca Actualizar")
    TunelPublico.update(t.id, url=estado.url)
    t.url = estado.url
    return estado


def status(sesion: Sesion, t: TunelPublico) -> Estado:  # propio
    d = _dir(t)
    s = sesion.run(VIVO + f"cd {d} 2>/dev/null || {{ echo CERRADO; exit 0; }}; "
                   'if [ -f tunel.pid ] && vivo "$(cat tunel.pid)"; '
                   "then echo ABIERTO; else echo CERRADO; fi; tail -c 20000 tunel.log 2>/dev/null",
                   timeout=15)
    primera, _, log = s.texto.partition("\n")
    url, error = parse_log(log, t.servicio)
    return Estado(primera.strip() == "ABIERTO", url, error)


def stop(sesion: Sesion, t: TunelPublico) -> Estado:  # propio
    sesion.run(f'cd {_dir(t)} 2>/dev/null && [ -f tunel.pid ] && kill "$(cat tunel.pid)" '
               "2>/dev/null; sleep 0.5; true", timeout=15)
    return Estado(False, None, None)


def remove(sesion: Sesion | None, t: TunelPublico) -> None:  # propio
    """Lo cierra (si se puede) y lo borra de la app."""
    if sesion is not None:
        stop(sesion, t)
        sesion.run(f"rm -rf {_dir(t)}", timeout=15)
    TunelPublico.delete(t.id)

"""
Webhooks: instalar, iniciar, detener y leer el receptor de tu servidor (por SSH).

Todo aquí es bloqueante (SSH): las pantallas lo llaman con asyncio.to_thread.

  install()    sube receptor.py + config.json, lo inicia y lo deja en
               `crontab @reboot` (vuelve solo si el servidor se reinicia)
  status()     ¿está escuchando?  -> Estado
  start/stop   iniciar / detener
  apply()      reescribe config.json (qué responde, cuántos guarda) y reinicia
  fetch()      trae lo nuevo a la BD de la app (solo lo que no tenía)
  uninstall()  lo detiene y borra su carpeta y su renglón de crontab
  open_port()  `sudo ufw allow <puerto>/tcp` si el servidor usa ufw
  test_send()  manda un webhook de prueba DESDE EL CEL (¿se alcanza de fuera?)
"""
import base64
import json
import shlex
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import delete, select

from core.database import SessionLocal
from modulos.kraken.models import Equipo, Receptor, TunelPublico, WebhookRecibido
from modulos.kraken.ssh.conexion import Sesion
from modulos.kraken.webhooks.receptor import LEER, SCRIPT

# ¿sigue vivo ese pid? (un proceso muerto sin recoger, "zombi", no cuenta)
VIVO = ('vivo() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null && '
        '[ "$(cut -d" " -f3 /proc/"$1"/stat 2>/dev/null || echo R)" != Z ]; }; ')

LOTE = 300     # cuántos se piden por vuelta al leer
VENTANA = 100  # con reenvío: se vuelve a mirar los últimos 100 (sus respuestas llegan después)


@dataclass
class Estado:
    instalado: bool
    activo: bool
    detalle: str = ""          # últimas líneas del log si algo falló

    @property
    def texto(self) -> str:  # propio
        if not self.instalado:
            return "No instalado"
        return "Escuchando" if self.activo else "Detenido"


def _dir(r: Receptor) -> str:  # propio
    return f'"$HOME"/{shlex.quote(r.carpeta)}'


def _tag(r: Receptor) -> str:  # propio
    return f"ck-webhook-{r.clave}"


def _config(r: Receptor) -> dict:  # propio
    return {"puerto": r.puerto, "clave": r.clave, "status": r.status,
            "cuerpo": r.respuesta or "", "max": max(r.max_guardados * 2, 200),
            "reenviar": [u for u in (r.reenviar or []) if u.strip()],
            "tipo": "application/json" if (r.respuesta or "").lstrip()[:1] in "{[" else
            "text/plain; charset=utf-8"}


def _write(ruta: str, contenido: str) -> str:  # propio
    """Comando que escribe un archivo (en base64: sin problemas de comillas)."""
    datos = base64.b64encode(contenido.encode("utf-8")).decode("ascii")
    return f"printf %s {datos} | base64 -d > {ruta}"


def friendly_log(texto: str, r: Receptor) -> str:  # propio
    bajo = texto.lower()
    if "address already in use" in bajo:
        return f"El puerto {r.puerto} ya está ocupado en el servidor: elige otro."
    if "permission denied" in bajo:
        return f"Sin permiso para usar el puerto {r.puerto}: usa uno mayor a 1024."
    return texto.strip()[-400:]


# ============================================================================
# En el servidor
# ============================================================================
def install(sesion: Sesion, r: Receptor) -> Estado:  # propio
    d = _dir(r)
    salida = sesion.run("command -v python3 >/dev/null && echo SI || echo NO", timeout=15)
    if "SI" not in salida.texto:
        raise ValueError("El servidor no tiene python3 (en Ubuntu/Debian: sudo apt install "
                         "python3)")
    pasos = [f"mkdir -p {d}", f"chmod 700 {d}",
             _write(f"{d}/receptor.py", SCRIPT),
             _write(f"{d}/config.json", json.dumps(_config(r), ensure_ascii=False))]
    s = sesion.run(" && ".join(pasos), timeout=30)
    if not s.ok:
        raise ValueError(f"No se pudo copiar el receptor: {s.errores.strip()[:300]}")
    _cron(sesion, r, agregar=True)
    estado = start(sesion, r)
    Receptor.update(r.id, instalado=True)
    return estado


def _cron(sesion: Sesion, r: Receptor, agregar: bool) -> bool:  # propio
    """Agrega (o quita) el renglón @reboot. False si el servidor no tiene crontab."""
    if "SI" not in sesion.run("command -v crontab >/dev/null && echo SI || echo NO").texto:
        return False
    tag = _tag(r)
    linea = f'@reboot cd "$HOME"/{r.carpeta} && python3 receptor.py >> receptor.log 2>&1 # {tag}'
    nuevo = f"; echo {shlex.quote(linea)}" if agregar else ""
    sesion.run(f"(crontab -l 2>/dev/null | grep -v {shlex.quote(tag)}{nuevo}) | crontab -",
               timeout=15)
    return True


def status(sesion: Sesion, r: Receptor) -> Estado:  # propio
    d = _dir(r)
    s = sesion.run(
        VIVO + f"cd {d} 2>/dev/null || {{ echo NOINSTALADO; exit 0; }}; "
        "if [ -f receptor.pid ] && vivo \"$(cat receptor.pid)\"; "
        "then echo ACTIVO; else echo DETENIDO; tail -n 5 receptor.log 2>/dev/null; fi",
        timeout=15)
    primera, _, resto = s.texto.partition("\n")
    if primera.strip() == "NOINSTALADO":
        return Estado(False, False)
    return Estado(True, primera.strip() == "ACTIVO", "" if primera.strip() == "ACTIVO"
                  else friendly_log(resto, r))


def start(sesion: Sesion, r: Receptor) -> Estado:  # propio
    d = _dir(r)
    sesion.run(
        VIVO + f"cd {d} && if [ -f receptor.pid ] && vivo \"$(cat receptor.pid)\"; "
        "then :; else rm -f receptor.pid; "
        "(setsid nohup python3 receptor.py </dev/null >>receptor.log 2>&1 &) ; sleep 1.2; fi",
        timeout=20)
    estado = status(sesion, r)
    if estado.instalado and not estado.activo:
        raise ValueError(estado.detalle or "El receptor no arrancó (revisa receptor.log)")
    return estado


def stop(sesion: Sesion, r: Receptor) -> Estado:  # propio
    d = _dir(r)
    sesion.run(f"cd {d} 2>/dev/null && [ -f receptor.pid ] && kill \"$(cat receptor.pid)\" "
               "2>/dev/null; rm -f receptor.pid 2>/dev/null; sleep 0.3; true", timeout=15)
    return status(sesion, r)


def apply(sesion: Sesion, r: Receptor) -> Estado:  # propio
    """Después de editar: config nueva (y el script por si cambió de versión) y reinicia."""
    d = _dir(r)
    s = sesion.run(" && ".join([_write(f"{d}/receptor.py", SCRIPT),
                                _write(f"{d}/config.json", json.dumps(_config(r)))]))
    if not s.ok:
        raise ValueError(f"No se pudo actualizar: {s.errores.strip()[:300]}")
    stop(sesion, r)
    return start(sesion, r)


def uninstall(sesion: Sesion, r: Receptor) -> None:  # propio
    stop(sesion, r)
    _cron(sesion, r, agregar=False)
    sesion.run(f"rm -rf {_dir(r)}", timeout=15)
    Receptor.update(r.id, instalado=False)


def open_port(sesion: Sesion, r: Receptor) -> str:  # propio
    s = sesion.run("sudo ufw status 2>/dev/null | head -1", timeout=20)
    if "inactive" in s.texto.lower() or not s.texto.strip():
        return ("Este servidor no usa ufw (o no está activo). Si no llega nada, revisa el "
                "firewall de tu proveedor (AWS, DigitalOcean, Azure…).")
    s = sesion.run(f"sudo ufw allow {int(r.puerto)}/tcp", timeout=20)
    if not s.ok:
        return f"No se pudo: {(s.errores or s.texto).strip()[:300]}"
    return f"Listo: ufw permite el puerto {r.puerto}."


# ============================================================================
# Traer lo recibido
# ============================================================================
def _local_time(texto: str) -> datetime:  # propio
    try:
        return datetime.fromisoformat(texto).astimezone().replace(tzinfo=None)
    except (TypeError, ValueError):
        return datetime.now()


def fetch(sesion: Sesion, r: Receptor) -> int:  # propio
    """
    Trae lo nuevo a la BD. Devuelve cuántos webhooks llegaron.

    Con reenvío, lo que contestó cada destino llega DESPUÉS en un renglón
    "actualiza" con el id del webhook; por eso se pide desde un poco antes
    del último (VENTANA) y se juntan, sin repetir los que ya estaban.
    """
    archivo = f'"$HOME"/{shlex.quote(r.carpeta)}/recibidos.jsonl'
    desde = max(0, r.ultimo_id - (VENTANA if r.reenviar else 0))
    ultimo, total = r.ultimo_id, 0
    for _ in range(10):          # hasta 3,000 de una vez
        s = sesion.run(f"python3 -c {shlex.quote(LEER)} {int(desde)} {LOTE} {archivo}",
                       timeout=30, max_bytes=20_000_000)
        renglones = []
        for renglon in s.texto.splitlines():
            try:
                renglones.append(json.loads(renglon))
            except ValueError:
                continue
        if not renglones:
            break
        with SessionLocal() as session:
            ids = {d["id"] for d in renglones if "id" in d}
            existentes = {w.remoto_id: w for w in session.scalars(select(WebhookRecibido).where(
                WebhookRecibido.receptor_id == r.id, WebhookRecibido.remoto_id.in_(ids)))}
            for d in renglones:
                numero = int(d.get("id", 0))
                if d.get("actualiza"):
                    if numero in existentes:
                        existentes[numero].reenvios = d.get("reenvios") or []
                    continue
                if numero in existentes:
                    continue
                w = WebhookRecibido(
                    receptor_id=r.id, remoto_id=numero, recibido_en=_local_time(d.get("fecha")),
                    metodo=str(d.get("metodo", "?"))[:10], ruta=d.get("ruta") or "/",
                    query=d.get("query") or None, headers=d.get("headers") or [],
                    body=d.get("body") or None, es_base64=bool(d.get("base64")),
                    tamano=int(d.get("tamano") or 0), ip=(d.get("ip") or "")[:64] or None,
                    reenvios=d.get("reenvios"))
                session.add(w)
                existentes[numero] = w
                ultimo = max(ultimo, numero)
                total += 1
            session.commit()
        desde = max(d.get("id", 0) for d in renglones)
        if len(renglones) < LOTE:
            break
    if ultimo != r.ultimo_id:
        Receptor.update(r.id, ultimo_id=ultimo)
        r.ultimo_id = ultimo
    prune(r)
    return total


def prune(r: Receptor) -> int:  # propio
    """Deja solo los últimos `max_guardados` en la app."""
    with SessionLocal() as session:
        sobran = list(session.scalars(
            select(WebhookRecibido.id).where(WebhookRecibido.receptor_id == r.id)
            .order_by(WebhookRecibido.remoto_id.desc()).offset(r.max_guardados)))
        if sobran:
            session.execute(delete(WebhookRecibido).where(WebhookRecibido.id.in_(sobran)))
            session.commit()
        return len(sobran)


def mark_seen(r: Receptor) -> None:  # propio
    with SessionLocal() as session:
        session.execute(WebhookRecibido.__table__.update().where(
            WebhookRecibido.receptor_id == r.id).values(visto=True))
        session.commit()


def clear(r: Receptor) -> None:  # propio
    """Borra lo recibido EN LA APP (el servidor conserva su archivo rotativo)."""
    with SessionLocal() as session:
        session.execute(delete(WebhookRecibido).where(WebhookRecibido.receptor_id == r.id))
        session.commit()


# ============================================================================
# Desde el celular
# ============================================================================
def public_url(r: Receptor) -> str | None:  # propio
    """La URL que se pega en el proveedor: la del túnel https si hay, si no IP:puerto."""
    t = TunelPublico.of_receiver(r.id)
    if t is not None and t.url:
        return f"{t.url.rstrip('/')}/{r.clave}"
    host = host_of(r)
    return r.url(host) if host else None


def test_send(r: Receptor, destino: str) -> tuple[bool, str]:  # propio
    """Manda un webhook de prueba a la URL pública (como lo haría Stripe, GitHub…).
    `destino`: la URL pública completa, o solo el host (URL directa)."""
    host = destino.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    url = (destino if destino.startswith("http") else r.url(destino)) + "/prueba"
    try:
        resp = httpx.post(url, json={"evento": "prueba", "desde": "ControlKraken",
                                     "hora": datetime.now().isoformat(timespec="seconds")},
                          timeout=10)
    except httpx.ConnectTimeout:
        return False, (f"No se alcanza {host}:{r.puerto} desde aquí: el firewall lo bloquea. "
                       "Toca «Abrir puerto» (ufw), ábrelo en tu proveedor o usa un túnel.")
    except httpx.ConnectError:
        return False, (f"{host}:{r.puerto} rechaza la conexión: ¿el receptor está detenido? "
                       "(o el puerto está cerrado)")
    except httpx.HTTPError as ex:
        return False, f"No se pudo: {ex}"
    if resp.status_code == r.status:
        return True, f"Llegó: el receptor respondió {resp.status_code}."
    if resp.status_code in (502, 503, 504) or "ngrok" in resp.text[:2000].lower():
        return False, (f"El túnel respondió {resp.status_code}: está abierto pero el receptor "
                       "no contesta (¿detenido?).")
    return False, f"Respondió {resp.status_code}: ¿es otro programa el que usa ese puerto?"


def host_of(r: Receptor) -> str | None:  # propio
    e = Equipo.get(r.equipo_id) if r.equipo_id else None
    return e.host if e else None


# ============================================================================
# Para mostrar / reenviar
# ============================================================================
def body_text(w: WebhookRecibido) -> str:  # propio
    if not w.body:
        return ""
    if w.es_base64:
        return f"(binario, {w.tamano:,} bytes en base64)\n{w.body[:2000]}"
    return w.body


def content_type(w: WebhookRecibido) -> str:  # propio
    return next((v for k, v in w.headers or [] if k.lower() == "content-type"), "")


SALTAR = {"host", "content-length", "connection", "accept-encoding", "x-forwarded-for",
          "x-real-ip", "transfer-encoding"}


def to_draft(w: WebhookRecibido):  # propio
    """El webhook como petición del Cliente HTTP (para reenviarlo a otro lado)."""
    from urllib.parse import parse_qsl

    from modulos.kraken.http.services import Borrador, kv, pretty

    tipo = content_type(w).lower()
    b = Borrador(metodo=w.metodo if w.metodo in ("GET", "POST", "PUT", "PATCH", "DELETE")
                 else "POST", url="",
                 params=[kv(k, v) for k, v in parse_qsl(w.query or "", keep_blank_values=True)],
                 headers=[kv(k, v) for k, v in w.headers or [] if k.lower() not in SALTAR])
    if w.body and not w.es_base64:
        if "json" in tipo:
            b.body_tipo, b.body = "json", pretty(w.body)
        elif "x-www-form-urlencoded" in tipo:
            b.body_tipo = "form"
            b.form = [kv(k, v) for k, v in parse_qsl(w.body, keep_blank_values=True)]
            b.headers = [h for h in b.headers if h["clave"].lower() != "content-type"]
        else:
            b.body_tipo, b.body = "texto", w.body
    return b

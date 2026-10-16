"""
El receptor que vive EN TU SERVIDOR (lo sube la app por SSH).

Es un solo archivo de Python sin dependencias (solo la librería estándar), para
que corra en cualquier Linux con python3. Se guarda en
~/.controlkraken/webhooks/<clave>/receptor.py junto a:

  config.json      puerto, clave, qué responder, cuántos guardar
  recibidos.jsonl  un renglón JSON por webhook (id, fecha, método, headers, body…)
  receptor.pid     el proceso que está escuchando
  receptor.log     errores (p. ej. "puerto ocupado")

Solo guarda lo que llega a /<clave> (o /<clave>/algo): lo demás responde 404 y
no se anota, así los robots que escanean internet no llenan tu lista.

Reenviar (config "reenviar": [urls]): PRIMERO contesta al que mandó (Stripe no
espera), y luego en otro hilo manda lo mismo a cada URL. Lo que contestó cada
destino se anota en un renglón aparte {"id": <el mismo>, "actualiza": true,
"reenvios": […]}, que la app junta con el webhook.

La app NO necesita estar abierta: el receptor guarda todo y la app lo lee
(por SSH) cuando abres la pantalla. Qué es / dónde: notas técnicas, nota 54.
"""

SCRIPT = r'''#!/usr/bin/env python3
# Receptor de webhooks de ControlKraken. Lo instaló la app; se puede borrar desde ella.
import base64, json, os, sys, threading, time
import urllib.error, urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DIR = os.path.dirname(os.path.abspath(__file__))
CONF = json.load(open(os.path.join(DIR, "config.json")))
ARCHIVO = os.path.join(DIR, "recibidos.jsonl")
MAX_BODY = 1024 * 1024
CANDADO = threading.Lock()


def ultimo_id():
    try:
        with open(ARCHIVO, "rb") as f:
            f.seek(0, 2)
            inicio = max(0, f.tell() - 65536)
            f.seek(inicio)
            renglones = f.read().decode("utf-8", "replace").strip().splitlines()
        ids = []
        for renglon in renglones[1:] if inicio else renglones:   # el 1º puede venir cortado
            try:
                ids.append(json.loads(renglon)["id"])
            except (ValueError, KeyError):
                pass
        return max(ids) if ids else 0
    except (OSError, ValueError, KeyError, IndexError):
        return 0


SIGUIENTE = [ultimo_id() + 1]


SALTAR = {"host", "content-length", "connection", "transfer-encoding", "accept-encoding"}


def anotar(registro):
    with CANDADO:
        with open(ARCHIVO, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def reenviar(numero, metodo, headers, datos, query):
    resultados = []
    for url in CONF.get("reenviar") or []:
        destino = url + (("&" if "?" in url else "?") + query if query else "")
        cabeceras = {k: v for k, v in headers if k.lower() not in SALTAR}
        cabeceras["X-Kraken-Reenvio"] = "1"
        inicio = time.time()
        r = {"url": url}
        try:
            peticion = urllib.request.Request(destino, data=datos if datos else None,
                                              headers=cabeceras, method=metodo)
            with urllib.request.urlopen(peticion, timeout=15) as resp:
                r["status"] = resp.status
                r["respuesta"] = resp.read(4000).decode("utf-8", "replace")
        except urllib.error.HTTPError as ex:
            r["status"] = ex.code
            r["respuesta"] = ex.read(4000).decode("utf-8", "replace")
        except Exception as ex:
            r["error"] = (type(ex).__name__ + ": " + str(getattr(ex, "reason", ex)))[:300]
        r["ms"] = round((time.time() - inicio) * 1000)
        resultados.append(r)
    anotar({"id": numero, "actualiza": True, "reenvios": resultados})


def podar():
    maximo = int(CONF.get("max", 1000))
    with open(ARCHIVO, encoding="utf-8") as f:
        renglones = f.readlines()
    if len(renglones) > maximo * 2:
        with open(ARCHIVO + ".tmp", "w", encoding="utf-8") as f:
            f.writelines(renglones[-maximo:])
        os.replace(ARCHIVO + ".tmp", ARCHIVO)


class Receptor(BaseHTTPRequestHandler):
    server_version = "ControlKraken"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _leer_cuerpo(self):
        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            datos = b""
            while len(datos) <= MAX_BODY:
                linea = self.rfile.readline().strip()
                tamano = int(linea.split(b";")[0] or b"0", 16)
                if tamano == 0:
                    self.rfile.readline()
                    break
                datos += self.rfile.read(tamano)
                self.rfile.readline()
            return datos
        largo = int(self.headers.get("Content-Length") or 0)
        datos = self.rfile.read(min(largo, MAX_BODY))
        if largo > MAX_BODY:
            self.rfile.read(largo - MAX_BODY)
        return datos

    def _atender(self):
        ruta, _, query = self.path.partition("?")
        clave = "/" + CONF["clave"]
        if ruta != clave and not ruta.startswith(clave + "/"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        try:
            datos = self._leer_cuerpo()
        except (ValueError, OSError):
            datos = b""
        try:
            cuerpo, b64 = datos.decode("utf-8"), False
        except UnicodeDecodeError:
            cuerpo, b64 = base64.b64encode(datos).decode("ascii"), True
        ip = self.headers.get("X-Forwarded-For", "").split(",")[0].strip() or self.client_address[0]
        destinos = CONF.get("reenviar") or []
        with CANDADO:
            registro = {"id": SIGUIENTE[0],
                        "fecha": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                        "metodo": self.command, "ruta": ruta[len(clave):] or "/",
                        "query": query, "headers": [[k, v] for k, v in self.headers.items()],
                        "body": cuerpo, "base64": b64, "tamano": len(datos), "ip": ip}
            if destinos:
                registro["reenvios"] = "pendiente"
            SIGUIENTE[0] += 1
            with open(ARCHIVO, "a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            if registro["id"] % 100 == 0:
                podar()
        respuesta = CONF.get("cuerpo", "").encode("utf-8")
        self.send_response(int(CONF.get("status", 200)))
        self.send_header("Content-Type", CONF.get("tipo", "application/json"))
        self.send_header("Content-Length", str(len(respuesta)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(respuesta)
        if destinos and self.headers.get("X-Kraken-Reenvio") != "1":   # sin bucles
            threading.Thread(target=reenviar, daemon=True, args=(
                registro["id"], self.command, list(self.headers.items()), datos,
                query)).start()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _atender


def principal():
    servidor = ThreadingHTTPServer(("0.0.0.0", int(CONF["puerto"])), Receptor)
    servidor.daemon_threads = True
    with open(os.path.join(DIR, "receptor.pid"), "w") as f:
        f.write(str(os.getpid()))
    print(time.strftime("%F %T"), "escuchando en", CONF["puerto"], flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    principal()
'''

# Lee lo nuevo: los renglones con id mayor al último que ya tiene la app.
LEER = r'''
import json, sys
desde, limite, archivo = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
salida = []
try:
    with open(archivo, encoding="utf-8") as f:
        for renglon in f:
            try:
                if json.loads(renglon)["id"] > desde:
                    salida.append(renglon.rstrip("\n"))
            except (ValueError, KeyError):
                pass
except FileNotFoundError:
    pass
print("\n".join(salida[-limite:]))
'''

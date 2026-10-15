"""
Prueba Kraken Tools sin celular ni internet:

    python scripts/verificar_kraken.py

Trabaja en una carpeta temporal (CK_DATA_ROOT): NUNCA toca tu BD real.

  HTTP     levanta un servidor local (http.server en un hilo) con rutas de
           prueba: /eco (regresa lo que le mandas), /404, /lento, /grande,
           /imagen. Revisa variables {{}}, params, body JSON/form, auth,
           errores, tiempo de espera, historial (recorte y tamaño), cURL.
  SQLite   crea una base de prueba, la agrega como conexión, lee tablas,
           esquema, datos con paginación, ejecuta SQL, solo lectura y CSV.
  Respaldo una base marcada "no respaldar" no entra al zip y NO se borra al
           restaurar; una marcada "respaldar" sí viaja.
  Red      ping (ICMP si el sistema lo deja, y TCP), puertos, DNS contra un
           servidor DNS falso, certificado contra un servidor HTTPS con un
           certificado autofirmado/vencido (hecho con openssl), Whois (RDAP y
           puerto 43 falsos), Mi IP, Wake-on-LAN (se recibe el paquete), dispositivos
           en la red (en 127.0.0.0/29) e historial.
"""
import asyncio
import base64
import json
import os
import sqlite3
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
TMP = Path(tempfile.mkdtemp(prefix="ck_kraken_"))
os.environ["CK_DATA_ROOT"] = str(TMP)

from core import database  # noqa: E402

FALLAS: list[str] = []


def check(condicion: bool, texto: str):  # propio
    print(("  ✓ " if condicion else "  ✗ ") + texto)
    if not condicion:
        FALLAS.append(texto)


# ============================================================================
# Servidor de prueba
# ============================================================================
class Servidor(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencio
        pass

    def _responder(self):  # propio
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo).decode("utf-8") if largo else ""
        if self.path.startswith("/404"):
            self._json(404, {"error": "no existe"})
        elif self.path.startswith("/lento"):
            import time
            time.sleep(3)
            self._json(200, {"ok": True})
        elif self.path.startswith("/grande"):
            self._json(200, {"datos": "x" * 300_000})
        elif self.path.startswith("/rdap/domain/registrado.test"):
            self._json(200, {"events": [
                {"eventAction": "registration", "eventDate": "2015-03-01T00:00:00Z"},
                {"eventAction": "expiration", "eventDate": "2030-03-01T00:00:00Z"}],
                "entities": [{"roles": ["registrar"], "vcardArray": [
                    "vcard", [["version", {}, "text", "4.0"], ["fn", {}, "text", "Registrador X"]]]}],
                "nameservers": [{"ldhName": "NS1.EJEMPLO.TEST"}],
                "status": ["client transfer prohibited"]})
        elif self.path.startswith("/rdap/"):
            self._json(404, {"errorCode": 404})
        elif self.path.startswith("/ipinfo"):
            self._json(200, {"ip": "201.141.1.2", "city": "Puebla", "region": "Puebla",
                             "country": "MX", "org": "AS8151 Uninet"})
        elif self.path.startswith("/imagen"):
            datos = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
        else:
            self._json(200, {"metodo": self.command, "ruta": self.path, "cuerpo": cuerpo,
                             "headers": dict(self.headers)})

    def _json(self, codigo, datos):  # propio
        crudo = json.dumps(datos).encode()
        try:
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(crudo)))
            self.end_headers()
            self.wfile.write(crudo)
        except (BrokenPipeError, ConnectionResetError):
            pass  # el cliente ya se fue (p. ej. la prueba de Cancelar)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _responder


def start_server() -> str:  # propio
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"


# ============================================================================
def test_http(base: str):  # propio
    from modulos.kraken.http import services as s
    from modulos.kraken.models import Ajustes, Entorno, HistorialHttp

    print("HTTP")
    glob = Entorno.globals_()
    Entorno.update(glob.id, variables=[s.kv("base", base), s.kv("token", "GLOBAL")])
    local = Entorno.create(nombre="Local", variables=[s.kv("token", "abc123")])
    Ajustes.change(entorno_id=local.id)
    check(s.variables() == {"base": base, "token": "abc123"}, "el entorno pisa a Globales")

    b = s.Borrador(metodo="POST", url="{{base}}/eco", params=[s.kv("q", "hola mundo"),
                                                              s.kv("no", "x", False)],
                   headers=[s.kv("X-Prueba", "{{token}}")], body_tipo="json",
                   body='{"a": 1}', auth_tipo="bearer", auth_usuario="{{token}}")
    check(s.missing_variables(b, s.variables()) == [], "sin variables faltantes")
    check(s.missing_variables(s.Borrador(url="{{nada}}/x"), {}) == ["nada"],
          "detecta {{variables}} sin definir")
    r = asyncio.run(s.send(b))
    eco = json.loads(r.texto)
    check(r.status == 200 and r.error is None, f"POST con JSON: {r.status} en {r.tiempo_ms} ms")
    check(eco["ruta"] == "/eco?q=hola+mundo", f"params activos en la URL ({eco['ruta']})")
    check(eco["cuerpo"] == '{"a": 1}', "body JSON llega igual")
    check(eco["headers"].get("Authorization") == "Bearer abc123", "Bearer con variable")
    check(eco["headers"].get("X-Prueba") == "abc123", "header con variable")
    check(eco["headers"].get("Content-Type") == "application/json", "Content-Type automático")
    check(r.es_json and '\n  "metodo"' in s.pretty(r.texto), "JSON bonito")

    r = asyncio.run(s.send(s.Borrador(metodo="PUT", url=f"{base}/eco", body_tipo="form",
                                      form=[s.kv("a", "1"), s.kv("a", "2"), s.kv("b", "é")],
                                      auth_tipo="basic", auth_usuario="yo", auth_clave="sec:reto")))
    eco = json.loads(r.texto)
    check(eco["cuerpo"] == "a=1&a=2&b=%C3%A9", f"formulario ({eco['cuerpo']})")
    esperado = "Basic " + base64.b64encode(b"yo:sec:reto").decode()
    check(eco["headers"].get("Authorization") == esperado, "usuario y contraseña (Basic)")

    r = asyncio.run(s.send(s.Borrador(url=f"{base}/404")))
    check(r.status == 404 and r.motivo == "Not Found", "404 llega como respuesta, no como error")
    r = asyncio.run(s.send(s.Borrador(url="http://127.0.0.1:1/nada")))
    check(r.status is None and r.error.startswith("No se pudo conectar"), f"sin servidor: {r.error}")
    Ajustes.change(timeout_s=1)
    r = asyncio.run(s.send(s.Borrador(url=f"{base}/lento")))
    check(r.error and "tiempo de espera" in r.error, "tiempo de espera")
    Ajustes.change(timeout_s=30)
    r = asyncio.run(s.send(s.Borrador(url=f"{base}/imagen")))
    check(r.es_binario and r.datos.startswith(b"\x89PNG") and "binario" in r.texto,
          "respuesta binaria (imagen): se guarda como archivo, no como texto")
    r = asyncio.run(s.send(s.Borrador(url="ftp://x")))
    check(r.error and "URL no válida" in r.error, "URL no válida")
    r = asyncio.run(s.send(s.Borrador(url="")))
    check(r.error == "Escribe la URL", "URL vacía")

    # Cancelar
    async def cancelar():  # propio
        tarea = asyncio.create_task(s.send(s.Borrador(url=f"{base}/lento")))
        await asyncio.sleep(0.3)
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            return True
        return False
    antes = len(HistorialHttp.search_all())
    check(asyncio.run(cancelar()) and len(HistorialHttp.search_all()) == antes,
          "Cancelar corta la espera y no ensucia el historial")

    # Historial: recorte y límite
    Ajustes.change(respuesta_max_kb=64)
    r = asyncio.run(s.send(s.Borrador(url=f"{base}/grande")))
    h = HistorialHttp.get(r.historial_id)
    check(len(r.texto) > 300_000 and len(h.resp_body.encode()) == 64 * 1024 and h.recortado,
          "respuesta completa en pantalla, recortada a 64 KB en el historial")
    Ajustes.change(respuesta_max_kb=0)
    r = asyncio.run(s.send(s.Borrador(url=f"{base}/grande")))
    check(not HistorialHttp.get(r.historial_id).recortado, "respuesta 'Completa' no se recorta")
    total = len(HistorialHttp.search_all())
    check(s.prune_history(3) == total - 3 and len(HistorialHttp.search_all()) == 3,
          f"límite del historial ({total} -> 3)")
    check(s.history()[0].id == r.historial_id, "el más nuevo, primero")
    viejo = s.result_from_history(s.history()[0])
    check(viejo.status == 200 and viejo.es_json, "ver de nuevo un envío del historial")

    # Guardar en colección
    col = s.create_collection("Mi API")
    p = s.save_request(None, b, coleccion_id=col.id)
    check(p.nombre == "POST /eco" and p.coleccion_id == col.id, "guardar con nombre sugerido")
    p2 = s.duplicate(p.id)
    check(p2.nombre == "POST /eco (copia)" and s.Borrador.from_request(p2) == b, "duplicar")
    try:
        s.create_collection("mi api")
        check(False, "colección repetida")
    except ValueError:
        check(True, "no deja dos colecciones con el mismo nombre")

    # cURL
    curl = s.to_curl(b)
    check("-H 'Authorization: Bearer abc123'" in curl and "--data-raw" in curl
          and "q=hola+mundo" in curl, "copiar como cURL (con variables reemplazadas)")
    de_vuelta = s.parse_curl(curl)
    check(de_vuelta.metodo == "POST" and de_vuelta.auth_tipo == "bearer"
          and de_vuelta.params == [s.kv("q", "hola mundo")]
          and json.loads(de_vuelta.body) == {"a": 1}, "cURL -> petición -> cURL (ida y vuelta)")
    chrome = ("curl 'https://api.x.com/v1/items?page=2&limit=10' \\\n"
              "  -H 'accept: application/json' \\\n  -H 'content-type: application/json' \\\n"
              "  --data-raw '{\"nombre\":\"Kraken\"}' \\\n  --compressed")
    c = s.parse_curl(chrome)
    check(c.metodo == "POST" and c.url == "https://api.x.com/v1/items" and len(c.params) == 2
          and c.body_tipo == "json" and len(c.headers) == 2, "cURL estilo Chrome")
    c = s.parse_curl('curl -u admin:1234 -d "a=1&b=2" http://localhost:8069/web')
    check(c.auth_tipo == "basic" and c.auth_clave == "1234" and c.body_tipo == "form"
          and c.form == [s.kv("a", "1"), s.kv("b", "2")], "cURL con -u y formulario")
    c = s.parse_curl("curl -X DELETE --url=https://x.com/1 -H 'Authorization: Bearer zz'")
    check(c.metodo == "DELETE" and c.auth_usuario == "zz" and c.headers == [], "--url= y Bearer")
    for malo in ("", "wget x", "curl -H 'a: b'", "curl 'sin cerrar"):
        try:
            s.parse_curl(malo)
            check(False, f"debió rechazar: {malo!r}")
        except ValueError:
            pass
    check(True, "rechaza textos que no son curl, sin URL o mal cerrados")


def make_test_db(ruta: Path):  # propio
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE clientes (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, ciudad TEXT,
                               foto BLOB);
        CREATE TABLE "pedidos del mes" (id INTEGER PRIMARY KEY,
                               cliente_id INTEGER REFERENCES clientes(id), total REAL);
        CREATE INDEX ix_pedidos_cliente ON "pedidos del mes"(cliente_id);
        CREATE VIEW grandes AS SELECT * FROM "pedidos del mes" WHERE total > 100;
    """)
    con.executemany("INSERT INTO clientes (nombre, ciudad, foto) VALUES (?, ?, ?)",
                    [(f"Cliente {i}", "CDMX" if i % 2 else "Puebla; centro",
                      b"\x00\x01" if i == 1 else None) for i in range(1, 121)])
    con.executemany('INSERT INTO "pedidos del mes" (cliente_id, total) VALUES (?, ?)',
                    [(i, i * 10.5) for i in range(1, 31)])
    con.commit()
    con.close()


def test_sqlite():  # propio
    from modulos.kraken.models import ConexionSqlite
    from modulos.kraken.sqlite import services as q

    print("SQLite")
    original = TMP / "tienda.db"
    make_test_db(original)
    try:
        q.add_database("notas.txt", b"hola, no soy una base")
        check(False, "rechazar un archivo que no es SQLite")
    except ValueError:
        check(True, "rechaza un archivo que no es SQLite")
    c = q.add_database("tienda.db", original.read_bytes())
    base = q.get_database(c.id)
    check(base.existe and base.ruta.parent.name == "bases" and base.solo_lectura,
          "se copia a data/kraken/bases/ y abre en solo lectura")

    tablas = {t.nombre: t for t in q.tables(base)}
    check(tablas["clientes"].filas == 120 and tablas["pedidos del mes"].filas == 30
          and tablas["grandes"].tipo == "view", "tablas, vistas y filas (nombre con espacios)")
    e = q.schema(base, "pedidos del mes")
    col = {x.nombre: x for x in e.columnas}
    check(col["id"].llave and col["cliente_id"].apunta_a == "clientes.id"
          and e.indices[0][0] == "ix_pedidos_cliente", "esquema: llave, foránea e índice")
    cols, filas, total = q.page_rows(base, "clientes", pagina=2)
    check(len(filas) == 20 and total == 120 and filas[0][0] == 101, "página 3 de 50 en 50")
    cols, filas, total = q.page_rows(base, "clientes", buscar="puebla")
    check(total == 60, "búsqueda en todas las columnas")
    check(q.cell_text(None) == "NULL" and q.cell_text(b"\x00\x01") == "<BLOB 2 B>"
          and q.cell_text("x" * 100).endswith("…"), "celdas: NULL, BLOB y texto largo")

    r = q.run(base, "SELECT ciudad, COUNT(*) n FROM clientes GROUP BY ciudad ORDER BY 1;")
    check(r.error is None and r.columnas == ["ciudad", "n"] and len(r.filas) == 2, "SELECT")
    r = q.run(base, "SELECT * FROM clientes c, clientes d")
    check(r.hay_mas and len(r.filas) == q.MAX_FILAS, f"resultado grande: solo {q.MAX_FILAS} filas")
    r = q.run(base, "DELETE FROM clientes")
    check(r.error and "solo lectura" in r.error, "solo lectura de verdad (SQLite lo rechaza)")
    check(q.split_statements("select ';'; select 2") == ["select ';';", "select 2;"],
          "separa sentencias respetando ; dentro de textos")
    check(q.is_read_only("-- hola\nselect 1; pragma table_info(x)")
          and not q.is_read_only("select 1; update x set a=1"), "distingue lectura de escritura")

    ConexionSqlite.update(c.id, solo_lectura=False)
    base = q.get_database(c.id)
    r = q.run(base, "UPDATE clientes SET ciudad = 'GDL' WHERE id <= 5; "
                    "INSERT INTO clientes (nombre) VALUES ('Nuevo')")
    check(r.error is None and r.cambios == 6 and r.sentencias == 2, "editable: varias sentencias")
    r = q.run(base, "UPDATE clientes SET ciudad = 'X'; INSERT INTO nada VALUES (1)")
    _, filas, _ = q.page_rows(base, "clientes", buscar="X")
    check(r.error and "no such table" in r.error and not any(f[2] == "X" for f in filas),
          "si una sentencia falla, no se aplica ninguna")
    check(original.read_bytes() != base.ruta.read_bytes(), "el archivo original no se toca")

    app = q.get_database(None)
    r = q.run(app, "SELECT COUNT(*) FROM kt_entornos")
    check(r.error is None and r.filas[0][0] >= 1, "ControlKraken se puede consultar")
    r = q.run(app, "DELETE FROM kt_entornos")
    check(r.error and "ControlKraken" in r.error, "ControlKraken siempre en solo lectura")

    check(len(q.history(base)) >= 4 and len(q.history(app)) == 2, "historial por base")
    q.save_favorite(base, "Por ciudad", "SELECT ciudad FROM clientes")
    check([f.nombre for f in q.favorites(base)] == ["Por ciudad"] and not q.favorites(app),
          "favoritas por base")
    csv_ = q.to_csv(["a", "b"], [(1, None), ("ñ, sí", b"\x00")]).decode("utf-8-sig")
    check(csv_.splitlines() == ["a,b", "1,", '"ñ, sí",<BLOB 1 bytes>'], "CSV")
    check(q.file_bytes(base)[:16] == q.ENCABEZADO, "descargar copia de la base")
    return c.id


def test_backup(conexion_id: int):  # propio
    from core import backup
    from modulos.kraken.models import ConexionSqlite
    from modulos.kraken.sqlite import services as q

    print("Respaldo")
    grande = q.add_database("grande.db", (TMP / "tienda.db").read_bytes())
    ConexionSqlite.update(grande.id, respaldar=False)
    con_ruta = q.get_database(conexion_id).ruta
    sin_ruta = q.get_database(grande.id).ruta
    zip_ = backup.create_backup(TMP / "zips", "prueba")
    nombres = set(zipfile.ZipFile(zip_).namelist())
    rel = lambda r: "data/" + r.relative_to(database.DATA_ROOT / "data").as_posix()  # noqa: E731
    check(rel(con_ruta) in nombres, "base con «respaldar» entra al zip")
    check(rel(sin_ruta) not in nombres, "base con «no respaldar» se queda fuera del zip")
    backup.restore_backup(zip_)
    check(con_ruta.is_file() and sin_ruta.is_file(),
          "al restaurar, la base fuera del respaldo NO se borra de este equipo")
    check(ConexionSqlite.get(grande.id) is not None, "su conexión sigue (viene en la BD)")


# ============================================================================
# Red: servidores falsos
# ============================================================================
def start_dns() -> int:  # propio
    """Servidor DNS mínimo (UDP) con dnspython: ejemplo.test y nada más."""
    import socket
    import dns.message
    import dns.rcode
    import dns.rrset

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    respuestas = {"A": ["93.184.216.34"], "MX": ["10 correo.ejemplo.test."],
                  "TXT": ['"v=spf1 -all"'], "NS": ["ns1.ejemplo.test."]}

    def servir():  # propio
        while True:
            datos, quien = s.recvfrom(4096)
            pregunta = dns.message.from_wire(datos)
            resp = dns.message.make_response(pregunta)
            q = pregunta.question[0]
            nombre, tipo = q.name.to_text(), dns.rdatatype.to_text(q.rdtype)
            if nombre == "ejemplo.test.":
                if tipo in respuestas:
                    resp.answer.append(dns.rrset.from_text(nombre, 300, "IN", tipo,
                                                           *respuestas[tipo]))
            elif nombre == "1.0.0.127.in-addr.arpa.":
                resp.answer.append(dns.rrset.from_text(nombre, 60, "IN", "PTR", "localhost."))
            else:
                resp.set_rcode(dns.rcode.NXDOMAIN)
            s.sendto(resp.to_wire(), quien)

    threading.Thread(target=servir, daemon=True).start()
    return s.getsockname()[1]


def start_whois() -> int:  # propio
    """Puerto 43 falso: hace de whois.iana.org (refer) y del registro de .test."""
    import socketserver

    class W(socketserver.StreamRequestHandler):
        def handle(self):  # propio
            pregunta = self.rfile.readline().decode().strip()
            if pregunta == "test":
                texto = "domain: TEST\nrefer: 127.0.0.1\n"
            elif pregunta == "viejo.test":
                texto = ("Domain Name: VIEJO.TEST\nRegistrar: Akky\n"
                         "Created On: 2001-05-10\nExpiration Date: 15-mar-2020\n"
                         "DNS: ns1.viejo.test\nDNS: ns2.viejo.test\n")
            else:
                texto = "No match for domain\n"
            self.wfile.write(texto.encode())

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), W)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def start_tls(dias: int) -> int:  # propio
    """HTTPS con certificado autofirmado (dias < 0: ya vencido), hecho con openssl."""
    import ssl
    import subprocess

    carpeta = Path(tempfile.mkdtemp())
    llave, cert = carpeta / "k.pem", carpeta / "c.pem"
    if dias >= 0:
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout",
                        llave, "-out", cert, "-days", str(dias), "-subj", "/CN=localhost",
                        "-addext", "subjectAltName=DNS:localhost"], check=True,
                       capture_output=True)
    else:  # vencido: openssl de línea de comandos no deja fechas pasadas -> cryptography
        from datetime import datetime as dt

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        nombre = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "viejo.local")])
        c = (x509.CertificateBuilder().subject_name(nombre).issuer_name(nombre)
             .public_key(k.public_key()).serial_number(1)
             .not_valid_before(dt(2020, 1, 1)).not_valid_after(dt(2021, 1, 1))
             .sign(k, hashes.SHA256()))
        llave.write_bytes(k.private_bytes(serialization.Encoding.PEM,
                                          serialization.PrivateFormat.TraditionalOpenSSL,
                                          serialization.NoEncryption()))
        cert.write_bytes(c.public_bytes(serialization.Encoding.PEM))
    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.load_cert_chain(cert, llave)
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()

    def servir():  # propio
        while True:
            c, _ = s.accept()
            try:
                with contexto.wrap_socket(c, server_side=True) as t:
                    t.recv(10)
            except (ssl.SSLError, OSError):
                pass

    threading.Thread(target=servir, daemon=True).start()
    return s.getsockname()[1]


def test_red(base: str):  # propio
    import socket
    from modulos.kraken.models import Ajustes, Equipo, HistorialRed
    from modulos.kraken.red import (certificado, consulta_dns, historial, mi_ip, ping, puertos,
                                    whois, wol)
    from modulos.kraken.red.comun import clean_host

    print("Red")
    check(clean_host("https://www.Ejemplo.com/ruta?x=1") == "www.ejemplo.com"
          and clean_host("ejemplo.com:8069") == "ejemplo.com" and clean_host(" 10.0.0.1 ") == "10.0.0.1",
          "limpia lo que escribes (URL, puerto, espacios)")
    # --- ping
    if ping._icmp_available():
        r = asyncio.run(ping.ping("127.0.0.1", veces=3, pausa=0.05))
        check(r.metodo == "icmp" and len(r.recibidos) == 3, f"ping ICMP: {r.summary()[0]}")
    else:
        print("  · ICMP no permitido en este equipo: se prueba solo TCP")
    puerto_http = int(base.rsplit(":", 1)[1])
    avances = []
    r = asyncio.run(ping.ping("localhost", veces=3, pausa=0.05, metodo="tcp",
                              on_progress=lambda x: avances.append(len(x.tiempos))))
    check(r.metodo == "tcp" and len(r.recibidos) == 3 and avances == [1, 2, 3],
          f"ping TCP (aunque el puerto esté cerrado, contesta): {r.summary()[0]}")
    r = asyncio.run(ping.ping("no-existe.invalid", veces=1))
    check(r.error and "No se encontró" in r.error, "ping a un dominio que no existe")

    # --- puertos
    libre = socket.socket(); libre.bind(("127.0.0.1", 0)); cerrado = libre.getsockname()[1]
    libre.close()
    r = asyncio.run(puertos.scan("127.0.0.1", f"{puerto_http}, {cerrado}"))
    estados = {p["puerto"]: p["estado"] for p in r.puertos}
    check(estados == {puerto_http: "abierto", cerrado: "cerrado"} and len(r.abiertos) == 1,
          f"puertos: abierto y cerrado ({r.summary()[0]})")
    r = asyncio.run(puertos.scan("127.0.0.1", "1-1000", timeout=0.5))
    check(r.revisados == 1000 and r.puertos[0]["puerto"] == 1, "1,000 puertos en orden")
    r = asyncio.run(puertos.scan("127.0.0.1", "80-x"))
    check(r.error is not None, "rango mal escrito")
    check(puertos.SERVICIOS[8069] == "Odoo", "nombres de servicios (8069 = Odoo)")

    # --- DNS
    servidor = f"127.0.0.1:{start_dns()}"
    r = asyncio.run(consulta_dns.lookup("ejemplo.test", servidor))
    reg = {t: [x["valor"] for x in v] for t, v in r.registros.items()}
    check(reg["A"] == ["93.184.216.34"] and reg["MX"] == ["10 correo.ejemplo.test"]
          and reg["TXT"] == ["v=spf1 -all"] and reg["AAAA"] == [] and r.error is None,
          f"DNS: A, MX, TXT y NS ({r.summary()[0]})")
    r = asyncio.run(consulta_dns.lookup("127.0.0.1", servidor))
    check(r.registros.get("PTR", [{}])[0].get("valor") == "localhost", "DNS inverso (PTR)")
    r = asyncio.run(consulta_dns.lookup("noexiste.test", servidor))
    check(r.error and "no existe" in r.error, "DNS: dominio que no existe")
    r = asyncio.run(consulta_dns.lookup("ejemplo.test", "127.0.0.1:1", timeout=1))
    check(r.error and "no contestó" in r.error, "DNS: servidor que no contesta")
    r = asyncio.run(consulta_dns.lookup("x.com", "dns.google"))
    check(r.error and "IP" in r.error, "el servidor DNS debe ser una IP")
    check(Ajustes.current().dns_servidor == "1.1.1.1", "DNS por defecto: 1.1.1.1 (Cloudflare)")

    # --- certificado
    r = asyncio.run(certificado.check(f"localhost:{start_tls(90)}"))
    check(not r.valido and "autofirmado" in r.motivo and 88 <= r.dias_restantes <= 90
          and r.para == "localhost" and r.nombres == ["localhost"],
          f"certificado autofirmado: {r.summary()[0]}")
    try:
        import cryptography  # noqa: F401  (solo para fabricar el certificado vencido)
        r = asyncio.run(certificado.check("localhost", start_tls(-1)))
        check(not r.valido and r.dias_restantes < 0 and r.para == "viejo.local",
              f"certificado vencido: {r.summary()[0]}")
    except ImportError:
        print("  · sin el paquete cryptography: se salta la prueba del certificado vencido")
    r = asyncio.run(certificado.check("localhost", puerto_http, timeout=2))
    check(r.error and "HTTPS" in r.error, "un puerto que no habla HTTPS")
    r = asyncio.run(certificado.check("localhost", cerrado))
    check(r.error and "cerrado" in r.error, "puerto cerrado")

    # --- whois
    puerto_whois = start_whois()
    rdap = f"{base}/rdap/domain/"
    r = asyncio.run(whois.lookup("https://www.registrado.test/x", rdap=rdap, iana="127.0.0.1",
                                 puerto=puerto_whois))
    check(r.fuente == "RDAP" and r.registrador == "Registrador X" and r.vence == "2030-03-01"
          and r.servidores == ["ns1.ejemplo.test"] and r.dias_restantes > 1000,
          f"Whois por RDAP: {r.summary()[0]}")
    r = asyncio.run(whois.lookup("viejo.test", rdap=rdap, iana="127.0.0.1", puerto=puerto_whois))
    check(r.fuente == "WHOIS" and r.registrador == "Akky" and r.creado == "2001-05-10"
          and r.vence == "2020-03-15" and r.dias_restantes < 0 and len(r.servidores) == 2,
          f"Whois por puerto 43 (formato .mx): {r.summary()[0]}")
    r = asyncio.run(whois.lookup("libre.test", rdap=rdap, iana="127.0.0.1", puerto=puerto_whois))
    check(r.error and "no está registrado" in r.error, "dominio libre")
    check(whois.to_date("2026-03-15T04:00:00Z") == whois.to_date("15-Mar-2026")
          == whois.to_date("2026.03.15") == "2026-03-15", "fechas en varios formatos")
    r = asyncio.run(whois.lookup("8.8.8.8"))
    check(r.error is not None, "Whois de una IP: se explica que es para dominios")

    # --- mi IP
    r = asyncio.run(mi_ip.my_ip(servicio_info=f"{base}/ipinfo", servicio_ip=f"{base}/404"))
    check(r.publica == "201.141.1.2" and r.proveedor == "AS8151 Uninet" and r.ciudad.startswith("Puebla"),
          f"Mi IP: {r.summary()[0]}")
    r = asyncio.run(mi_ip.my_ip(servicio_info="http://127.0.0.1:1/x",
                                servicio_ip="http://127.0.0.1:1/y", timeout=1))
    check(r.publica is None and r.error_publica, "sin internet: lo dice, no truena")
    check(mi_ip.network_of("192.168.1.37") == "192.168.1.0/24", "red local /24")

    # --- Wake-on-LAN
    escucha = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    escucha.bind(("127.0.0.1", 0)); escucha.settimeout(2)
    r = wol.wake("aa-bb-cc-dd-ee-ff", destino="127.0.0.1", puertos=(escucha.getsockname()[1],))
    datos, _ = escucha.recvfrom(200)
    check(r.error is None and len(datos) == 102 and datos[:6] == b"\xff" * 6
          and datos[6:12] == bytes.fromhex("aabbccddeeff"), "Wake-on-LAN: paquete mágico de 102 bytes")
    check(wol.wake("12:34").error is not None, "MAC mal escrita")

    # --- dispositivos en mi red (127.0.0.x: todas contestan "cerrado"; .3 tiene el 22)
    from modulos.kraken.red import dispositivos
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("127.0.0.3", 22)); srv.listen()
        con_ssh = True
    except OSError:
        con_ssh = False
    avances = []
    r = asyncio.run(dispositivos.discover("127.0.0.0/29", on_progress=lambda x: avances.append(1)))
    ips = [x["ip"] for x in r.dispositivos]
    check(r.revisados == 6 and ips == [f"127.0.0.{k}" for k in range(1, 7)] and avances,
          f"dispositivos: {r.summary()[0]} ({r.metodo})")
    if con_ssh:
        tres = r.dispositivos[2]
        check(tres["puertos"] == [22] and tres["parece"] == "Linux / servidor",
              "adivina qué es por sus puertos (22 -> Linux / servidor)")
    srv.close()
    for malo, texto in (("8.8.8.0/24", "privadas"), ("10.0.0.0/16", "grande"), ("x", "no válida")):
        check(texto in (asyncio.run(dispositivos.discover(malo)).error or ""),
              f"red rechazada: {malo}")
    check(dispositivos.guess("192.168.1.1", []) == "Probablemente tu router"
          and dispositivos.guess("192.168.1.9", [62078]) == "iPhone / iPad", "pistas por puertos")

    # --- equipos e historial
    e = Equipo.create(nombre="Servidor casa", host="192.168.1.10", puertos="22, 8069",
                      mac="AA:BB:CC:DD:EE:FF")
    check(e.id is not None, "equipo guardado")
    for malo in (dict(nombre="X", host="a b"), dict(nombre="X", host="h", puertos="99999"),
                 dict(nombre="X", host="h", mac="zz")):
        try:
            Equipo.create(**malo)
            check(False, f"equipo inválido aceptado: {malo}")
        except ValueError:
            pass
    check(True, "rechaza host con espacios, puertos y MAC inválidos")
    historial.clear()
    Ajustes.change(red_historial_max=3)
    for k in range(5):
        historial.record("ping", f"host{k}", asyncio.run(ping.ping("localhost", veces=1,
                                                                   metodo="tcp")))
    check(historial.count() == 3 and historial.history()[0].objetivo == "host4",
          "historial de Red con límite configurable (5 -> 3)")
    check(historial.recent_targets("ping")[:2] == ["host4", "host3"], "últimos objetivos")
    h = HistorialRed.get(historial.history()[0].id)
    check(h.detalle["metodo"] == "tcp" and h.exito, "el detalle completo se guarda")


def main() -> int:  # propio
    database.init_db()
    print(f"Carpeta de prueba: {TMP}")
    base = start_server()
    test_http(base)
    conexion_id = test_sqlite()
    test_backup(conexion_id)
    test_red(base)
    print()
    if FALLAS:
        print(f"✗ {len(FALLAS)} prueba(s) fallaron")
        return 1
    print("✓ Kraken Tools pasa todas las pruebas")
    return 0


if __name__ == "__main__":
    sys.exit(main())

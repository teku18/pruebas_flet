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
  SSH      un servidor SSH falso (paramiko) que corre los comandos de verdad en
           esta máquina, con un `sudo` falso: conexión, huella del servidor,
           métricas (CPU, RAM, discos, red, procesos, servicios), comandos con
           sudo, logs y errores (contraseña mala, puerto cerrado).
  Bases    PostgreSQL y MySQL de verdad, directo y por túnel SSH. Solo corren si
           les dices dónde hay uno de prueba (si no, se saltan):
             CK_TEST_PG=127.0.0.1:5432:usuario:clave
             CK_TEST_MYSQL=127.0.0.1:3306:usuario:clave
           Crean y borran sus propias bases de prueba (kraken_prueba_*).
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
import time
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


POSTMAN_V21 = {
    "info": {"_postman_id": "x", "name": "Mi API Odoo",
             "description": {"content": "Pruebas"},
             "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]},
    "variable": [{"key": "base", "value": "http://localhost:8069"}],
    "event": [{"listen": "prerequest", "script": {"exec": ["console.log(1)"]}}],
    "item": [
        {"name": "Usuarios", "item": [
            {"name": "Listar", "request": {
                "method": "GET", "header": [{"key": "Accept", "value": "application/json"},
                                            {"key": "X-Off", "value": "1", "disabled": True}],
                "url": {"raw": "{{base}}/api/users?page=2&q=a%20b", "host": ["{{base}}"],
                        "path": ["api", "users"],
                        "query": [{"key": "page", "value": "2"}, {"key": "q", "value": "a b"},
                                  {"key": "debug", "value": "1", "disabled": True}]}},
             "event": [{"listen": "test", "script": {"exec": ["pm.test()"]}}]},
            {"name": "Admin", "auth": {"type": "basic", "basic": [
                {"key": "username", "value": "admin"}, {"key": "password", "value": "secreto"}]},
             "item": [
                {"name": "Crear", "request": {
                    "method": "POST", "url": "{{base}}/api/users",
                    "body": {"mode": "raw", "raw": "{\"name\": \"Ana\"}",
                             "options": {"raw": {"language": "json"}}}}},
                {"name": "Sin auth", "request": {"method": "DELETE", "auth": {"type": "noauth"},
                                                 "url": "{{base}}/api/users/1"}}]}]},
        {"name": "Login", "request": {"method": "POST", "url": "{{base}}/web/login",
                                      "body": {"mode": "urlencoded", "urlencoded": [
                                          {"key": "login", "value": "a@b.c"},
                                          {"key": "password", "value": "x"}]}}},
        {"name": "Subir", "request": {"method": "POST", "url": "{{base}}/upload",
                                      "body": {"mode": "formdata", "formdata": [
                                          {"key": "titulo", "value": "foto"},
                                          {"key": "archivo", "type": "file", "src": "/a.png"}]}}},
        {"name": "GraphQL", "request": {"method": "POST", "url": "{{base}}/graphql",
                                        "body": {"mode": "graphql", "graphql": {
                                            "query": "{ me { id } }", "variables": "{\"a\": 1}"}}}},
        {"name": "Con API key", "request": {
            "method": "GET", "url": "https://api.x.com/v1",
            "auth": {"type": "apikey", "apikey": [{"key": "key", "value": "X-Key"},
                                                  {"key": "value", "value": "abc"},
                                                  {"key": "in", "value": "header"}]}}},
        {"name": "OAuth", "request": {"method": "GET", "url": "https://x.com",
                                      "auth": {"type": "oauth2", "oauth2": []}}},
    ],
}


def test_postman():  # propio
    """Importar y exportar colecciones y entornos de Postman (v2.1)."""
    from modulos.kraken.http import postman
    from modulos.kraken.models import Coleccion, Entorno

    print("Postman")
    r = postman.import_file(json.dumps(POSTMAN_V21).encode(), "mi.json")
    check(r.peticiones == 8 and r.colecciones == ["Mi API Odoo"], f"importa: {r.summary()}")
    c = Coleccion.search(Coleccion.nombre == "Mi API Odoo")[0]
    p = {x.nombre: x for x in c.peticiones}
    check([x.nombre for x in c.peticiones][:3] == ["Usuarios / Listar", "Usuarios / Admin / Crear",
                                                   "Usuarios / Admin / Sin auth"],
          "carpetas anidadas -> 'Usuarios / Admin / Crear' y en el mismo orden")
    listar = p["Usuarios / Listar"]
    check(listar.url == "{{base}}/api/users"
          and [(f["clave"], f["valor"], f["activo"]) for f in listar.params]
          == [("page", "2", True), ("q", "a b", True), ("debug", "1", False)],
          "URL sin query + params (también los desactivados)")
    check(listar.headers[1]["activo"] is False, "header desactivado se respeta")
    check(listar.auth_tipo == "bearer" and listar.auth_usuario == "{{token}}",
          "auth de la colección se hereda")
    crear = p["Usuarios / Admin / Crear"]
    check(crear.auth_tipo == "basic" and crear.auth_clave == "secreto"
          and crear.body_tipo == "json" and '"Ana"' in crear.body,
          "auth de la carpeta + body JSON")
    check(p["Usuarios / Admin / Sin auth"].auth_tipo == "ninguna", "noauth = Ninguna")
    check(p["Login"].body_tipo == "form" and len(p["Login"].form) == 2, "urlencoded -> Formulario")
    check(p["Subir"].form == [{"clave": "titulo", "valor": "foto", "activo": True}],
          "form-data: el archivo se omite")
    check(json.loads(p["GraphQL"].body) == {"query": "{ me { id } }", "variables": {"a": 1}},
          "GraphQL -> JSON")
    check(p["Con API key"].headers == [{"clave": "X-Key", "valor": "abc", "activo": True}],
          "API Key -> header")
    check(any("script" in a for a in r.avisos) and any("archivo" in a for a in r.avisos)
          and any("oauth2" in a for a in r.avisos) and any("entorno" in a for a in r.avisos),
          "avisa scripts, archivos, auth no soportada y variables")
    e = Entorno.search(Entorno.nombre == "Mi API Odoo")[0]
    check(e.variables == [{"clave": "base", "valor": "http://localhost:8069", "activo": True}],
          "variables de la colección -> entorno")
    r2 = postman.import_file(json.dumps(POSTMAN_V21), "otra")
    check(r2.colecciones == ["Mi API Odoo (2)"], "nombre repetido -> (2)")

    nombre, datos = postman.export_collection(c.id)
    doc = json.loads(datos)
    check(nombre == "Mi_API_Odoo.postman_collection.json" and doc["info"]["schema"].endswith(
        "v2.1.0/collection.json"), "exporta v2.1")
    usuarios = doc["item"][0]
    check(usuarios["name"] == "Usuarios" and usuarios["item"][1]["name"] == "Admin"
          and usuarios["item"][1]["item"][0]["name"] == "Crear", "las carpetas se vuelven a armar")
    url = usuarios["item"][0]["request"]["url"]
    check(url["raw"] == "{{base}}/api/users?page=2&q=a b" and len(url["query"]) == 3
          and url["query"][2]["disabled"], "URL de vuelta con su query")
    # ida y vuelta: lo exportado se vuelve a importar igual
    r3 = postman.import_file(datos)
    c3 = Coleccion.search(Coleccion.nombre == r3.colecciones[0])[0]
    campos = lambda x: (x.nombre, x.metodo, x.url, x.params, x.headers, x.body_tipo, x.body,  # noqa: E731
                        x.form, x.auth_tipo, x.auth_usuario, x.auth_clave)
    check([campos(x) for x in c3.peticiones] == [campos(x) for x in c.peticiones],
          "ida y vuelta: exportar e importar deja todo igual")

    nombre, datos = postman.export_environment(e.id)
    env = json.loads(datos)
    check(env["name"] == "Mi API Odoo" and env["values"][0]["key"] == "base", "exporta entorno")
    r4 = postman.import_file(datos)
    check(len(r4.entornos) == 1 and not r4.colecciones and Entorno.search(
        Entorno.nombre == r4.entornos[0])[0].variables == e.variables,
          f"importa entorno: «{r4.entornos[0]}»")
    for malo, texto in ((b"no es json", "JSON"), (b"[1,2]", "Postman"), (b'{"a": 1}', "Postman")):
        try:
            postman.import_file(malo)
            check(False, f"aceptó {malo!r}")
        except ValueError as ex:
            check(texto in str(ex), f"rechaza {malo[:10]!r}: {ex}")


def test_variables_ui():  # propio
    """Pintar y autocompletar {{variables}} (la lógica; lo visual se revisa en el navegador)."""
    from modulos.kraken.http import services as s

    print("Variables: colores y autocompletar")
    check(s.split_variables("{{base}}/u/{{ id }}?x=1") == [
        ("{{base}}", "base"), ("/u/", None), ("{{ id }}", "id"), ("?x=1", None)],
          "separa texto y variables (también con espacios)")
    check(s.split_variables("sin nada") == [("sin nada", None)] and s.split_variables("") == [],
          "texto sin variables")
    check(s.variable_at_cursor("{{base}}/{{to", None) == (9, "to"), "detecta {{to al final")
    check(s.variable_at_cursor("{{to}}/x", 4) == (0, "to"), "detecta en medio (cursor)")
    check(s.variable_at_cursor("x {{", None) == (2, ""), "recién abierta: {{")
    check(s.variable_at_cursor("{{a}} b", None) is None and s.variable_at_cursor("{{a b", None)
          is None, "ya cerrada o con espacio: no sugiere")
    valores = {"token": "1", "auth_token": "2", "base": "3", "Token_admin": "4"}
    check([k for k, _ in s.suggest_variables("to", valores)] == ["Token_admin", "token",
                                                                 "auth_token"],
          "sugiere: primero las que empiezan, sin distinguir mayúsculas")
    check(len(s.suggest_variables("", valores)) == 4, "{{ sola: todas")
    check(s.insert_variable("{{ba}}/x", 0, 4, "base") == ("{{base}}/x", 8),
          "completa sin duplicar }}")
    check(s.insert_variable("a {{t", 2, None, "token") == ("a {{token}}", 11), "completa al final")
    check(s.insert_variable("{{t}/x", 0, 3, "token") == ("{{token}}/x", 9), "con una sola }")


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


# ============================================================================
# SSH: servidor falso
# ============================================================================
SUDO_FALSO = """#!/bin/bash
# sudo de prueba: -S lee la contraseña de la entrada; si es "secreto", ejecuta
# -v valida y "recuerda" (archivo marca); -n corre sólo si ya se validó.
validar=0; sinclave=0
while [ "${1:0:1}" = "-" ]; do
  case "$1" in -p) shift;; -v) validar=1;; -n) sinclave=1;; esac; shift; done
if [ $sinclave = 1 ]; then
  [ -e "${TMPDIR:-/tmp}/ck_sudo_ok" ] || { echo "sudo: a password is required" >&2; exit 1; }
  exec "$@"; fi
read -r clave
if [ "$clave" != "secreto" ]; then echo "Sorry, try again." >&2
  echo "sudo: 1 incorrect password attempt" >&2; exit 1; fi
if [ $validar = 1 ]; then touch "${TMPDIR:-/tmp}/ck_sudo_ok"; exit 0; fi
exec "$@"
"""


def start_ssh(usuario: str = "edgar", clave: str = "secreto") -> int:  # propio
    """Servidor SSH falso: acepta usuario/clave y corre cada comando con bash."""
    import socket
    import subprocess

    import paramiko

    bin_dir = Path(tempfile.mkdtemp())
    (bin_dir / "sudo").write_text(SUDO_FALSO)
    (bin_dir / "sudo").chmod(0o755)
    # crontab de prueba: guarda en un archivo (no toca el crontab real de esta máquina)
    (bin_dir / "crontab").write_text('#!/bin/bash\nf="$HOME/.crontab_prueba"\n'
                                     'if [ "$1" = "-l" ]; then cat "$f" 2>/dev/null; '
                                     'else cat > "$f"; fi\n')
    (bin_dir / "crontab").chmod(0o755)
    casa = Path(tempfile.mkdtemp(prefix="ck_home_"))   # el HOME del "servidor"
    llave = paramiko.RSAKey.generate(2048)  # cada servidor falso: su propia llave

    class Srv(paramiko.ServerInterface):
        def __init__(self):  # propio
            self.listo, self.cmd = threading.Event(), None
            self.tuneles = {}  # canal -> (host, puerto) de un túnel

        def check_auth_password(self, u, p):  # noqa: D102
            return paramiko.AUTH_SUCCESSFUL if (u, p) == (usuario, clave) else paramiko.AUTH_FAILED

        def get_allowed_auths(self, u):  # noqa: D102
            return "password"

        def check_channel_request(self, kind, cid):  # noqa: D102
            return paramiko.OPEN_SUCCEEDED

        def check_channel_exec_request(self, ch, cmd):  # noqa: D102
            self.cmd = cmd.decode()
            self.listo.set()
            return True

        def check_channel_direct_tcpip_request(self, chanid, origen, destino):  # noqa: D102
            self.tuneles[chanid] = destino
            return paramiko.OPEN_SUCCEEDED

    def channel(t: "paramiko.Transport"):  # propio
        while t.is_active():
            ch = t.accept(5)
            if ch is None:
                continue
            srv = t.server_object
            if ch.get_id() in srv.tuneles:  # túnel: conectar al destino y pasar bytes
                from modulos.kraken.ssh.tunel import Tunel
                destino = socket.create_connection(srv.tuneles.pop(ch.get_id()))
                threading.Thread(target=Tunel._pump, args=(destino, ch), daemon=True).start()
                continue
            srv.listo.wait(5)
            srv.listo.clear()
            env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", TMPDIR=str(bin_dir),
                       HOME=str(casa))
            proc = subprocess.Popen(["bash", "-c", srv.cmd], stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            ch.settimeout(0.3)
            entrada = b""
            try:
                while True:
                    trozo = ch.recv(4096)
                    if not trozo:
                        break
                    entrada += trozo
            except socket.timeout:
                pass
            if srv.cmd.startswith("bash -l -s"):  # consola: salida en vivo + Ctrl+C
                proc.stdin.write(entrada)
                proc.stdin.close()
                os.set_blocking(proc.stdout.fileno(), False)
                while True:
                    if ch.closed or not t.is_active():
                        proc.kill()
                        break
                    trozo = proc.stdout.read(4096)
                    if trozo:
                        ch.sendall(trozo)
                    elif proc.poll() is not None:
                        resto = proc.stdout.read() or b""
                        ch.sendall(resto + (proc.stderr.read() or b""))
                        ch.send_exit_status(proc.returncode)
                        ch.close()
                        break
                    else:
                        time.sleep(0.05)
                continue
            out, err = proc.communicate(entrada)
            ch.sendall(out)
            ch.sendall_stderr(err)
            ch.send_exit_status(proc.returncode)
            ch.close()

    def attend(c):  # propio
        t = paramiko.Transport(c)
        t.add_server_key(llave)
        t.start_server(server=Srv())
        channel(t)

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    s.listen()

    def accept():  # propio
        while True:
            c, _ = s.accept()
            threading.Thread(target=attend, args=(c,), daemon=True).start()

    threading.Thread(target=accept, daemon=True).start()
    return s.getsockname()[1]


def test_ssh():  # propio
    import time as tiempo

    from modulos.kraken.models import ComandoSsh, Equipo
    from modulos.kraken.ssh import acciones, metricas
    from modulos.kraken.ssh.conexion import HuellaCambio, Sesion, friendly

    print("SSH")
    puerto = start_ssh()
    e = Equipo.create(nombre="Servidor cliente", host="127.0.0.1", ssh_usuario="edgar",
                      ssh_puerto=puerto, ssh_clave="secreto", ssh_servicios="cron ssh")
    with Sesion(e) as ses:
        check(ses.abierta and ses.huella.startswith("ssh-rsa SHA256:"),
              f"conecta y lee la huella ({ses.ms_conexion} ms)")
        check(Equipo.get(e.id).ssh_huella == ses.huella, "la huella se guarda la primera vez")
        texto = ses.run(metricas.script(e.servicios)).texto
        m1 = metricas.parse(texto, tiempo.monotonic())
        tiempo.sleep(1)
        m2 = metricas.parse(ses.run(metricas.script(e.servicios)).texto, tiempo.monotonic(), m1)
    check(m1.ram_total > 0 and m1.discos and m1.nucleos >= 1 and m1.encendido_s > 0
          and m1.cpu is None, f"métricas: {m1.sistema} · {m1.nucleos} núcleos · "
          f"RAM {metricas.kb_text(m1.ram_total)} · {len(m1.discos)} disco(s)")
    check(m2.cpu is not None and 0 <= m2.cpu <= 100 and m2.rx_s is not None,
          f"segunda lectura: {m2.summary()}")
    check(m1.procesos and set(m1.servicios) == {"cron", "ssh"}, "procesos y servicios")
    check(metricas.uptime_text(266580) == "3 días, 2 h" and metricas.kb_text(32276480) == "30.8 GB",
          "textos de tiempo encendido y tamaño")
    raro = "@@os\nX\n@@fin\n"
    check(metricas.parse(raro, 0).ram_total == 0, "un servidor raro no truena el panel")
    try:
        metricas.parse("Welcome to router", 0)
        check(False, "salida sin datos aceptada")
    except ValueError:
        check(True, "salida que no es Linux: lo dice")

    with Sesion(Equipo.get(e.id)) as ses:
        r = acciones.run_command(ses, "Prueba sudo", "sudo echo hola-root")
        check(r.codigo == 0 and r.salida.strip() == "hola-root", "comando con sudo (contraseña por -S)")
        r = acciones.run_command(ses, "Falla", "ls /no/existe")
        # el mensaje depende del idioma del servidor ("No such file" / "No existe el archivo")
        check(r.codigo != 0 and "/no/existe" in r.errores and not r.summary()[1],
              f"comando que falla: {r.summary()[0]}")
        log = Path(tempfile.mkdtemp()) / "odoo.log"
        log.write_text("".join(f"2026-10-15 linea {k} {'ERROR boom' if k % 10 == 0 else 'INFO ok'}\n"
                               for k in range(1, 501)))
        s_ = acciones.read_log(ses, str(log), 50)
        check(len(s_.texto.splitlines()) == 50 and "linea 500" in s_.texto, "log: últimas 50 líneas")
        s_ = acciones.read_log(ses, str(log), 20, buscar="error")
        check(len(s_.texto.splitlines()) == 20 and all("ERROR" in x for x in s_.texto.splitlines()),
              "log: buscar sin distinguir mayúsculas")
        s_ = acciones.read_log(ses, str(log), 5, con_sudo=True)
        check(s_.ok and "linea 500" in s_.texto, "log con sudo")
        check(acciones.log_command("/var/log/a b.log", 10, "x'y") ==
              "grep -i -F -- 'x'\"'\"'y' '/var/log/a b.log' | tail -n 10", "rutas y búsquedas con comillas")

    Equipo.update(e.id, ssh_clave="mala")
    malo = Equipo.get(e.id)
    try:
        Sesion(malo).open()
        check(False, "contraseña mala aceptada")
    except Exception as ex:  # noqa: BLE001
        check("Usuario o contraseña incorrectos" in friendly(ex, malo), friendly(ex, malo))
    Equipo.update(e.id, ssh_clave="secreto", ssh_puerto=start_ssh())  # otro servidor: otra llave
    try:
        Sesion(Equipo.get(e.id)).open()
        check(False, "huella cambiada aceptada")
    except HuellaCambio as ex:
        ses = Sesion(Equipo.get(e.id))
        ses.open(aceptar_huella=ex.nueva)
        ses.close()
        check(Equipo.get(e.id).ssh_huella == ex.nueva,
              "si la huella cambia NO se conecta; al aceptar, se guarda la nueva")
    import socket
    libre = socket.socket(); libre.bind(("127.0.0.1", 0)); cerrado = libre.getsockname()[1]; libre.close()
    Equipo.update(e.id, ssh_puerto=cerrado)
    try:
        Sesion(Equipo.get(e.id)).open()
    except Exception as ex:  # noqa: BLE001
        check("Nadie atiende SSH" in friendly(ex, Equipo.get(e.id)), "puerto cerrado: explicado")
    check([c.nombre for c in ComandoSsh.for_server(e.id)][0] == "Reiniciar Odoo",
          "vienen los comandos iniciales")


# ============================================================================
# Bases de datos en servidor (PostgreSQL / MySQL)
# ============================================================================
def _admin(tipo: str, host, puerto, usuario, clave, base=None):  # propio
    if tipo == "postgres":
        import pg8000.dbapi
        con = pg8000.dbapi.connect(user=usuario, password=clave, host=host, port=puerto,
                                   database=base or "postgres")
        con.autocommit = True
        return con
    import pymysql
    return pymysql.connect(host=host, port=puerto, user=usuario, password=clave,
                           database=base, autocommit=True)


def test_console():  # propio
    """Consola SSH: comandos libres, carpeta recordada, sudo, Tab, Ctrl+C."""
    from modulos.kraken.models import Equipo
    from modulos.kraken.ssh import consola
    from modulos.kraken.ssh.conexion import Sesion

    print("Consola SSH")
    puerto = start_ssh()
    e = Equipo.create(nombre="Consola prueba", host="127.0.0.1", ssh_usuario="edgar",
                      ssh_puerto=puerto, ssh_clave="secreto")
    carpeta = Path(tempfile.mkdtemp())
    (carpeta / "sub dir").mkdir()
    (carpeta / "archivo_uno.txt").write_text("hola\n")
    with Sesion(e) as ses:
        c = consola.Consola(ses)
        c.start()
        check(c.cwd and c.cwd.startswith("/"), f"carpeta de inicio: {c.cwd}")
        r = c.run(f"cd {carpeta}")
        check(r.codigo == 0 and c.cwd == str(carpeta), "cd se recuerda")
        r = c.run("ls")
        check(r.codigo == 0 and "archivo_uno.txt" in r.salida and "sub dir" in r.salida,
              "ls libre en la carpeta recordada")
        r = c.run("cd 'sub dir' && pwd")
        check(c.cwd == str(carpeta / "sub dir") and r.salida.strip() == c.cwd, "cd con espacios")
        c.run("cd ..")
        r = c.run("ls /no/existe")
        check(r.codigo not in (0, None) and "/no/existe" in r.salida,
              "error: stderr junto a la salida + código")
        r = c.run("echo uno; echo dos >&2; echo tres | tr a-z A-Z")
        check(r.salida.splitlines() == ["uno", "dos", "TRES"], "tuberías y varios comandos")
        r = c.run("cd /tmp && sudo echo hola-root")
        check(r.codigo == 0 and r.salida.strip() == "hola-root", "sudo en medio del comando")
        c.run(f"cd {carpeta}")
        r = c.run("echo dato | sudo tee " + str(carpeta / "t.txt"))
        check((carpeta / "t.txt").read_text() == "dato\n",
              "sudo tee: la contraseña NO se escribe en el archivo")
        pedazos = []
        r = c.run("for i in 1 2 3; do echo l$i; sleep 0.3; done", on_chunk=pedazos.append)
        check(len(pedazos) >= 2 and "".join(pedazos).split() == ["l1", "l2", "l3"],
              f"salida en vivo ({len(pedazos)} pedazos)")
        threading.Timer(0.8, c.cancel).start()
        r = c.run("echo empiezo; sleep 30; echo nunca")
        check(r.cancelado and r.tiempo_ms < 5000 and "nunca" not in r.salida,
              f"Ctrl+C corta el comando ({r.tiempo_ms} ms)")
        r = c.run("echo sigo-vivo")
        check(r.salida.strip() == "sigo-vivo" and c.cwd == str(carpeta), "después de Ctrl+C sigue")
        check(c.complete("ls arch") == ["archivo_uno.txt"], "Tab: archivo")
        check(c.complete("ls su") == ["sub dir/"], "Tab: carpeta con /")
        check("echo" in c.complete("ech"), "Tab: comando")
        check(consola.common_prefix(["archivo_a", "archivo_b"]) == "archivo_", "prefijo común")
    check(consola.full_screen_hint("sudo vim /etc/hosts") is not None
          and consola.full_screen_hint("htop") is not None
          and consola.full_screen_hint("cat vim.txt") is None, "avisa vim/htop (sin TTY)")
    Equipo.delete(e.id)


def test_webhooks():  # propio
    """Receptor real (python3) instalado por SSH en el "servidor" de prueba."""
    import socket

    import httpx

    from modulos.kraken.models import Equipo, Receptor, WebhookRecibido
    from modulos.kraken.ssh.conexion import Sesion
    from modulos.kraken.webhooks import servicio

    print("Webhooks")
    puerto_ssh = start_ssh()
    e = Equipo.create(nombre="Servidor webhooks", host="127.0.0.1", ssh_usuario="edgar",
                      ssh_puerto=puerto_ssh, ssh_clave="secreto")
    with socket.socket() as s_:
        s_.bind(("127.0.0.1", 0))
        libre = s_.getsockname()[1]
    try:
        Receptor.create(nombre="X", equipo_id=e.id, puerto=80)
        check(False, "puerto 80 aceptado")
    except ValueError:
        check(True, "rechaza puertos < 1024 (sin root)")
    r = Receptor.create(nombre="Stripe pruebas", equipo_id=e.id, puerto=libre, max_guardados=10)
    check(len(r.clave) >= 20, f"clave secreta en la URL: {r.url('host')}")
    with Sesion(e) as ses:
        check(not servicio.status(ses, r).instalado, "antes de instalar: no instalado")
        estado = servicio.install(ses, r)
        check(estado.activo and Receptor.get(r.id).instalado, f"instala e inicia: {estado.texto}")
        cron = ses.run("crontab -l").texto
        check(f"ck-webhook-{r.clave}" in cron and "@reboot" in cron,
              "queda en crontab @reboot (vuelve solo si reinicia el servidor)")
        servicio.install(ses, Receptor.get(r.id))
        check(ses.run("crontab -l").texto.count("@reboot") == 1, "reinstalar no duplica crontab")
        url = r.url("127.0.0.1")
        resp = httpx.post(url + "/pagos?x=1", json={"evento": "pago", "monto": 10},
                          headers={"X-Firma": "abc"})
        check(resp.status_code == 200 and resp.json() == {"ok": True},
              "responde 200 {\"ok\": true}")
        check(httpx.get(f"http://127.0.0.1:{libre}/otra-cosa").status_code == 404,
              "otra ruta: 404 y no se guarda")
        httpx.put(url, content=b"\xff\x00\x01", headers={"Content-Type": "application/octet-stream"})
        httpx.post(url, data={"a": "1", "b": "dos"})
        n = servicio.fetch(ses, r)
        lista = WebhookRecibido.of(r.id)
        check(n == 3 and len(lista) == 3, f"trae lo nuevo: {n}")
        pago = next(w for w in lista if w.ruta == "/pagos")
        check(pago.metodo == "POST" and pago.query == "x=1" and json.loads(pago.body)["monto"] == 10
              and ["X-Firma", "abc"] in pago.headers and pago.ip == "127.0.0.1",
              "método, ruta, query, headers, body e IP")
        binario = next(w for w in lista if w.metodo == "PUT")
        check(binario.es_base64 and binario.tamano == 3, "body binario: en base64")
        check(servicio.fetch(ses, Receptor.get(r.id)) == 0, "segunda lectura: nada repetido")
        b = servicio.to_draft(pago)
        check(b.body_tipo == "json" and b.params == [{"clave": "x", "valor": "1", "activo": True}]
              and not any(h["clave"].lower() == "host" for h in b.headers),
              "a Cliente HTTP: JSON, params y sin headers de transporte")
        form = next(w for w in lista if w.metodo == "POST" and w.ruta == "/")
        check(servicio.to_draft(form).form[1] == {"clave": "b", "valor": "dos", "activo": True},
              "a Cliente HTTP: formulario")
        for k in range(12):
            httpx.post(url, json={"k": k})
        servicio.fetch(ses, Receptor.get(r.id))
        check(len(WebhookRecibido.of(r.id)) == 10, "guarda solo los últimos 10 (configurable)")
        ok, texto = servicio.test_send(Receptor.get(r.id), "127.0.0.1")
        check(ok, f"probar desde el cel: {texto}")
        Receptor.update(r.id, status=202, respuesta="recibido")
        servicio.apply(ses, Receptor.get(r.id))
        resp = httpx.post(url, content=b"x")
        check(resp.status_code == 202 and resp.text == "recibido"
              and resp.headers["content-type"].startswith("text/plain"),
              "editar la respuesta: reinicia con 202 «recibido»")
        estado = servicio.stop(ses, Receptor.get(r.id))
        check(estado.instalado and not estado.activo, "detener")
        ok, texto = servicio.test_send(Receptor.get(r.id), "127.0.0.1")
        check(not ok and "rechaza" in texto, f"detenido, probar lo explica: {texto[:50]}…")
        check(servicio.start(ses, Receptor.get(r.id)).activo, "volver a iniciar")
        n_antes = WebhookRecibido.unseen(r.id)
        httpx.post(url, content=b"y")
        servicio.fetch(ses, Receptor.get(r.id))
        check(WebhookRecibido.unseen(r.id) >= 1 and n_antes >= 1, "cuenta los no vistos")
        servicio.mark_seen(Receptor.get(r.id))
        check(WebhookRecibido.unseen(r.id) == 0, "marcar vistos")
        # Otro receptor en el MISMO puerto: el log lo explica
        otro = Receptor.create(nombre="Choca", equipo_id=e.id, puerto=libre)
        try:
            servicio.install(ses, otro)
            check(False, "dos receptores en el mismo puerto")
        except ValueError as ex:
            check("ocupado" in str(ex), f"puerto ocupado: {ex}")
        servicio.uninstall(ses, otro)
        servicio.uninstall(ses, Receptor.get(r.id))
        check(not servicio.status(ses, r).instalado and "ck-webhook" not in ses.run(
            "crontab -l").texto, "desinstalar: sin carpeta ni crontab")
        try:
            httpx.post(url, content=b"z", timeout=2)
            check(False, "sigue escuchando tras desinstalar")
        except httpx.ConnectError:
            check(True, "desinstalado: ya no escucha")
    Receptor.delete(r.id)
    check(not WebhookRecibido.of(r.id), "borrar el receptor borra lo recibido")


def prepare_server_db(tipo: str, host, puerto, usuario, clave) -> str:  # propio
    """Crea kraken_prueba_<tipo> con clientes (120), pedidos (30, FK) y una vista."""
    nombre = f"kraken_prueba_{tipo}"
    con = _admin(tipo, host, puerto, usuario, clave)
    cur = con.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {nombre}")
    cur.execute(f"CREATE DATABASE {nombre}")
    con.close()
    con = _admin(tipo, host, puerto, usuario, clave, nombre)
    cur = con.cursor()
    if tipo == "postgres":
        cur.execute("CREATE TABLE clientes (id serial PRIMARY KEY, nombre varchar(80) NOT NULL, "
                    "ciudad text, datos jsonb, saldo numeric(12,2))")
        cur.execute("CREATE SCHEMA ventas")
        cur.execute("CREATE TABLE ventas.pedidos (id serial PRIMARY KEY, "
                    "cliente_id int REFERENCES clientes(id), total numeric(10,2))")
        cur.execute("CREATE INDEX ix_pedidos_cliente ON ventas.pedidos(cliente_id)")
        cur.execute("CREATE VIEW grandes AS SELECT * FROM ventas.pedidos WHERE total > 100")
        for i in range(1, 121):
            cur.execute("INSERT INTO clientes (nombre, ciudad, datos, saldo) VALUES "
                        "(%s, %s, %s::jsonb, %s)", (f"Cliente {i}", "CDMX" if i % 2 else "Puebla",
                                                    '{"vip": true}' if i == 1 else None, i * 1.5))
        for i in range(1, 31):
            cur.execute("INSERT INTO ventas.pedidos (cliente_id, total) VALUES (%s, %s)",
                        (i, i * 10.5))
        cur.execute("ANALYZE")
    else:
        cur.execute("CREATE TABLE clientes (id int AUTO_INCREMENT PRIMARY KEY, nombre "
                    "varchar(80) NOT NULL, ciudad text, saldo decimal(12,2)) ENGINE=InnoDB")
        cur.execute("CREATE TABLE pedidos (id int AUTO_INCREMENT PRIMARY KEY, cliente_id int, "
                    "total decimal(10,2), INDEX ix_pedidos_cliente (cliente_id), "
                    "FOREIGN KEY (cliente_id) REFERENCES clientes(id)) ENGINE=InnoDB")
        cur.execute("CREATE VIEW grandes AS SELECT * FROM pedidos WHERE total > 100")
        for i in range(1, 121):
            cur.execute("INSERT INTO clientes (nombre, ciudad, saldo) VALUES (%s, %s, %s)",
                        (f"Cliente {i}", "CDMX" if i % 2 else "Puebla", i * 1.5))
        for i in range(1, 31):
            cur.execute("INSERT INTO pedidos (cliente_id, total) VALUES (%s, %s)", (i, i * 10.5))
        cur.execute("ANALYZE TABLE clientes, pedidos")
        cur.fetchall()
    con.close()
    return nombre


def test_server_db(tipo: str, variable: str):  # propio
    from modulos.kraken.models import ConexionSqlite, Equipo
    from modulos.kraken.sqlite import motores
    from modulos.kraken.sqlite import services as q
    from modulos.kraken.ssh.tunel import close_all

    valor = os.environ.get(variable)
    titulo = "PostgreSQL" if tipo == "postgres" else "MySQL / MariaDB"
    print(titulo)
    if not valor:
        print(f"  · sin servidor de prueba ({variable}=host:puerto:usuario:clave): se salta")
        return
    host, puerto, usuario, clave = valor.split(":", 3)
    puerto = int(puerto)
    nombre = prepare_server_db(tipo, host, puerto, usuario, clave)
    pedidos = "ventas.pedidos" if tipo == "postgres" else "pedidos"

    sin_base = q.save_server(None, nombre=f"Prueba {tipo}", tipo=tipo, host=host, puerto=puerto,
                             usuario=usuario, clave=clave, base_datos="")
    prueba = q.test_server(q.get_database(sin_base.id))
    check(prueba.ok and nombre in prueba.bases and prueba.version,
          f"probar conexión: {prueba.version} · {len(prueba.bases)} bases")
    mala = q.save_server(None, nombre="Mala", tipo=tipo, host=host, puerto=puerto,
                         usuario=usuario, clave="no-es", base_datos=nombre)
    prueba = q.test_server(q.get_database(mala.id))
    check(not prueba.ok and "contraseña incorrectos" in prueba.mensaje, prueba.mensaje)
    import socket
    libre = socket.socket(); libre.bind(("127.0.0.1", 0)); cerrado = libre.getsockname()[1]
    libre.close()
    ConexionSqlite.update(mala.id, puerto=cerrado)
    prueba = q.test_server(q.get_database(mala.id))
    check(not prueba.ok and "Nadie atiende" in prueba.mensaje, "puerto cerrado: explicado")

    c = q.save_server(sin_base.id, base_datos=nombre, tipo=tipo)
    base = q.get_database(c.id)
    check(base.solo_lectura and base.es_servidor and base.existe, "nuevo servidor: solo lectura")
    tablas = {t.nombre: t for t in q.tables(base)}
    check(tablas["clientes"].filas == 120 and pedidos in tablas and tablas["grandes"].tipo == "view",
          f"tablas y vistas ({', '.join(sorted(tablas))})")
    e = q.schema(base, pedidos)
    col = {x.nombre: x for x in e.columnas}
    check(col["id"].llave and col["cliente_id"].apunta_a == "clientes.id"
          and any(i[0] == "ix_pedidos_cliente" and i[2] == ["cliente_id"] for i in e.indices)
          and "CREATE TABLE" in e.sql, "esquema: llave, foránea, índice y CREATE")
    cols, filas, total = pagina = q.page_rows(base, "clientes", pagina=2)
    check(len(filas) == 20 and total == 120 and not pagina.aproximado, "página 3 de 50 en 50")
    cols, filas, total = q.page_rows(base, "clientes", buscar="puebla")
    check(total == 60, "búsqueda en todas las columnas (sin distinguir mayúsculas)")
    r = q.run(base, "SELECT ciudad, COUNT(*) AS n FROM clientes GROUP BY ciudad ORDER BY 1;")
    check(r.error is None and r.columnas == ["ciudad", "n"] and len(r.filas) == 2, "SELECT")
    r = q.run(base, "DELETE FROM clientes")
    check(r.error and "solo lectura" in r.error, f"solo lectura de verdad ({titulo} lo rechaza)")
    ConexionSqlite.update(c.id, solo_lectura=False)
    base = q.get_database(c.id)
    r = q.run(base, "UPDATE clientes SET ciudad = 'GDL' WHERE id <= 5; "
                    "INSERT INTO clientes (nombre) VALUES ('Nuevo')")
    check(r.error is None and r.cambios == 6 and r.sentencias == 2, "editable: varias sentencias")
    r = q.run(base, "UPDATE clientes SET ciudad = 'X'; INSERT INTO no_existe VALUES (1)")
    _, filas, _ = q.page_rows(base, "clientes", buscar="X")
    check(r.error and not any(f[2] == "X" for f in filas), "si una sentencia falla, no se aplica ninguna")
    if tipo == "postgres":
        _, filas, _ = q.page_rows(base, "clientes", buscar="vip")
        check(q.cell_text(filas[0][3]) == '{"vip": true}', "columna JSON se ve como JSON")
        anterior = motores.TIEMPO_MAX_S
        motores.TIEMPO_MAX_S = 1
        r = q.run(base, "SELECT pg_sleep(3)")
        motores.TIEMPO_MAX_S = anterior
        check(r.error and "tardó más" in r.error, "consulta muy lenta: se corta sola")
    check(q.cell_text(filas[0][-1]).replace(".", "").isdigit(), "números decimales")

    # --- por túnel SSH (el servidor falso hace de servidor SSH)
    equipo = Equipo.create(nombre=f"SSH {tipo}", host="127.0.0.1", ssh_usuario="edgar",
                           ssh_puerto=start_ssh(), ssh_clave="secreto")
    t = q.save_server(None, nombre=f"{tipo} por SSH", tipo=tipo, host="localhost",
                      puerto=puerto, usuario=usuario, clave=clave, base_datos=nombre,
                      ssh_equipo_id=equipo.id)
    base_t = q.get_database(t.id)
    prueba = q.test_server(base_t)
    tablas = q.tables(base_t)
    from modulos.kraken.ssh import tunel
    abiertos = len(tunel._ABIERTOS)
    q.page_rows(base_t, "clientes")
    check(prueba.ok and len(tablas) >= 3 and len(tunel._ABIERTOS) == abiertos == 1,
          "por túnel SSH (el túnel se reusa entre consultas)")
    close_all()
    check(not tunel._ABIERTOS, "cerrar túneles al salir")
    con = _admin(tipo, host, puerto, usuario, clave)
    con.cursor().execute(f"DROP DATABASE IF EXISTS {nombre}")
    con.close()


def main() -> int:  # propio
    database.init_db()
    print(f"Carpeta de prueba: {TMP}")
    base = start_server()
    test_http(base)
    test_postman()
    test_variables_ui()
    conexion_id = test_sqlite()
    test_backup(conexion_id)
    test_red(base)
    test_ssh()
    test_console()
    test_webhooks()
    test_server_db("postgres", "CK_TEST_PG")
    test_server_db("mysql", "CK_TEST_MYSQL")
    print()
    if FALLAS:
        print(f"✗ {len(FALLAS)} prueba(s) fallaron")
        return 1
    print("✓ Kraken Tools pasa todas las pruebas")
    return 0


if __name__ == "__main__":
    sys.exit(main())

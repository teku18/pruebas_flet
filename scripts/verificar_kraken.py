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
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(crudo)))
        self.end_headers()
        self.wfile.write(crudo)

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


def main() -> int:  # propio
    database.init_db()
    print(f"Carpeta de prueba: {TMP}")
    test_http(start_server())
    conexion_id = test_sqlite()
    test_backup(conexion_id)
    print()
    if FALLAS:
        print(f"✗ {len(FALLAS)} prueba(s) fallaron")
        return 1
    print("✓ Kraken Tools pasa todas las pruebas")
    return 0


if __name__ == "__main__":
    sys.exit(main())

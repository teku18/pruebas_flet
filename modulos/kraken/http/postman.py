"""
Importar y exportar en el formato de Postman.

  Colección  -> "Postman Collection v2.1" (también lee la v2.0)
  Entorno    -> "Postman Environment" (lo que da Postman en Environments > Export)

Cómo se acomoda lo de Postman en Kraken:

  Postman                         Kraken
  ──────────────────────────────  ─────────────────────────────────────────────
  colección                       colección
  carpetas (anidadas)             en el nombre: "Usuarios / Crear"  (al exportar
                                  se vuelven a armar las carpetas)
  variables de la colección       un entorno con el nombre de la colección
  auth de colección/carpeta       se copia a cada petición que la hereda
  body raw (JSON) / raw (texto)   JSON / Texto
  x-www-form-urlencoded           Formulario
  form-data                       Formulario (los campos de archivo se omiten)
  GraphQL                         JSON {"query": …, "variables": …}
  API Key                         un header o un param, según dónde iba
  scripts (pre-request / tests)   no se importan (se avisa cuántos)

Las {{variables}} se escriben igual en los dos: no se tocan.

Qué es / para qué / dónde: docs/notas_tecnicas.md (nota 52).
"""
import json
import uuid
from dataclasses import dataclass, field
from urllib.parse import unquote

from sqlalchemy import func

from modulos.kraken.http.services import Borrador, kv, save_request
from modulos.kraken.models import Coleccion, Entorno, Peticion
from modulos.kraken.models.http import METODOS

ESQUEMA_V21 = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
SEPARADOR = " / "      # carpeta / subcarpeta / petición


@dataclass
class Importado:
    colecciones: list[str] = field(default_factory=list)
    peticiones: int = 0
    entornos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    def summary(self) -> str:  # propio
        partes = []
        if self.colecciones:
            partes.append((f"{self.peticiones} petición" if self.peticiones == 1
                           else f"{self.peticiones} peticiones")
                          + f" en «{', '.join(self.colecciones)}»")
        if self.entornos:
            partes.append("entorno «" + "», «".join(self.entornos) + "»")
        return "Importado: " + "; ".join(partes) if partes else "No había nada que importar"


# ============================================================================
# Importar
# ============================================================================
def import_file(datos: bytes | str, nombre_archivo: str = "") -> Importado:  # propio
    """Lee un .json de Postman (colección o entorno) y lo guarda. ValueError si no lo es."""
    try:
        if isinstance(datos, bytes):   # Postman en Windows a veces guarda en UTF-16
            datos = datos.decode("utf-16" if datos[:2] in (b"\xff\xfe", b"\xfe\xff")
                                 else "utf-8-sig")
        doc = json.loads(datos)
    except (UnicodeDecodeError, json.JSONDecodeError) as ex:
        raise ValueError(f"{nombre_archivo or 'El archivo'} no es JSON válido ({ex})") from ex
    if not isinstance(doc, dict):
        raise ValueError("No parece un archivo de Postman")
    resultado = Importado()
    if ("requests" in doc or "folders" in doc or "v1" in str((doc.get("info") or {})
                                                                 .get("schema", ""))):
        raise ValueError("Es una colección v1 (muy vieja): en Postman expórtala de nuevo "
                         "como «Collection v2.1»")
    if isinstance(doc.get("item"), list):
        _import_collection(doc, resultado)
    elif isinstance(doc.get("values"), list):
        _import_environment(doc, resultado)
    elif isinstance(doc.get("collections"), list) or isinstance(doc.get("environments"), list):
        # "Export data" de Postman: todo junto
        for c in doc.get("collections") or []:
            if isinstance(c, dict) and "item" in c:
                _import_collection(c, resultado)
        for e in doc.get("environments") or []:
            if isinstance(e, dict):
                _import_environment(e, resultado)
    else:
        raise ValueError("No parece una colección ni un entorno de Postman")
    return resultado


def _free_name(modelo, nombre: str, largo: int) -> str:  # propio
    """'Mi API' -> 'Mi API (2)' si ya existe."""
    base = (nombre or "Importada").strip()[:largo] or "Importada"
    candidato, n = base, 2
    while modelo.search(func.lower(modelo.nombre) == candidato.lower()):
        sufijo = f" ({n})"
        candidato = base[:largo - len(sufijo)] + sufijo
        n += 1
    return candidato


def _text(valor) -> str:  # propio
    """Postman a veces guarda descripciones como {"content": …}."""
    if isinstance(valor, dict):
        return str(valor.get("content") or "")
    return "" if valor is None else str(valor)


def _rows(lista, clave="key", valor="value") -> list[dict]:  # propio
    filas = []
    for x in lista or []:
        if isinstance(x, dict) and (x.get(clave) or x.get(valor)):
            filas.append(kv(str(x.get(clave) or ""), _text(x.get(valor)),
                            not x.get("disabled", False) and x.get("enabled", True) is not False))
    return filas


def _import_collection(doc: dict, r: Importado) -> None:  # propio
    info = doc.get("info") if isinstance(doc.get("info"), dict) else {}
    nombre = _free_name(Coleccion, info.get("name") or doc.get("name") or "Postman", 80)
    coleccion = Coleccion.create(nombre=nombre, descripcion=_text(info.get("description")) or None)
    r.colecciones.append(nombre)
    contador = {"scripts": 0, "archivos": 0, "auth": set(), "secuencia": 0}

    def walk(items, ruta: list[str], auth_padre):  # propio
        for item in items or []:
            if not isinstance(item, dict):
                continue
            contador["scripts"] += _scripts(item.get("event"))
            auth = item.get("auth") if "auth" in item else auth_padre
            if "item" in item and "request" not in item:      # carpeta
                walk(item["item"], ruta + [str(item.get("name") or "Carpeta")], auth)
                continue
            peticion = item.get("request")
            if peticion is None:
                continue
            if isinstance(peticion, str):                      # v2: "request": "https://…"
                peticion = {"method": "GET", "url": peticion}
            b = _draft(peticion, peticion.get("auth", auth) if "auth" in peticion else auth,
                       contador)
            contador["secuencia"] += 10
            nombre_p = SEPARADOR.join(ruta + [str(item.get("name") or b.nombre_sugerido)])
            nueva = save_request(None, b, nombre_p[:120], coleccion.id)
            Peticion.update(nueva.id, secuencia=contador["secuencia"])   # mismo orden
            r.peticiones += 1

    contador["scripts"] += _scripts(doc.get("event"))
    walk(doc.get("item"), [], doc.get("auth"))
    _import_auth_notes(contador, r)

    variables = _rows(doc.get("variable"))
    if variables:
        entorno = _free_name(Entorno, nombre, 60)
        Entorno.create(nombre=entorno, variables=variables)
        r.entornos.append(entorno)
        r.avisos.append(f"Las variables de la colección quedaron en el entorno «{entorno}»: "
                        "actívalo en Entornos para usarlas.")


def _scripts(eventos) -> int:  # propio
    """Cuántos scripts trae (Postman los guarda de varias formas)."""
    total = 0
    for ev in eventos if isinstance(eventos, list) else []:
        script = ev.get("script") if isinstance(ev, dict) else None
        if isinstance(script, dict) and script.get("exec") or isinstance(script, str) and script:
            total += 1
    return total


def _import_auth_notes(contador: dict, r: Importado) -> None:  # propio
    if contador["scripts"]:
        r.avisos.append(f"{contador['scripts']} script(s) de Postman (pre-request/tests) no se "
                        "importaron: Kraken no corre scripts.")
    if contador["archivos"]:
        r.avisos.append(f"{contador['archivos']} campo(s) de archivo en form-data se omitieron.")
    if contador["auth"]:
        r.avisos.append("Autenticación no soportada (quedó en «Ninguna»): "
                        + ", ".join(sorted(contador["auth"])) + ".")


def _auth_values(auth: dict, tipo: str) -> dict:  # propio
    """{'token': '…'} de [{"key": "token", "value": "…"}] (v2.1) o de un dict (v2.0)."""
    datos = auth.get(tipo)
    if isinstance(datos, dict):
        return {k: _text(v) for k, v in datos.items()}
    return {x.get("key"): _text(x.get("value")) for x in datos or [] if isinstance(x, dict)}


def _split_url(url) -> tuple[str, list[dict]]:  # propio
    """URL de Postman (texto u objeto) -> (url sin query, params)."""
    if isinstance(url, dict):
        raw = str(url.get("raw") or "")
        if not raw:   # armarla con las piezas
            host = url.get("host") or ""
            host = ".".join(host) if isinstance(host, list) else str(host)
            ruta = url.get("path") or ""
            ruta = "/".join(str(p) for p in ruta) if isinstance(ruta, list) else str(ruta)
            raw = (f"{url['protocol']}://" if url.get("protocol") else "") + host + (
                f":{url['port']}" if url.get("port") else "") + (f"/{ruta}" if ruta else "")
        base = raw.split("?", 1)[0].split("#", 1)[0]
        if "query" in url:
            return base, _rows(url.get("query"))
    else:
        raw = str(url or "")
        base = raw.split("?", 1)[0].split("#", 1)[0]
    query = raw.split("?", 1)[1].split("#", 1)[0] if "?" in raw else ""
    params = []
    for parte in query.split("&") if query else []:
        clave, _, valor = parte.partition("=")
        params.append(kv(unquote(clave), unquote(valor)))
    return base, params


def _draft(p: dict, auth, contador: dict) -> Borrador:  # propio
    metodo = str(p.get("method") or "GET").upper()
    if metodo not in METODOS:
        metodo = "GET"
    url, params = _split_url(p.get("url"))
    b = Borrador(metodo=metodo, url=url, params=params, headers=_rows(p.get("header")))

    cuerpo = p.get("body") or {}
    modo = cuerpo.get("mode") if isinstance(cuerpo, dict) else None
    if modo == "raw" and cuerpo.get("raw"):
        lenguaje = ((cuerpo.get("options") or {}).get("raw") or {}).get("language", "")
        texto = str(cuerpo["raw"])
        es_json = lenguaje == "json" or (not lenguaje and texto.lstrip()[:1] in "{[")
        b.body_tipo, b.body = ("json" if es_json else "texto"), texto
    elif modo in ("urlencoded", "formdata"):
        filas = []
        for x in cuerpo.get(modo) or []:
            if x.get("type") == "file":
                contador["archivos"] += 1
                continue
            filas.append(kv(str(x.get("key") or ""), _text(x.get("value")),
                            not x.get("disabled", False)))
        b.body_tipo, b.form = "form", filas
    elif modo == "graphql":
        g = cuerpo.get("graphql") or {}
        variables = g.get("variables") or "{}"
        try:
            variables = json.loads(variables) if isinstance(variables, str) else variables
        except json.JSONDecodeError:
            variables = {}
        b.body_tipo = "json"
        b.body = json.dumps({"query": g.get("query", ""), "variables": variables},
                            ensure_ascii=False, indent=2)

    if isinstance(auth, dict):
        tipo = auth.get("type")
        valores = _auth_values(auth, tipo) if tipo else {}
        if tipo == "bearer":
            b.auth_tipo, b.auth_usuario = "bearer", valores.get("token", "")
        elif tipo == "basic":
            b.auth_tipo = "basic"
            b.auth_usuario, b.auth_clave = valores.get("username", ""), valores.get("password", "")
        elif tipo == "apikey":
            fila = kv(valores.get("key", "") or "X-API-Key", valores.get("value", ""))
            (b.params if valores.get("in") == "query" else b.headers).append(fila)
        elif tipo not in (None, "noauth"):
            contador["auth"].add(tipo)
    return b


def _import_environment(doc: dict, r: Importado) -> None:  # propio
    nombre = _free_name(Entorno, doc.get("name") or "Postman", 60)
    Entorno.create(nombre=nombre, variables=_rows(doc.get("values")))
    r.entornos.append(nombre)


# ============================================================================
# Exportar
# ============================================================================
def _query(params: list[dict]) -> list[dict]:  # propio
    filas = []
    for f in params or []:
        if not (f.get("clave") or "").strip():
            continue
        fila = {"key": f["clave"], "value": f.get("valor", "")}
        if not f.get("activo", True):
            fila["disabled"] = True
        filas.append(fila)
    return filas


def _url(url: str, params: list[dict]) -> dict:  # propio
    query = _query(params)
    activos = [q for q in query if not q.get("disabled")]
    raw = url + (("&" if "?" in url else "?") + "&".join(
        f"{q['key']}={q['value']}" for q in activos) if activos else "")
    resultado: dict = {"raw": raw}
    resto = url
    if "://" in resto:
        protocolo, resto = resto.split("://", 1)
        resultado["protocol"] = protocolo
    host, _, ruta = resto.partition("/")
    if host:
        resultado["host"] = host.split(".") if not host.startswith("{{") else [host]
    if ruta:
        resultado["path"] = ruta.split("/")
    if query:
        resultado["query"] = query
    return resultado


def _request(p: Peticion) -> dict:  # propio
    req: dict = {"method": p.metodo, "header": _query(p.headers), "url": _url(p.url or "",
                                                                                p.params)}
    if p.body_tipo == "json" and p.body:
        req["body"] = {"mode": "raw", "raw": p.body, "options": {"raw": {"language": "json"}}}
    elif p.body_tipo == "texto" and p.body:
        req["body"] = {"mode": "raw", "raw": p.body, "options": {"raw": {"language": "text"}}}
    elif p.body_tipo == "form" and p.form:
        req["body"] = {"mode": "urlencoded", "urlencoded": _query(p.form)}
    if p.auth_tipo == "bearer":
        req["auth"] = {"type": "bearer", "bearer": [
            {"key": "token", "value": p.auth_usuario or "", "type": "string"}]}
    elif p.auth_tipo == "basic":
        req["auth"] = {"type": "basic", "basic": [
            {"key": "username", "value": p.auth_usuario or "", "type": "string"},
            {"key": "password", "value": p.auth_clave or "", "type": "string"}]}
    return req


def export_collection(coleccion_id: int) -> tuple[str, bytes]:  # propio
    """(nombre de archivo, contenido) en Collection v2.1. "A / B" vuelven a ser carpetas."""
    c = Coleccion.get(coleccion_id)
    if c is None:
        raise ValueError("La colección ya no existe")
    raiz: list = []
    for p in c.peticiones:
        *carpetas, nombre = [x.strip() for x in p.nombre.split(SEPARADOR)] or [p.nombre]
        nivel = raiz
        for carpeta in carpetas:
            existente = next((x for x in nivel if x.get("name") == carpeta and "item" in x
                              and "request" not in x), None)
            if existente is None:
                existente = {"name": carpeta, "item": []}
                nivel.append(existente)
            nivel = existente["item"]
        nivel.append({"name": nombre or p.nombre, "request": _request(p), "response": []})
    doc = {"info": {"_postman_id": str(uuid.uuid4()), "name": c.nombre,
                    "description": c.descripcion or "", "schema": ESQUEMA_V21},
           "item": raiz}
    return f"{_file_name(c.nombre)}.postman_collection.json", _dump(doc)


def export_environment(entorno_id: int) -> tuple[str, bytes]:  # propio
    e = Entorno.get(entorno_id)
    if e is None:
        raise ValueError("El entorno ya no existe")
    doc = {"id": str(uuid.uuid4()), "name": e.nombre,
           "values": [{"key": f["clave"], "value": f.get("valor", ""), "type": "default",
                       "enabled": bool(f.get("activo", True))}
                      for f in e.variables or [] if (f.get("clave") or "").strip()],
           "_postman_variable_scope": "globals" if e.es_global else "environment"}
    return f"{_file_name(e.nombre)}.postman_environment.json", _dump(doc)


def _file_name(nombre: str) -> str:  # propio
    limpio = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in nombre).strip()
    return limpio.replace(" ", "_") or "kraken"


def _dump(doc: dict) -> bytes:  # propio
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")

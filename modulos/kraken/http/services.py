"""
Lógica del cliente HTTP (el "cocinero"):

  Borrador         la petición como está en el editor (guardada o no)
  variables()      Globales + el entorno elegido  -> {"base_url": "…", …}
  substitute()     "{{base_url}}/users" -> "https://api.x.com/users"
  send()           arma la petición, la manda con httpx (async) y la anota
                   en el historial (recortada según tus ajustes)
  to_curl()        la petición como comando curl (para pegar en la terminal)
  parse_curl()     al revés: pegas un `curl …` y sale un Borrador
  pretty()         JSON bonito (con sangría)

Por qué httpx y no requests: httpx tiene versión async (await client.send),
así la pantalla no se congela mientras llega la respuesta, y se puede cancelar.
"""
import asyncio
import base64
import json
import re
import shlex
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx
from sqlalchemy import delete, func, select

from core import APP_VERSION
from core.database import SessionLocal
from modulos.kraken.models import Ajustes, Coleccion, Entorno, HistorialHttp, Peticion

LIMITE_LECTURA = 50 * 1024 * 1024   # nunca se lee más de 50 MB de una respuesta
VARIABLE = re.compile(r"\{\{\s*([\w.\-]+)\s*\}\}")
BINARIOS = ("image/", "audio/", "video/", "application/octet-stream", "application/pdf",
            "application/zip", "application/gzip", "font/")


# ============================================================================
# El borrador (lo que hay en el editor)
# ============================================================================
def kv(clave: str = "", valor: str = "", activo: bool = True) -> dict:  # propio
    """Una fila clave/valor de params, headers, formulario o variables."""
    return {"clave": clave, "valor": valor, "activo": activo}


@dataclass
class Borrador:
    metodo: str = "GET"
    url: str = ""
    params: list[dict] = field(default_factory=list)
    headers: list[dict] = field(default_factory=list)
    body_tipo: str = "ninguno"
    body: str = ""
    form: list[dict] = field(default_factory=list)
    auth_tipo: str = "ninguna"
    auth_usuario: str = ""
    auth_clave: str = ""

    @classmethod
    def from_request(cls, p: Peticion) -> "Borrador":  # propio
        return cls(metodo=p.metodo, url=p.url or "", params=list(p.params or []),
                   headers=list(p.headers or []), body_tipo=p.body_tipo, body=p.body or "",
                   form=list(p.form or []), auth_tipo=p.auth_tipo,
                   auth_usuario=p.auth_usuario or "", auth_clave=p.auth_clave or "")

    @classmethod
    def from_dict(cls, datos: dict | None) -> "Borrador":  # propio
        validos = {k: v for k, v in (datos or {}).items() if k in cls.__dataclass_fields__}
        return cls(**validos)

    def to_dict(self) -> dict:  # propio
        return asdict(self)

    @property
    def nombre_sugerido(self) -> str:  # propio
        """'GET /users/2' (para cuando guardas sin pensar un nombre)."""
        ruta = urlsplit(self.url if "://" in self.url else f"http://{self.url}").path or "/"
        return f"{self.metodo} {ruta}"[:120]


def active_rows(filas: list[dict] | None) -> list[tuple[str, str]]:  # propio
    """Solo las filas con casilla y con clave."""
    return [(f.get("clave", "").strip(), f.get("valor", "") or "") for f in filas or []
            if f.get("activo", True) and (f.get("clave") or "").strip()]


# ============================================================================
# Variables {{así}}
# ============================================================================
def variables() -> dict[str, str]:  # propio
    """Globales y, encima, las del entorno elegido (si ambos la tienen, gana el entorno)."""
    resultado = dict(active_rows(Entorno.globals_().variables))
    entorno_id = Ajustes.current().entorno_id
    entorno = Entorno.get(entorno_id) if entorno_id else None
    if entorno is not None:
        resultado.update(active_rows(entorno.variables))
    return resultado


def substitute(texto: str | None, valores: dict[str, str]) -> str:  # propio
    """Reemplaza {{nombre}}; las que no existen se quedan tal cual (así se notan)."""
    if not texto:
        return texto or ""
    return VARIABLE.sub(lambda m: valores.get(m.group(1), m.group(0)), texto)


def split_variables(texto: str | None) -> list[tuple[str, str | None]]:  # propio
    """'{{base}}/users' -> [('{{base}}', 'base'), ('/users', None)] (para pintarlas)."""
    partes, inicio = [], 0
    for m in VARIABLE.finditer(texto or ""):
        if m.start() > inicio:
            partes.append((texto[inicio:m.start()], None))
        partes.append((m.group(0), m.group(1)))
        inicio = m.end()
    if inicio < len(texto or ""):
        partes.append((texto[inicio:], None))
    return partes


def variable_at_cursor(texto: str, cursor: int | None) -> tuple[int, str] | None:  # propio
    """Si estás escribiendo una variable ('…{{ba|'), (posición de las llaves, 'ba')."""
    texto = texto or ""
    cursor = len(texto) if cursor is None or not 0 <= cursor <= len(texto) else cursor
    antes = texto[:cursor]
    inicio = antes.rfind("{{")
    if inicio < 0:
        return None
    parcial = antes[inicio + 2:]
    if "}" in parcial or any(c.isspace() for c in parcial) or "{" in parcial:
        return None
    return inicio, parcial


def suggest_variables(parcial: str, valores: dict[str, str],  # propio
                      limite: int = 20) -> list[tuple[str, str]]:
    """Las variables que empiezan con lo escrito primero, luego las que lo contienen."""
    p = parcial.lower()
    empiezan = sorted(k for k in valores if k.lower().startswith(p))
    contienen = sorted(k for k in valores if p in k.lower() and k not in empiezan)
    return [(k, valores[k]) for k in (empiezan + contienen)[:limite]]


def insert_variable(texto: str, inicio: int, cursor: int | None,  # propio
                    nombre: str) -> tuple[str, int]:
    """Reemplaza '{{ba' por '{{base}}' (sin duplicar '}}' si ya estaban). -> (texto, cursor)."""
    texto = texto or ""
    cursor = len(texto) if cursor is None or not 0 <= cursor <= len(texto) else cursor
    despues = texto[cursor:]
    if despues.startswith("}}"):
        despues = despues[2:]
    elif despues.startswith("}"):
        despues = despues[1:]
    nuevo = texto[:inicio] + "{{" + nombre + "}}"
    return nuevo + despues, len(nuevo)


def missing_variables(b: Borrador, valores: dict[str, str]) -> list[str]:  # propio
    """Variables que usa la petición y no están definidas."""
    textos = [b.url, b.body, b.auth_usuario, b.auth_clave]
    for fila in (*b.params, *b.headers, *b.form):
        textos += [fila.get("clave", ""), fila.get("valor", "")]
    usadas = {m.group(1) for t in textos if t for m in VARIABLE.finditer(t)}
    return sorted(usadas - valores.keys())


# ============================================================================
# Armar
# ============================================================================
@dataclass
class Lista:
    """La petición ya resuelta: lo que de verdad sale por la red."""
    metodo: str
    url: str
    headers: list[tuple[str, str]]
    contenido: bytes | None = None
    formulario: dict[str, list[str]] | None = None

    @property
    def cuerpo_texto(self) -> str | None:  # propio
        if self.contenido is not None:
            return self.contenido.decode("utf-8", errors="replace")
        if self.formulario:
            return "&".join(f"{k}={v}" for k, vs in self.formulario.items() for v in vs)
        return None


def _with_scheme(url: str) -> str:  # propio
    url = url.strip()
    return url if "://" in url or not url else f"http://{url}"


def _has_header(headers: list[tuple[str, str]], nombre: str) -> bool:  # propio
    return any(k.lower() == nombre.lower() for k, _ in headers)


def build(b: Borrador, valores: dict[str, str] | None = None) -> Lista:  # propio
    """Reemplaza variables, suma params a la URL, pone body y auth."""
    valores = variables() if valores is None else valores
    sub = lambda t: substitute(t, valores)  # noqa: E731
    url = _with_scheme(sub(b.url))
    if not url:
        raise ValueError("Escribe la URL")
    params = [(sub(k), sub(v)) for k, v in active_rows(b.params)]
    if params:
        url = str(httpx.URL(url).copy_merge_params(params))
    headers = [(sub(k), sub(v)) for k, v in active_rows(b.headers)]

    lista = Lista(b.metodo, url, headers)
    if b.body_tipo == "json" and b.body.strip():
        lista.contenido = sub(b.body).encode("utf-8")
        if not _has_header(headers, "content-type"):
            headers.append(("Content-Type", "application/json"))
    elif b.body_tipo == "texto" and b.body:
        lista.contenido = sub(b.body).encode("utf-8")
        if not _has_header(headers, "content-type"):
            headers.append(("Content-Type", "text/plain; charset=utf-8"))
    elif b.body_tipo == "form":
        formulario: dict[str, list[str]] = {}
        for k, v in active_rows(b.form):
            formulario.setdefault(sub(k), []).append(sub(v))
        lista.formulario = formulario or None

    if b.auth_tipo == "bearer" and b.auth_usuario.strip():
        headers.append(("Authorization", f"Bearer {sub(b.auth_usuario).strip()}"))
    elif b.auth_tipo == "basic" and (b.auth_usuario or b.auth_clave):
        par = f"{sub(b.auth_usuario)}:{sub(b.auth_clave)}".encode("utf-8")
        headers.append(("Authorization", f"Basic {base64.b64encode(par).decode('ascii')}"))
    if not _has_header(headers, "user-agent"):
        headers.append(("User-Agent", f"ControlKraken/{APP_VERSION}"))
    return lista


# ============================================================================
# Mandar
# ============================================================================
@dataclass
class Resultado:
    url: str
    metodo: str
    status: int | None = None
    motivo: str = ""
    tiempo_ms: int = 0
    tamano: int = 0
    headers: list[tuple[str, str]] = field(default_factory=list)
    req_headers: list[tuple[str, str]] = field(default_factory=list)
    texto: str = ""              # el cuerpo como texto (o una descripción si es binario)
    datos: bytes = b""           # el cuerpo tal cual (para "guardar como archivo")
    tipo: str = ""               # Content-Type
    incompleto: bool = False     # pasó de LIMITE_LECTURA
    error: str | None = None
    historial_id: int | None = None

    @property
    def es_json(self) -> bool:  # propio
        return "json" in self.tipo.lower() or _looks_json(self.texto)

    @property
    def es_binario(self) -> bool:  # propio
        return self.tipo.lower().startswith(BINARIOS)


def _looks_json(texto: str) -> bool:  # propio
    t = (texto or "").lstrip()[:1]
    if t not in ("{", "["):
        return False
    try:
        json.loads(texto)
        return True
    except ValueError:
        return False


def _decode(datos: bytes, respuesta: httpx.Response) -> str:  # propio
    tipo = respuesta.headers.get("content-type", "")
    if tipo.lower().startswith(BINARIOS):
        from core.storage import human_size
        return f"(contenido binario: {human_size(len(datos))}, {tipo})"
    try:
        return datos.decode(respuesta.encoding or "utf-8", errors="replace")
    except LookupError:  # el servidor dijo un charset que Python no conoce
        return datos.decode("utf-8", errors="replace")


def _friendly_error(ex: Exception, timeout: int) -> str:  # propio
    if isinstance(ex, httpx.TimeoutException):
        return f"Se acabó el tiempo de espera ({timeout} s). Súbelo en Ajustes si hace falta."
    if isinstance(ex, (httpx.UnsupportedProtocol, httpx.InvalidURL)):
        return f"URL no válida: {ex}"
    if isinstance(ex, httpx.ConnectError):
        texto = str(ex)
        if "CERTIFICATE" in texto.upper() or "SSL" in texto.upper():
            return f"Problema con el certificado HTTPS: {texto}"
        return f"No se pudo conectar: {texto or 'el servidor no responde'}"
    return f"{type(ex).__name__}: {ex}"


async def send(b: Borrador, peticion_id: int | None = None) -> Resultado:  # propio
    """
    Manda la petición y la anota en el historial. Nunca lanza por errores de
    red: el error viene en Resultado.error. Sí deja pasar la cancelación
    (asyncio.CancelledError) para que el botón Cancelar funcione.
    """
    ajustes = Ajustes.current()
    try:
        lista = build(b)
    except ValueError as ex:
        return Resultado(url=b.url, metodo=b.metodo, error=str(ex))
    r = Resultado(url=lista.url, metodo=lista.metodo, req_headers=list(lista.headers))
    inicio = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=ajustes.timeout_s, follow_redirects=True) as cliente:
            peticion = cliente.build_request(lista.metodo, lista.url, headers=lista.headers,
                                             content=lista.contenido, data=lista.formulario)
            r.req_headers = list(peticion.headers.items())  # con los que pone httpx
            respuesta = await cliente.send(peticion, stream=True)
            try:
                trozos, total = [], 0
                async for trozo in respuesta.aiter_bytes():
                    trozos.append(trozo)
                    total += len(trozo)
                    if total > LIMITE_LECTURA:
                        r.incompleto = True
                        break
            finally:
                await respuesta.aclose()
        r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
        r.datos = b"".join(trozos)[:LIMITE_LECTURA]
        r.tamano = len(r.datos)
        r.status, r.motivo = respuesta.status_code, respuesta.reason_phrase
        r.headers = list(respuesta.headers.items())
        r.tipo = respuesta.headers.get("content-type", "")
        r.url = str(respuesta.url)  # la final, si hubo redirecciones
        r.texto = _decode(r.datos, respuesta)
    except asyncio.CancelledError:
        raise
    except Exception as ex:  # noqa: BLE001  (cualquier problema de red)
        r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
        r.error = _friendly_error(ex, ajustes.timeout_s)
    r.historial_id = _record(b, lista, r, peticion_id, ajustes)
    return r


# ============================================================================
# Historial
# ============================================================================
def cut(texto: str, max_kb: int) -> tuple[str, bool]:  # propio
    """Recorta a max_kb (0 = sin recortar). Regresa (texto, ¿se recortó?)."""
    if not max_kb:
        return texto, False
    datos = texto.encode("utf-8")
    limite = max_kb * 1024
    if len(datos) <= limite:
        return texto, False
    return datos[:limite].decode("utf-8", errors="ignore"), True


def _record(b: Borrador, lista: Lista, r: Resultado, peticion_id: int | None,  # propio
            ajustes: Ajustes) -> int:
    cuerpo, recortado = cut(r.texto, ajustes.respuesta_max_kb)
    req_body, _ = cut(lista.cuerpo_texto or "", ajustes.respuesta_max_kb)
    fila = HistorialHttp.create(
        peticion_id=peticion_id, metodo=lista.metodo, url=r.url,
        req_headers=[list(h) for h in r.req_headers], req_body=req_body or None,
        borrador=b.to_dict(), status=r.status, motivo=(r.motivo or None) and r.motivo[:80],
        tiempo_ms=r.tiempo_ms, tamano=r.tamano, resp_headers=[list(h) for h in r.headers],
        resp_body=cuerpo or None, recortado=recortado or r.incompleto, error=r.error,
    )
    prune_history(ajustes.historial_max)
    return fila.id


def prune_history(maximo: int) -> int:  # propio
    """Deja solo los `maximo` envíos más nuevos (0 = no borra). Regresa cuántos borró."""
    if not maximo:
        return 0
    with SessionLocal() as session:
        sobran = list(session.scalars(select(HistorialHttp.id)
                                      .order_by(HistorialHttp.creado_en.desc(),
                                                HistorialHttp.id.desc())
                                      .offset(maximo)))
        if sobran:
            session.execute(delete(HistorialHttp).where(HistorialHttp.id.in_(sobran)))
            session.commit()
        return len(sobran)


def history(limite: int = 300) -> list[HistorialHttp]:  # propio
    """Lo más nuevo primero (la pantalla muestra hasta `limite`)."""
    with SessionLocal() as session:
        return list(session.scalars(select(HistorialHttp).order_by(
            HistorialHttp.creado_en.desc(), HistorialHttp.id.desc()).limit(limite)))


def history_stats() -> tuple[int, int]:  # propio
    """(envíos guardados, bytes que ocupan sus cuerpos) para Ajustes."""
    with SessionLocal() as session:
        n, peso = session.execute(select(
            func.count(HistorialHttp.id),
            func.coalesce(func.sum(func.length(HistorialHttp.resp_body)), 0)
            + func.coalesce(func.sum(func.length(HistorialHttp.req_body)), 0))).one()
        return n, int(peso or 0)


def clear_history() -> None:  # propio
    with SessionLocal() as session:
        session.execute(delete(HistorialHttp))
        session.commit()


def result_from_history(h: HistorialHttp) -> Resultado:  # propio
    """Un envío del historial como si acabara de llegar (para verlo de nuevo)."""
    headers = [tuple(x) for x in h.resp_headers or []]
    tipo = next((v for k, v in headers if k.lower() == "content-type"), "")
    return Resultado(url=h.url, metodo=h.metodo, status=h.status, motivo=h.motivo or "",
                     tiempo_ms=h.tiempo_ms or 0, tamano=h.tamano or 0, headers=headers,
                     req_headers=[tuple(x) for x in h.req_headers or []],
                     texto=h.resp_body or "", tipo=tipo, incompleto=h.recortado,
                     error=h.error, historial_id=h.id)


# ============================================================================
# Colecciones y peticiones guardadas
# ============================================================================
def tree() -> tuple[list[Coleccion], list[Peticion]]:  # propio
    """(colecciones con sus peticiones, peticiones sin colección)."""
    return Coleccion.search_all(), Peticion.search(Peticion.coleccion_id.is_(None))


def save_request(peticion_id: int | None, b: Borrador, nombre: str | None = None,  # propio
                 coleccion_id: int | None | type(...) = ...) -> Peticion:
    """Crea o actualiza. `coleccion_id=...` (sin pasar) = no la mueve."""
    valores = dict(metodo=b.metodo, url=b.url.strip(), params=b.params, headers=b.headers,
                   body_tipo=b.body_tipo, body=b.body or None, form=b.form,
                   auth_tipo=b.auth_tipo, auth_usuario=b.auth_usuario or None,
                   auth_clave=b.auth_clave or None, actualizado_en=datetime.now())
    if nombre is not None:
        valores["nombre"] = nombre.strip()
    if coleccion_id is not ...:
        valores["coleccion_id"] = coleccion_id
    if peticion_id is None:
        valores.setdefault("nombre", b.nombre_sugerido)
        return Peticion.create(**valores)
    return Peticion.update(peticion_id, **valores)


def duplicate(peticion_id: int) -> Peticion:  # propio
    p = Peticion.get(peticion_id)
    return save_request(None, Borrador.from_request(p), f"{p.nombre} (copia)"[:120],
                        p.coleccion_id)


def create_collection(nombre: str) -> Coleccion:  # propio
    Coleccion.check_unique(nombre)
    return Coleccion.create(nombre=nombre.strip())


def rename_collection(coleccion_id: int, nombre: str) -> Coleccion:  # propio
    Coleccion.check_unique(nombre, excluir_id=coleccion_id)
    return Coleccion.update(coleccion_id, nombre=nombre.strip())


# ============================================================================
# Texto: JSON bonito y cURL
# ============================================================================
def pretty(texto: str) -> str:  # propio
    """JSON con sangría; si no es JSON, igual que llegó."""
    try:
        return json.dumps(json.loads(texto), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return texto


def to_curl(b: Borrador, con_variables: bool = True) -> str:  # propio
    """La petición como comando curl, con las variables ya reemplazadas."""
    lista = build(b, variables() if con_variables else {})
    partes = ["curl"]
    if lista.metodo != "GET" or lista.contenido is not None or lista.formulario:
        partes += ["-X", lista.metodo]
    partes.append(shlex.quote(lista.url))
    for k, v in lista.headers:
        if k.lower() == "user-agent" and v.startswith("ControlKraken/"):
            continue  # el que pone la app no hace falta copiarlo
        partes += ["-H", shlex.quote(f"{k}: {v}")]
    if lista.contenido is not None:
        partes += ["--data-raw", shlex.quote(lista.contenido.decode("utf-8", errors="replace"))]
    for k, vs in (lista.formulario or {}).items():
        for v in vs:
            partes += ["--data-urlencode", shlex.quote(f"{k}={v}")]
    return " \\\n  ".join(_group_flags(partes))


def _group_flags(partes: list[str]) -> list[str]:  # propio
    """['curl','-X','POST','url','-H','a'] -> ['curl -X POST url', '-H a'] (una opción por línea)."""
    lineas, actual = [], []
    for k, p in enumerate(partes):
        if p.startswith("-") and p not in ("-X",) and actual and k > 0 and partes[k - 1] != "-X":
            lineas.append(" ".join(actual))
            actual = []
        actual.append(p)
    lineas.append(" ".join(actual))
    return lineas


_CON_VALOR = {"-X", "--request", "-H", "--header", "-d", "--data", "--data-raw",
              "--data-binary", "--data-ascii", "--data-urlencode", "--json", "-u", "--user",
              "-F", "--form", "--url", "-A", "--user-agent", "-e", "--referer", "-b",
              "--cookie", "-o", "--output", "-m", "--max-time", "--connect-timeout",
              "-x", "--proxy", "-w", "--write-out"}


def parse_curl(texto: str) -> Borrador:  # propio
    """
    `curl -X POST https://x.com/api?a=1 -H 'Authorization: Bearer t' -d '{"x":1}'`
    -> Borrador listo para el editor. Entiende lo que copian Chrome ("Copy as
    cURL"), Postman y la documentación de casi cualquier API. Lo demás
    (-s, -L, -k, --compressed…) se ignora.
    """
    limpio = texto.strip().replace("\\\r\n", " ").replace("\\\n", " ").replace("^\n", " ")
    if not limpio:
        raise ValueError("Pega un comando curl")
    try:
        tokens = shlex.split(limpio)
    except ValueError as ex:
        raise ValueError(f"No se pudo leer el comando (¿comillas sin cerrar?): {ex}") from ex
    if not tokens or tokens[0] != "curl":
        raise ValueError("El texto debe empezar con  curl")

    b = Borrador()
    metodo, url, datos, form, get = None, None, [], [], False
    k = 1
    while k < len(tokens):
        t = tokens[k]
        valor = None
        if t.startswith("--") and "=" in t and t.split("=", 1)[0] in _CON_VALOR:
            t, valor = t.split("=", 1)
        elif t in _CON_VALOR:
            k += 1
            valor = tokens[k] if k < len(tokens) else ""
        if t in ("-X", "--request"):
            metodo = valor.upper()
        elif t in ("-H", "--header"):
            clave, _, v = valor.partition(":")
            b.headers.append(kv(clave.strip(), v.strip()))
        elif t in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            datos.append(valor)
        elif t == "--data-urlencode":
            clave, _, v = valor.partition("=")
            form.append(kv(clave, v))
        elif t == "--json":
            datos.append(valor)
            b.body_tipo = "json"
        elif t in ("-F", "--form"):
            clave, _, v = valor.partition("=")
            form.append(kv(clave, v))
        elif t in ("-u", "--user"):
            usuario, _, clave = valor.partition(":")
            b.auth_tipo, b.auth_usuario, b.auth_clave = "basic", usuario, clave
        elif t in ("-A", "--user-agent"):
            b.headers.append(kv("User-Agent", valor))
        elif t in ("-e", "--referer"):
            b.headers.append(kv("Referer", valor))
        elif t in ("-b", "--cookie"):
            b.headers.append(kv("Cookie", valor))
        elif t in ("-G", "--get"):
            get = True
        elif t == "--url":
            url = valor
        elif not t.startswith("-") and url is None:
            url = t
        k += 1

    if not url:
        raise ValueError("No encontré la URL en el comando")
    # Los ?a=1&b=2 de la URL pasan a la pestaña Params (como en Postman)
    partes = urlsplit(url)
    if partes.query:
        b.params = [kv(c, v) for c, v in parse_qsl(partes.query, keep_blank_values=True)]
        url = urlunsplit(partes._replace(query=""))
    b.url = url

    if get and (datos or form):  # -G: los datos van en la URL
        for d in datos:
            b.params += [kv(c, v) for c, v in parse_qsl(d, keep_blank_values=True)]
        b.params += form
        datos, form = [], []
    if datos:
        b.body = "&".join(datos)
        tipo = next((h["valor"] for h in b.headers if h["clave"].lower() == "content-type"), "")
        if b.body_tipo != "json":
            if "json" in tipo.lower() or _looks_json(b.body):
                b.body_tipo = "json"
            elif "x-www-form-urlencoded" in tipo.lower() or (not tipo and "=" in b.body
                                                            and not b.body.lstrip().startswith(("{", "["))):
                b.body_tipo = "form"
                b.form = [kv(c, v) for c, v in parse_qsl(b.body, keep_blank_values=True)]
                b.body = ""
            else:
                b.body_tipo = "texto"
        if b.body_tipo == "json":
            b.body = pretty(b.body)
    elif form:
        b.body_tipo, b.form = "form", form
    # Un "Authorization: Bearer …" pasa a la pestaña Auth
    for h in list(b.headers):
        if h["clave"].lower() == "authorization" and h["valor"].lower().startswith("bearer "):
            b.auth_tipo, b.auth_usuario = "bearer", h["valor"][7:].strip()
            b.headers.remove(h)
    b.metodo = metodo or ("POST" if (b.body or b.form) else "GET")
    if b.metodo not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        raise ValueError(f"Método no soportado: {b.metodo}")
    return b

"""
Lógica del explorador SQLite (el "cocinero"):

  databases()      la de ControlKraken (siempre arriba) + las que agregaste
  add_database()   copia un .db a data/kraken/bases/ y lo registra
  tables()         tablas y vistas con su número de filas
  schema()         columnas, llaves, índices y el CREATE de una tabla
  page_rows()      filas de 50 en 50 (con búsqueda en todas las columnas)
  run()            ejecuta tu SQL y lo anota en el historial de esa base
  to_csv()         un resultado -> CSV que abre Excel

Solo lectura de verdad: la conexión se abre con  file:…?mode=ro  (SQLite
mismo rechaza cualquier escritura: "attempt to write a readonly database").
La BD de ControlKraken SIEMPRE se abre así, además con PRAGMA query_only.

Se usa sqlite3 (viene con Python) y no SQLAlchemy: aquí no hay modelos, son
bases cualesquiera.
"""
import csv
import io
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import delete, select

from core.database import DB_PATH, SessionLocal
from core.storage import save_file
from modulos.kraken.models import BASES_DIR, ConexionSqlite, ConsultaSqlite

POR_PAGINA = 50
MAX_FILAS = 1000            # filas de un resultado de SQL que se traen a la pantalla
HISTORIAL_POR_BASE = 100    # consultas recientes por base (las favoritas no cuentan)
ENCABEZADO = b"SQLite format 3\x00"
LECTURA = ("SELECT", "WITH", "PRAGMA", "EXPLAIN", "VALUES")


# ============================================================================
# Las bases
# ============================================================================
@dataclass
class BaseInfo:
    id: int | None           # None = la BD de ControlKraken
    nombre: str
    ruta: Path
    solo_lectura: bool
    respaldar: bool
    origen: str | None = None

    @property
    def es_app(self) -> bool:  # propio
        return self.id is None

    @property
    def existe(self) -> bool:  # propio
        return self.ruta.is_file()

    @property
    def tamano(self) -> int:  # propio
        return self.ruta.stat().st_size if self.existe else 0


APP = BaseInfo(None, "ControlKraken (esta app)", DB_PATH, True, True)


def _info(c: ConexionSqlite) -> BaseInfo:  # propio
    return BaseInfo(c.id, c.nombre, c.ruta, c.solo_lectura, c.respaldar, c.origen)


def databases() -> list[BaseInfo]:  # propio
    return [APP, *(_info(c) for c in ConexionSqlite.search_all())]


def get_database(conexion_id: int | None) -> BaseInfo | None:  # propio
    if conexion_id is None:
        return APP
    c = ConexionSqlite.get(conexion_id)
    return _info(c) if c else None


def is_sqlite(datos: bytes) -> bool:  # propio
    return datos[:16] == ENCABEZADO


def add_database(nombre_archivo: str, datos: bytes | None = None,  # propio
                 origen: Path | None = None) -> ConexionSqlite:
    """Copia el archivo a data/kraken/bases/ (el original no se toca)."""
    if datos is None and origen is not None:
        datos = Path(origen).read_bytes()
    if not datos:
        raise ValueError("El archivo está vacío")
    if not is_sqlite(datos):
        raise ValueError("Ese archivo no es una base SQLite")
    relativa = save_file(None, datos, BASES_DIR, Path(nombre_archivo).name)
    nombre = Path(nombre_archivo).stem[:80] or "Base"
    return ConexionSqlite.create(nombre=nombre, archivo=str(relativa).replace("\\", "/"),
                                 origen=str(origen) if origen else nombre_archivo)


def connect(base: BaseInfo) -> sqlite3.Connection:  # propio
    if not base.existe:
        raise ValueError("El archivo de esta base no está en este equipo "
                         "(se marcó «no respaldar» y vienes de otro equipo)")
    if base.solo_lectura or base.es_app:
        con = sqlite3.connect(f"{base.ruta.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
        con.execute("PRAGMA query_only = 1")
    else:
        con = sqlite3.connect(base.ruta, timeout=5)
    return con


def _q(nombre: str) -> str:  # propio
    """Nombre de tabla/columna entre comillas dobles (por si trae espacios o es palabra de SQL)."""
    return '"' + nombre.replace('"', '""') + '"'


# ============================================================================
# Tablas y esquema
# ============================================================================
@dataclass
class Tabla:
    nombre: str
    tipo: str          # "table" | "view"
    filas: int | None  # None si no se pudo contar (vista rota, etc.)


def tables(base: BaseInfo) -> list[Tabla]:  # propio
    con = connect(base)
    try:
        nombres = con.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        resultado = []
        for nombre, tipo in nombres:
            try:
                filas = con.execute(f"SELECT COUNT(*) FROM {_q(nombre)}").fetchone()[0]
            except sqlite3.Error:
                filas = None
            resultado.append(Tabla(nombre, tipo, filas))
        return resultado
    finally:
        con.close()


@dataclass
class Columna:
    nombre: str
    tipo: str
    obligatoria: bool
    defecto: str | None
    llave: bool                 # parte de la llave primaria
    apunta_a: str | None = None  # "proyectos.id" si es llave foránea


@dataclass
class Esquema:
    columnas: list[Columna]
    indices: list[tuple[str, bool, list[str]]]   # (nombre, único, columnas)
    sql: str


def schema(base: BaseInfo, tabla: str) -> Esquema:  # propio
    con = connect(base)
    try:
        foraneas = {f[3]: f"{f[2]}.{f[4]}" for f in
                    con.execute(f"PRAGMA foreign_key_list({_q(tabla)})").fetchall()}
        columnas = [Columna(c[1], c[2] or "", bool(c[3]), c[4], bool(c[5]), foraneas.get(c[1]))
                    for c in con.execute(f"PRAGMA table_info({_q(tabla)})").fetchall()]
        indices = []
        for i in con.execute(f"PRAGMA index_list({_q(tabla)})").fetchall():
            cols = [x[2] for x in con.execute(f"PRAGMA index_info({_q(i[1])})").fetchall()]
            indices.append((i[1], bool(i[2]), cols))
        fila = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (tabla,)).fetchone()
        return Esquema(columnas, indices, (fila[0] if fila else "") or "")
    finally:
        con.close()


def page_rows(base: BaseInfo, tabla: str, pagina: int = 0,  # propio
              buscar: str = "") -> tuple[list[str], list[tuple], int]:
    """(columnas, filas de esa página, total que cumplen la búsqueda)."""
    con = connect(base)
    try:
        columnas = [c[1] for c in con.execute(f"PRAGMA table_info({_q(tabla)})").fetchall()]
        donde, args = "", []
        if buscar.strip() and columnas:
            donde = " WHERE " + " OR ".join(f"CAST({_q(c)} AS TEXT) LIKE ?" for c in columnas)
            args = [f"%{buscar.strip()}%"] * len(columnas)
        total = con.execute(f"SELECT COUNT(*) FROM {_q(tabla)}{donde}", args).fetchone()[0]
        cursor = con.execute(f"SELECT * FROM {_q(tabla)}{donde} LIMIT ? OFFSET ?",
                             [*args, POR_PAGINA, pagina * POR_PAGINA])
        columnas = [d[0] for d in cursor.description]
        return columnas, cursor.fetchall(), total
    finally:
        con.close()


# ============================================================================
# SQL
# ============================================================================
def split_statements(sql: str) -> list[str]:  # propio
    """'select 1; select 2;' -> ['select 1;', 'select 2;'] (respeta ; dentro de textos)."""
    sentencias, actual = [], ""
    for parte in sql.split(";"):
        actual += parte + ";"
        if sqlite3.complete_statement(actual):
            if actual.strip(" \n\t;"):
                sentencias.append(actual.strip())
            actual = ""
    if actual.strip(" \n\t;"):
        sentencias.append(actual.strip().rstrip(";"))
    return sentencias


def _strip_comments(sql: str) -> str:  # propio
    lineas = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return "\n".join(lineas).strip()


def is_read_only(sql: str) -> bool:  # propio
    """¿Solo consulta (SELECT, PRAGMA…)? Si no, en una base editable se pide confirmar."""
    sentencias = split_statements(sql)
    return bool(sentencias) and all(
        _strip_comments(s).split(None, 1)[0].upper().strip("(") in LECTURA
        for s in sentencias if _strip_comments(s))


@dataclass
class ResultadoSql:
    columnas: list[str] = field(default_factory=list)
    filas: list[tuple] = field(default_factory=list)
    hay_mas: bool = False          # pasó de MAX_FILAS
    cambios: int = 0               # filas afectadas (INSERT/UPDATE/DELETE)
    sentencias: int = 0
    tiempo_ms: int = 0
    error: str | None = None


def run(base: BaseInfo, sql: str, guardar: bool = True) -> ResultadoSql:  # propio
    """
    Ejecuta una o varias sentencias. Muestra el resultado de la ÚLTIMA que
    regresa filas. En una base editable, todo va en una transacción: si una
    falla, no se aplica ninguna.
    """
    r = ResultadoSql()
    sentencias = split_statements(sql)
    if not sentencias:
        r.error = "Escribe una consulta"
        return r
    inicio = time.perf_counter()
    try:
        con = connect(base)
    except (ValueError, sqlite3.Error) as ex:
        r.error = str(ex)
        return r
    try:
        for s in sentencias:
            cursor = con.execute(s)
            r.sentencias += 1
            if cursor.description:
                r.columnas = [d[0] for d in cursor.description]
                r.filas = cursor.fetchmany(MAX_FILAS + 1)
                r.hay_mas = len(r.filas) > MAX_FILAS
                r.filas = r.filas[:MAX_FILAS]
            elif cursor.rowcount and cursor.rowcount > 0:
                r.cambios += cursor.rowcount
        con.commit()
    except sqlite3.Error as ex:
        con.rollback()
        r.error = _friendly_error(ex, base)
    finally:
        con.close()
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    if guardar:
        _record(base, sql, r)
    return r


def _friendly_error(ex: sqlite3.Error, base: BaseInfo) -> str:  # propio
    texto = str(ex)
    if "readonly" in texto or "query_only" in texto or "attempt to write" in texto:
        if base.es_app:
            return "La base de ControlKraken es de solo lectura (para no romper la app)."
        return "Esta base está en solo lectura. Cámbialo en la lista de bases: menú de tres puntos, Permitir cambios."
    return texto


def _record(base: BaseInfo, sql: str, r: ResultadoSql):  # propio
    ConsultaSqlite.create(conexion_id=base.id, sql=sql.strip(),
                          filas=len(r.filas) if r.columnas else r.cambios, error=r.error)
    with SessionLocal() as session:
        sobran = list(session.scalars(
            select(ConsultaSqlite.id)
            .where(ConsultaSqlite.conexion_id.is_(base.id) if base.id is None
                   else ConsultaSqlite.conexion_id == base.id,
                   ConsultaSqlite.nombre.is_(None))
            .order_by(ConsultaSqlite.creado_en.desc(), ConsultaSqlite.id.desc())
            .offset(HISTORIAL_POR_BASE)))
        if sobran:
            session.execute(delete(ConsultaSqlite).where(ConsultaSqlite.id.in_(sobran)))
            session.commit()


def _of_base(base: BaseInfo):  # propio
    return (ConsultaSqlite.conexion_id.is_(None) if base.id is None
            else ConsultaSqlite.conexion_id == base.id)


def favorites(base: BaseInfo) -> list[ConsultaSqlite]:  # propio
    return sorted(ConsultaSqlite.search(_of_base(base), ConsultaSqlite.nombre.is_not(None)),
                  key=lambda c: c.nombre.lower())


def history(base: BaseInfo) -> list[ConsultaSqlite]:  # propio
    return ConsultaSqlite.search(_of_base(base), ConsultaSqlite.nombre.is_(None))


def save_favorite(base: BaseInfo, nombre: str, sql: str) -> ConsultaSqlite:  # propio
    if not nombre.strip():
        raise ValueError("Ponle un nombre")
    if not sql.strip():
        raise ValueError("No hay SQL que guardar")
    return ConsultaSqlite.create(conexion_id=base.id, nombre=nombre.strip()[:80], sql=sql.strip())


# ============================================================================
# Mostrar y exportar
# ============================================================================
def cell_text(valor, largo: int = 60) -> str:  # propio
    """Lo que se ve en una celda: NULL, <BLOB 12 KB> o el texto (recortado)."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bytes):
        from core.storage import human_size
        return f"<BLOB {human_size(len(valor))}>"
    texto = str(valor).replace("\n", " ")
    return texto if len(texto) <= largo else texto[:largo - 1] + "…"


def to_csv(columnas: list[str], filas: list[tuple]) -> bytes:  # propio
    """CSV con BOM (utf-8-sig): Excel lo abre con acentos bien."""
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(columnas)
    for fila in filas:
        escritor.writerow(["" if v is None else (f"<BLOB {len(v)} bytes>" if isinstance(v, bytes)
                                                  else v) for v in fila])
    return salida.getvalue().encode("utf-8-sig")


def file_bytes(base: BaseInfo) -> bytes:  # propio
    """Copia consistente del .db (para "Descargar copia"), aunque esté abierto."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "copia.db"
        origen, destino = connect(base), sqlite3.connect(copia)
        try:
            origen.backup(destino)
        finally:
            destino.close()
            origen.close()
        return copia.read_bytes()

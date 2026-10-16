"""
Lógica del explorador de bases (el "cocinero"). Sirve igual para SQLite,
PostgreSQL y MySQL: lo que cambia entre ellos vive en motores.py.

  databases()      la de ControlKraken (siempre arriba) + las que agregaste
  add_database()   copia un .db a data/kraken/bases/ y lo registra
  save_server()    alta/edición de un servidor PostgreSQL o MySQL
  test_server()    "Probar conexión": versión del servidor y sus bases de datos
  tables()         tablas y vistas con su número de filas
  schema()         columnas, llaves, índices y el CREATE de una tabla
  page_rows()      filas de 50 en 50 (con búsqueda en todas las columnas)
  run()            ejecuta tu SQL y lo anota en el historial de esa base
  to_csv()         un resultado -> CSV que abre Excel

Solo lectura de verdad: la hace cumplir la propia base (motores.py). La BD de
ControlKraken SIEMPRE se abre así.
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
from modulos.kraken.models.sqlite import PUERTOS, TIPOS
from modulos.kraken.sqlite import motores
from modulos.kraken.sqlite.motores import (POR_PAGINA, Columna, Esquema, Pagina, Tabla,
                                           message)

# Las pantallas y las pruebas los usan como services.Tabla, services.POR_PAGINA…
__all__ = ["APP", "POR_PAGINA", "BaseInfo", "Columna", "Esquema", "Pagina", "Tabla"]

MAX_FILAS = 1000            # filas de un resultado de SQL que se traen a la pantalla
HISTORIAL_POR_BASE = 100    # consultas recientes por base (las favoritas no cuentan)
ENCABEZADO = b"SQLite format 3\x00"
LECTURA = ("SELECT", "WITH", "PRAGMA", "EXPLAIN", "VALUES", "SHOW", "DESCRIBE", "DESC")


# ============================================================================
# Las bases
# ============================================================================
@dataclass
class BaseInfo:
    id: int | None           # None = la BD de ControlKraken
    nombre: str
    ruta: Path | None
    solo_lectura: bool
    respaldar: bool
    origen: str | None = None
    tipo: str = "sqlite"     # sqlite | postgres | mysql
    host: str | None = None
    puerto: int | None = None
    base_datos: str | None = None
    usuario: str | None = None
    clave: str | None = None
    ssh_equipo_id: int | None = None

    @property
    def es_app(self) -> bool:  # propio
        return self.id is None

    @property
    def es_servidor(self) -> bool:  # propio
        return self.tipo != "sqlite"

    @property
    def existe(self) -> bool:  # propio
        return self.es_servidor or bool(self.ruta and self.ruta.is_file())

    @property
    def tamano(self) -> int:  # propio
        return self.ruta.stat().st_size if (not self.es_servidor and self.existe) else 0

    @property
    def destino(self) -> str:  # propio
        """'odoo@localhost:5432/produccion' (para mostrar)."""
        puerto = self.puerto or PUERTOS.get(self.tipo, "")
        return f"{self.usuario}@{self.host}:{puerto}/{self.base_datos or '(sin base)'}"


APP = BaseInfo(None, "ControlKraken (esta app)", DB_PATH, True, True)


def _info(c: ConexionSqlite) -> BaseInfo:  # propio
    return BaseInfo(c.id, c.nombre, c.ruta, c.solo_lectura, c.respaldar, c.origen, c.tipo,
                    c.host, c.puerto, c.base_datos, c.usuario, c.clave, c.ssh_equipo_id)


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


def save_server(conexion_id: int | None, **valores) -> ConexionSqlite:  # propio
    """Alta o edición de un servidor PostgreSQL/MySQL (nuevo = en solo lectura)."""
    if valores.get("tipo") not in TIPOS or valores.get("tipo") == "sqlite":
        raise ValueError("Elige PostgreSQL o MySQL")
    for campo in ("nombre", "host", "base_datos", "usuario"):
        if isinstance(valores.get(campo), str):
            valores[campo] = valores[campo].strip() or None
    if conexion_id is None:
        valores.setdefault("solo_lectura", True)
        return ConexionSqlite.create(respaldar=False, **valores)
    return ConexionSqlite.update(conexion_id, **valores)


@dataclass
class Prueba:
    ok: bool
    mensaje: str
    version: str = ""
    bases: list[str] = field(default_factory=list)   # bases de datos del servidor


def test_server(base: BaseInfo) -> Prueba:  # propio
    """Conecta, dice la versión y lista las bases de datos (para elegir una)."""
    inicio = time.perf_counter()
    try:
        semilla = base.base_datos or ("postgres" if base.tipo == "postgres" else None)
        with motores.opened(base, semilla) as (con, motor):
            cur = con.cursor()
            cur.execute("SELECT version()")
            version = str(cur.fetchone()[0]).split(" on ")[0].split(",")[0]
            bases = motor.databases(con)
    except Exception as ex:  # noqa: BLE001
        return Prueba(False, friendly_connect_error(ex, base))
    ms = round((time.perf_counter() - inicio) * 1000)
    return Prueba(True, f"Conectado en {ms} ms", version, bases)


def friendly_connect_error(ex: Exception, base: BaseInfo) -> str:  # propio
    from modulos.kraken.ssh.conexion import HuellaCambio
    if isinstance(ex, HuellaCambio):
        return "La huella del servidor SSH cambió: ábrelo en SSH para revisarla"
    texto = message(ex)
    bajo = texto.lower()
    via = " (por el túnel SSH)" if base.ssh_equipo_id else ""
    if "password authentication failed" in bajo or "access denied" in bajo:
        return f"Usuario o contraseña incorrectos{via}"
    if ("does not exist" in bajo and "database" in bajo) or "unknown database" in bajo:
        return f"No existe la base de datos «{base.base_datos}»"
    causa = ex.__cause__ or ex.__context__
    if isinstance(causa, TimeoutError) or isinstance(ex, TimeoutError):
        return f"El servidor no contestó a tiempo{via}"
    if (isinstance(ex, ConnectionRefusedError) or isinstance(causa, ConnectionRefusedError)
            or "refused" in bajo or "can't connect" in bajo
            or "can't create a connection" in bajo):
        return (f"Nadie atiende en {base.host}:{base.puerto or PUERTOS.get(base.tipo)}{via}: "
                "¿el servidor está encendido y escucha en ese puerto?")
    if "timed out" in bajo or "timeout" in bajo:
        return f"El servidor no contestó a tiempo{via}"
    if "pg_hba.conf" in bajo:
        return ("PostgreSQL no deja entrar desde aquí (pg_hba.conf). Usa un túnel SSH o "
                "permite esta conexión en el servidor.")
    return texto


def connect(base: BaseInfo) -> sqlite3.Connection:  # propio
    """Conexión directa a un SQLite (la usa "Descargar copia")."""
    return motores.Sqlite().connect(base)


# ============================================================================
# Tablas y esquema
# ============================================================================
def tables(base: BaseInfo) -> list[Tabla]:  # propio
    with motores.opened(base) as (con, motor):
        return motor.tables(con)


def schema(base: BaseInfo, tabla: str) -> Esquema:  # propio
    with motores.opened(base) as (con, motor):
        return motor.schema(con, tabla)


def page_rows(base: BaseInfo, tabla: str, pagina: int = 0, buscar: str = "") -> Pagina:  # propio
    """(columnas, filas de esa página, total que cumplen la búsqueda); .aproximado si se estimó."""
    with motores.opened(base) as (con, motor):
        return motores.page(con, motor, tabla, pagina, buscar)


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
    regresa filas. Todo va en una transacción: si una falla, no se aplica
    ninguna (en MySQL, CREATE/ALTER/DROP se aplican al momento: así es MySQL).
    """
    r = ResultadoSql()
    sentencias = split_statements(sql)
    if not sentencias:
        r.error = "Escribe una consulta"
        return r
    inicio = time.perf_counter()
    try:
        with motores.opened(base) as (con, motor):
            try:
                cur = con.cursor()
                for s_ in sentencias:
                    cur.execute(s_.rstrip(";") if base.es_servidor else s_)
                    r.sentencias += 1
                    if cur.description:
                        r.columnas = [d[0] for d in cur.description]
                        filas = cur.fetchmany(MAX_FILAS + 1)
                        r.hay_mas = len(filas) > MAX_FILAS
                        r.filas = [tuple(f) for f in filas[:MAX_FILAS]]
                    elif cur.rowcount and cur.rowcount > 0:
                        r.cambios += cur.rowcount
                con.commit()
            except Exception as ex:  # noqa: BLE001  (cada librería tiene sus errores)
                try:
                    con.rollback()
                except Exception:  # noqa: BLE001
                    pass
                r.error = _friendly_error(ex, base, motor)
    except Exception as ex:  # noqa: BLE001  (no se pudo ni conectar)
        r.error = friendly_connect_error(ex, base) if base.es_servidor else message(ex)
    r.tiempo_ms = round((time.perf_counter() - inicio) * 1000)
    if guardar:
        _record(base, sql, r)
    return r


def _friendly_error(ex: Exception, base: BaseInfo, motor) -> str:  # propio
    texto = message(ex)
    if motor.is_read_only_error(texto):
        if base.es_app:
            return "La base de ControlKraken es de solo lectura (para no romper la app)."
        return ("Esta base está en solo lectura. Cámbialo en la lista de bases: menú de tres "
                "puntos, Permitir cambios.")
    if "statement timeout" in texto.lower() or "max_statement_time" in texto.lower() \
            or "maximum statement execution time" in texto.lower():
        return f"La consulta tardó más de {motores.TIEMPO_MAX_S} s y se canceló (usa LIMIT o un WHERE)"
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
    if isinstance(valor, memoryview):
        valor = bytes(valor)
    if isinstance(valor, (dict, list)):  # columnas JSON de Postgres (Odoo las usa)
        import json
        valor = json.dumps(valor, ensure_ascii=False)
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

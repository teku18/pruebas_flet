"""
Motores del explorador: lo que cambia entre SQLite, PostgreSQL y MySQL.

Todos hablan DB-API (el estándar de Python para bases: connect, cursor,
execute, fetchmany, commit, rollback), así que services.py ejecuta el SQL igual
para los tres. Aquí solo va lo que es distinto en cada uno:

  connect()   abrir la conexión (y ponerla en SOLO LECTURA si toca)
  quote()     comillas para nombres: "tabla" (SQLite/Postgres) o `tabla` (MySQL)
  tables()    lista de tablas y vistas con sus filas (en servidores: aproximadas)
  schema()    columnas, llaves, índices y el CREATE
  page()      filas de 50 en 50, con búsqueda en todas las columnas

Solo lectura de verdad, la hace cumplir el propio servidor:
  SQLite      archivo abierto con ?mode=ro + PRAGMA query_only
  PostgreSQL  SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY
  MySQL       SET SESSION TRANSACTION READ ONLY
Cualquier INSERT/UPDATE/DELETE/DROP falla con un error del servidor.

Librerías de puro Python (funcionan en el APK): pg8000 (PostgreSQL) y PyMySQL.
"""
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

POR_PAGINA = 50
TIEMPO_MAX_S = 30          # ninguna consulta del explorador espera más que esto
APROXIMAR_DESDE = 1_000_000  # tablas más grandes: el total de filas es estimado


@dataclass
class Tabla:
    nombre: str
    tipo: str               # "table" | "view"
    filas: int | None       # None si no se pudo contar
    aproximado: bool = False


@dataclass
class Columna:
    nombre: str
    tipo: str
    obligatoria: bool
    defecto: str | None
    llave: bool
    apunta_a: str | None = None


@dataclass
class Esquema:
    columnas: list[Columna]
    indices: list[tuple[str, bool, list[str]]]
    sql: str


class Pagina(tuple):
    """(columnas, filas, total) que además sabe si el total es aproximado."""

    def __new__(cls, columnas, filas, total, aproximado=False):
        obj = super().__new__(cls, (columnas, filas, total))
        obj.aproximado = aproximado
        return obj


def split_name(nombre: str) -> tuple[str | None, str]:  # propio
    """'ventas.pedidos' -> ('ventas', 'pedidos') · 'res_partner' -> (None, 'res_partner')."""
    if "." in nombre:
        esquema, _, tabla = nombre.partition(".")
        return esquema, tabla
    return None, nombre


def message(ex: Exception) -> str:  # propio
    """El texto útil de un error de cualquier librería."""
    if ex.args and isinstance(ex.args[0], dict):  # pg8000: {'S': 'ERROR', 'M': '…', 'C': '42P01'}
        datos = ex.args[0]
        texto = datos.get("M", str(datos))
        if datos.get("D"):
            texto += f" ({datos['D']})"
        return texto
    if len(ex.args) >= 2 and isinstance(ex.args[0], int):  # PyMySQL: (1146, "Table … doesn't exist")
        return str(ex.args[1])
    return str(ex) or type(ex).__name__


# ============================================================================
# SQLite
# ============================================================================
class Sqlite:
    nombre = "SQLite"

    @staticmethod
    def quote(nombre: str) -> str:  # propio
        return '"' + nombre.replace('"', '""') + '"'

    def qualify(self, tabla: str) -> str:  # propio
        return self.quote(tabla)

    def connect(self, base):  # propio
        if not base.existe:
            raise ValueError("El archivo de esta base no está en este equipo "
                             "(se marcó «no respaldar» y vienes de otro equipo)")
        if base.solo_lectura or base.es_app:
            con = sqlite3.connect(f"{base.ruta.resolve().as_uri()}?mode=ro", uri=True, timeout=5)
            con.execute("PRAGMA query_only = 1")
        else:
            con = sqlite3.connect(base.ruta, timeout=5)
        return con

    def is_read_only_error(self, texto: str) -> bool:  # propio
        return "readonly" in texto or "query_only" in texto or "attempt to write" in texto

    def tables(self, con) -> list[Tabla]:  # propio
        nombres = con.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        resultado = []
        for nombre, tipo in nombres:
            try:
                filas = con.execute(f"SELECT COUNT(*) FROM {self.quote(nombre)}").fetchone()[0]
            except sqlite3.Error:
                filas = None
            resultado.append(Tabla(nombre, tipo, filas))
        return resultado

    def schema(self, con, tabla: str) -> Esquema:  # propio
        q = self.quote(tabla)
        foraneas = {f[3]: f"{f[2]}.{f[4]}" for f in
                    con.execute(f"PRAGMA foreign_key_list({q})").fetchall()}
        columnas = [Columna(c[1], c[2] or "", bool(c[3]), c[4], bool(c[5]), foraneas.get(c[1]))
                    for c in con.execute(f"PRAGMA table_info({q})").fetchall()]
        indices = []
        for i in con.execute(f"PRAGMA index_list({q})").fetchall():
            cols = [x[2] for x in con.execute(f"PRAGMA index_info({self.quote(i[1])})").fetchall()]
            indices.append((i[1], bool(i[2]), cols))
        fila = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (tabla,)).fetchone()
        return Esquema(columnas, indices, (fila[0] if fila else "") or "")

    def column_names(self, con, tabla: str) -> list[str]:  # propio
        return [c[1] for c in con.execute(f"PRAGMA table_info({self.quote(tabla)})").fetchall()]

    def search_condition(self, columna: str) -> str:  # propio
        return f"CAST({self.quote(columna)} AS TEXT) LIKE ?"

    marcador = "?"

    def estimate(self, con, tabla: str) -> int | None:  # propio
        return None  # en SQLite contar es rápido


# ============================================================================
# PostgreSQL (pg8000)
# ============================================================================
class Postgres:
    nombre = "PostgreSQL"
    marcador = "%s"

    @staticmethod
    def quote(nombre: str) -> str:  # propio
        return '"' + nombre.replace('"', '""') + '"'

    def qualify(self, tabla: str) -> str:  # propio
        esquema, nombre = split_name(tabla)
        return (f"{self.quote(esquema)}." if esquema else "") + self.quote(nombre)

    def connect(self, base, host: str, puerto: int, base_datos: str | None = None):  # propio
        import pg8000.dbapi

        con = pg8000.dbapi.connect(user=base.usuario, password=base.clave or None, host=host,
                                   port=puerto, database=base_datos or base.base_datos or None,
                                   timeout=15, application_name="ControlKraken")
        cur = con.cursor()
        cur.execute(f"SET statement_timeout = {TIEMPO_MAX_S * 1000}")
        if base.solo_lectura:
            cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        con.commit()
        return con

    def is_read_only_error(self, texto: str) -> bool:  # propio
        return "read-only transaction" in texto

    def databases(self, con) -> list[str]:  # propio
        cur = con.cursor()
        cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate AND datallowconn "
                    "ORDER BY datname")
        return [f[0] for f in cur.fetchall()]

    def tables(self, con) -> list[Tabla]:  # propio
        cur = con.cursor()
        cur.execute("""
            SELECT t.table_schema, t.table_name, t.table_type, c.reltuples::bigint
            FROM information_schema.tables t
            LEFT JOIN pg_namespace n ON n.nspname = t.table_schema
            LEFT JOIN pg_class c ON c.relname = t.table_name AND c.relnamespace = n.oid
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND t.table_schema NOT LIKE 'pg_toast%'
            ORDER BY t.table_type, t.table_schema <> 'public', t.table_schema, t.table_name""")
        resultado = []
        for esquema, nombre, tipo, estimado in cur.fetchall():
            visible = nombre if esquema == "public" else f"{esquema}.{nombre}"
            filas = int(estimado) if estimado is not None and estimado >= 0 else None
            resultado.append(Tabla(visible, "view" if tipo == "VIEW" else "table", filas,
                                   aproximado=True))
        return resultado

    def _schema_and_table(self, tabla: str) -> tuple[str, str]:  # propio
        esquema, nombre = split_name(tabla)
        return esquema or "public", nombre

    def schema(self, con, tabla: str) -> Esquema:  # propio
        esquema, nombre = self._schema_and_table(tabla)
        cur = con.cursor()
        cur.execute("""
            SELECT kcu.column_name, tc.constraint_type, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND tc.constraint_type = 'FOREIGN KEY'
            WHERE tc.table_schema = %s AND tc.table_name = %s
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')""", (esquema, nombre))
        llaves, foraneas = set(), {}
        for col, tipo, ref_tabla, ref_col in cur.fetchall():
            if tipo == "PRIMARY KEY":
                llaves.add(col)
            elif ref_tabla:
                foraneas[col] = f"{ref_tabla}.{ref_col}"
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
            FROM information_schema.columns WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position""", (esquema, nombre))
        columnas = []
        for col, tipo, nulo, defecto, largo in cur.fetchall():
            tipo = f"{tipo}({largo})" if largo else tipo
            columnas.append(Columna(col, tipo, nulo == "NO", defecto, col in llaves,
                                    foraneas.get(col)))
        cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = %s "
                    "AND tablename = %s ORDER BY indexname", (esquema, nombre))
        indices = []
        for indice, definicion in cur.fetchall():
            m = re.search(r"\(([^()]*)\)\s*(WHERE.*)?$", definicion)
            cols = [c.strip().strip('"') for c in m.group(1).split(",")] if m else []
            indices.append((indice, "UNIQUE INDEX" in definicion.upper(), cols))
        lineas = [f"  {self.quote(c.nombre)} {c.tipo}"
                  + (" NOT NULL" if c.obligatoria else "")
                  + (f" DEFAULT {c.defecto}" if c.defecto else "") for c in columnas]
        if llaves:
            lineas.append(f"  PRIMARY KEY ({', '.join(self.quote(k) for k in sorted(llaves))})")
        sql = (f"CREATE TABLE {self.qualify(tabla)} (\n" + ",\n".join(lineas) + "\n);"
               + "".join(f"\n-- índice {i[0]} ({', '.join(i[2])})" for i in indices))
        return Esquema(columnas, indices, sql)

    def column_names(self, con, tabla: str) -> list[str]:  # propio
        esquema, nombre = self._schema_and_table(tabla)
        cur = con.cursor()
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s "
                    "AND table_name = %s ORDER BY ordinal_position", (esquema, nombre))
        return [f[0] for f in cur.fetchall()]

    def search_condition(self, columna: str) -> str:  # propio
        return f"CAST({self.quote(columna)} AS TEXT) ILIKE %s"

    def estimate(self, con, tabla: str) -> int | None:  # propio
        cur = con.cursor()
        cur.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass",
                    (self.qualify(tabla),))
        fila = cur.fetchone()
        return int(fila[0]) if fila and fila[0] is not None and fila[0] >= 0 else None


# ============================================================================
# MySQL / MariaDB (PyMySQL)
# ============================================================================
class Mysql:
    nombre = "MySQL"
    marcador = "%s"

    @staticmethod
    def quote(nombre: str) -> str:  # propio
        return "`" + nombre.replace("`", "``") + "`"

    def qualify(self, tabla: str) -> str:  # propio
        return self.quote(tabla)

    def connect(self, base, host: str, puerto: int, base_datos: str | None = None):  # propio
        import pymysql

        con = pymysql.connect(host=host, port=puerto, user=base.usuario,
                              password=base.clave or "", database=base_datos or base.base_datos
                              or None, connect_timeout=15, read_timeout=TIEMPO_MAX_S + 30,
                              write_timeout=TIEMPO_MAX_S + 30, charset="utf8mb4",
                              autocommit=False)
        cur = con.cursor()
        for limite in (f"SET SESSION MAX_EXECUTION_TIME = {TIEMPO_MAX_S * 1000}",   # MySQL
                       f"SET SESSION max_statement_time = {TIEMPO_MAX_S}"):          # MariaDB
            try:
                cur.execute(limite)
            except pymysql.MySQLError:
                pass  # cada uno entiende solo el suyo
        if base.solo_lectura:
            cur.execute("SET SESSION TRANSACTION READ ONLY")
        con.commit()
        return con

    def is_read_only_error(self, texto: str) -> bool:  # propio
        return "read only transaction" in texto.lower()

    def databases(self, con) -> list[str]:  # propio
        cur = con.cursor()
        cur.execute("SHOW DATABASES")
        internas = {"information_schema", "performance_schema", "mysql", "sys"}
        return [f[0] for f in cur.fetchall() if f[0] not in internas]

    def tables(self, con) -> list[Tabla]:  # propio
        cur = con.cursor()
        cur.execute("SELECT TABLE_NAME, TABLE_TYPE, TABLE_ROWS FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_TYPE, TABLE_NAME")
        return [Tabla(n, "view" if t == "VIEW" else "table",
                      int(f) if f is not None else None, aproximado=True)
                for n, t, f in cur.fetchall()]

    def schema(self, con, tabla: str) -> Esquema:  # propio
        cur = con.cursor()
        cur.execute("SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                    "FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL", (tabla,))
        foraneas = {c: f"{t}.{r}" for c, t, r in cur.fetchall()}
        cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY "
                    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                    "AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION", (tabla,))
        columnas = [Columna(c, t, n == "NO", d, k == "PRI", foraneas.get(c))
                    for c, t, n, d, k in cur.fetchall()]
        cur.execute("SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME FROM information_schema.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "ORDER BY INDEX_NAME, SEQ_IN_INDEX", (tabla,))
        indices: dict[str, tuple[bool, list[str]]] = {}
        for indice, no_unico, col in cur.fetchall():
            indices.setdefault(indice, (not no_unico, []))[1].append(col)
        try:
            cur.execute(f"SHOW CREATE TABLE {self.quote(tabla)}")
            sql = cur.fetchone()[1]
        except Exception:  # noqa: BLE001  (vistas sin permiso, etc.)
            sql = ""
        return Esquema(columnas, [(n, u, c) for n, (u, c) in indices.items()], sql)

    def column_names(self, con, tabla: str) -> list[str]:  # propio
        cur = con.cursor()
        cur.execute("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = "
                    "DATABASE() AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION", (tabla,))
        return [f[0] for f in cur.fetchall()]

    def search_condition(self, columna: str) -> str:  # propio
        return f"CAST({self.quote(columna)} AS CHAR) LIKE %s"

    def estimate(self, con, tabla: str) -> int | None:  # propio
        cur = con.cursor()
        cur.execute("SELECT TABLE_ROWS FROM information_schema.TABLES WHERE TABLE_SCHEMA = "
                    "DATABASE() AND TABLE_NAME = %s", (tabla,))
        fila = cur.fetchone()
        return int(fila[0]) if fila and fila[0] is not None else None


MOTORES = {"sqlite": Sqlite(), "postgres": Postgres(), "mysql": Mysql()}


# ============================================================================
# Abrir (con o sin túnel SSH)
# ============================================================================
@contextmanager
def opened(base, base_datos: str | None = None):  # propio
    """
    `with opened(base) as (con, motor):` — conexión lista (en solo lectura si
    toca) y se cierra al salir. Con túnel SSH, se conecta a 127.0.0.1:<puerto
    del túnel> y el túnel lleva todo al servidor.
    """
    motor = MOTORES[base.tipo]
    if base.tipo == "sqlite":
        con = motor.connect(base)
    else:
        host, puerto = base.host, base.puerto or (5432 if base.tipo == "postgres" else 3306)
        if base.ssh_equipo_id:
            from modulos.kraken.ssh.tunel import tunnel_for
            tunel = tunnel_for(base.ssh_equipo_id, host or "localhost", puerto)
            host, puerto = "127.0.0.1", tunel.puerto_local
        con = motor.connect(base, host, puerto, base_datos)
    try:
        yield con, motor
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass


def page(con, motor, tabla: str, pagina: int = 0, buscar: str = "") -> Pagina:  # propio
    columnas = motor.column_names(con, tabla)
    donde, args = "", []
    if buscar.strip() and columnas:
        donde = " WHERE " + " OR ".join(motor.search_condition(c) for c in columnas)
        args = [f"%{buscar.strip()}%"] * len(columnas)
    cur = con.cursor()
    aproximado = False
    total = None
    if not donde:
        estimado = motor.estimate(con, tabla)
        if estimado is not None and estimado >= APROXIMAR_DESDE:
            total, aproximado = estimado, True  # contar millones de filas tarda: se estima
    if total is None:
        cur.execute(f"SELECT COUNT(*) FROM {motor.qualify(tabla)}{donde}", args)
        total = cur.fetchone()[0]
    m = motor.marcador
    cur.execute(f"SELECT * FROM {motor.qualify(tabla)}{donde} LIMIT {m} OFFSET {m}",
                [*args, POR_PAGINA, pagina * POR_PAGINA])
    nombres = [d[0] for d in cur.description]
    filas = [tuple(f) for f in cur.fetchall()]
    try:
        con.rollback()  # solo leímos: que no quede una transacción abierta
    except Exception:  # noqa: BLE001
        pass
    return Pagina(nombres, filas, total, aproximado)

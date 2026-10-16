"""
Modelos del explorador de bases de datos (empezó solo con SQLite, de ahí el nombre):

  ConexionSqlite  1 ──< N  ConsultaSqlite
  (una base)               (historial de SQL; con nombre = favorita)

  tipo "sqlite"    un archivo .db copiado a la app (archivo, respaldar)
  tipo "postgres"  un servidor PostgreSQL  (host, puerto, base_datos, usuario, clave)
  tipo "mysql"     un servidor MySQL / MariaDB (los mismos campos)
  ssh_equipo_id    opcional: llegar al servidor por un TÚNEL SSH a través de ese
                   equipo (así el puerto 5432/3306 no se abre a internet). Con
                   túnel, `host` es como lo ve ese servidor: casi siempre localhost.

Las contraseñas se guardan tal cual (texto normal) y van en el respaldo, como
todo lo de Kraken Tools.

La BD de ControlKraken NO es una fila: siempre aparece arriba y siempre en
solo lectura (conexion_id = None en sus consultas).

Las demás bases se COPIAN a data/kraken/bases/ (en el celular la ruta del
archivo original no es estable). `respaldar` decide si esa copia entra en el
zip del respaldo: una base grande puede quedarse fuera. Cuando está fuera,
restaurar un respaldo NO la borra de este equipo (core/backup.py la aparta y
la regresa), pero en un equipo nuevo no estará.
"""
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, delete, select
from sqlalchemy.orm import Mapped, mapped_column

from core import backup
from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from core.storage import DATA_DIR, absolute_path, delete_file

BASES_DIR = DATA_DIR / "kraken" / "bases"


TIPOS = {"sqlite": "SQLite", "postgres": "PostgreSQL", "mysql": "MySQL / MariaDB"}
PUERTOS = {"postgres": 5432, "mysql": 3306}


class ConexionSqlite(CrudMixin, Base):
    __tablename__ = "kt_sqlite_conexiones"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="sqlite")
    archivo: Mapped[str | None] = mapped_column(String(300), nullable=True)  # relativo a data/
    origen: Mapped[str | None] = mapped_column(Text, nullable=True)     # de dónde se copió
    solo_lectura: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    respaldar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # --- servidores (postgres / mysql) ---
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    puerto: Mapped[int | None] = mapped_column(Integer, nullable=True)
    base_datos: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usuario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    clave: Mapped[str | None] = mapped_column(Text, nullable=True)
    ssh_equipo_id: Mapped[int | None] = mapped_column(ForeignKey("kt_equipos.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")
        self.tipo = self.tipo or "sqlite"  # el default de la columna llega hasta el INSERT
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo de base no válido: {self.tipo}")
        if self.tipo == "sqlite" and not self.archivo:
            raise ValueError("Falta el archivo")
        if self.tipo != "sqlite":
            if not (self.host or "").strip():
                raise ValueError("Escribe el servidor (IP o dominio)")
            if not (self.usuario or "").strip():
                raise ValueError("Escribe el usuario")
            if self.puerto is not None and not 1 <= int(self.puerto) <= 65535:
                raise ValueError("El puerto va de 1 a 65535")

    @property
    def es_servidor(self) -> bool:  # propio
        return self.tipo != "sqlite"

    @property
    def ruta(self) -> Path | None:  # propio
        return absolute_path(self.archivo) if self.archivo else None

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Borra la conexión, su copia del archivo y sus consultas."""
        conexion = cls.get(registro_id)
        with SessionLocal() as session:
            session.execute(delete(ConsultaSqlite).where(ConsultaSqlite.conexion_id == registro_id))
            session.commit()
        super().delete(registro_id)
        if conexion and conexion.archivo:
            delete_file(conexion.archivo)
            for extra in ("-wal", "-shm", "-journal"):  # restos de SQLite, si hay
                delete_file(conexion.archivo + extra)


class ConsultaSqlite(CrudMixin, Base):
    __tablename__ = "kt_sqlite_consultas"
    _orden = "creado_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conexion_id: Mapped[int | None] = mapped_column(ForeignKey("kt_sqlite_conexiones.id"),
                                                    nullable=True)   # None = ControlKraken
    nombre: Mapped[str | None] = mapped_column(String(80), nullable=True)  # favorita
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    filas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)


def _files_outside_backup() -> set[Path]:  # propio
    """Copias de bases marcadas "no respaldar" (core/backup.py las salta)."""
    with SessionLocal() as session:
        archivos = session.scalars(select(ConexionSqlite.archivo).where(
            ConexionSqlite.respaldar.is_(False), ConexionSqlite.archivo.is_not(None)))
        rutas = set()
        for archivo in archivos:
            ruta = absolute_path(archivo)
            rutas |= {ruta, *(Path(str(ruta) + x) for x in ("-wal", "-shm", "-journal"))}
        return rutas


backup.register_exclusion(_files_outside_backup)

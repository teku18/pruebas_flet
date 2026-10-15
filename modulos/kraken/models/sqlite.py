"""
Modelos del explorador SQLite:

  ConexionSqlite  1 ──< N  ConsultaSqlite
  (una base .db)           (historial de SQL; con nombre = favorita)

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


class ConexionSqlite(CrudMixin, Base):
    __tablename__ = "kt_sqlite_conexiones"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    archivo: Mapped[str] = mapped_column(String(300), nullable=False)   # relativo a data/
    origen: Mapped[str | None] = mapped_column(Text, nullable=True)     # de dónde se copió
    solo_lectura: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    respaldar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")

    @property
    def ruta(self) -> Path:  # propio
        return absolute_path(self.archivo)

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Borra la conexión, su copia del archivo y sus consultas."""
        conexion = cls.get(registro_id)
        with SessionLocal() as session:
            session.execute(delete(ConsultaSqlite).where(ConsultaSqlite.conexion_id == registro_id))
            session.commit()
        super().delete(registro_id)
        if conexion:
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
            ConexionSqlite.respaldar.is_(False)))
        rutas = set()
        for archivo in archivos:
            ruta = absolute_path(archivo)
            rutas |= {ruta, *(Path(str(ruta) + x) for x in ("-wal", "-shm", "-journal"))}
        return rutas


backup.register_exclusion(_files_outside_backup)

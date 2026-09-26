"""Modelo Proyecto: cabecera de la bitácora (personal, familiar o trabajo)."""
from datetime import date

from sqlalchemy import Date, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from core.storage import DATA_DIR, delete_folder

TIPO_PROYECTO_SELECTION = {
    "personal": "Personal",
    "familiar": "Familiar",
    "trabajo": "Trabajo",
}

ESTADO_PROYECTO_SELECTION = {
    "activo": "Activo",
    "pausa": "En pausa",
    "terminado": "Terminado",
}

# Carpeta de adjuntos de todos los proyectos: data/adjuntos/<proyecto_id>/
ADJUNTOS_DIR = DATA_DIR / "adjuntos"


class Proyecto(CrudMixin, Base):
    __tablename__ = "proyectos"
    _orden = "fecha_inicio desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)             # Selection
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="activo")
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Un proyecto tiene muchas entradas de bitácora (One2many)
    entradas: Mapped[list["Entrada"]] = relationship(  # noqa: F821
        back_populates="proyecto", cascade="all, delete-orphan"
    )

    @validates("tipo")
    def _validate_tipo(self, key, value):  # propio
        if value not in TIPO_PROYECTO_SELECTION:
            raise ValueError(f"Tipo de proyecto no válido: {value}")
        return value

    @validates("estado")
    def _validate_estado(self, key, value):  # propio
        if value not in ESTADO_PROYECTO_SELECTION:
            raise ValueError(f"Estado no válido: {value}")
        return value

    @property
    def tipo_label(self) -> str:  # propio
        return TIPO_PROYECTO_SELECTION.get(self.tipo, self.tipo)

    @property
    def estado_label(self) -> str:  # propio
        return ESTADO_PROYECTO_SELECTION.get(self.estado, self.estado)

    # --- Consultas -----------------------------------------------------
    @classmethod
    def search_by_tipo(cls, tipo: str | None) -> list["Proyecto"]:  # propio
        """Todos, o solo los de un tipo (filtro de la lista)."""
        return cls.search(cls.tipo == tipo) if tipo else cls.search_all()

    @classmethod
    def entries_summary(cls) -> dict[int, tuple[int, object]]:  # propio
        """{proyecto_id: (cantidad de entradas, fecha de la última)}"""
        from modulos.proyectos.models.entrada import Entrada

        with SessionLocal() as session:
            consulta = select(
                Entrada.proyecto_id, func.count(), func.max(Entrada.fecha_hora)
            ).group_by(Entrada.proyecto_id)
            return {pid: (n, ultima) for pid, n, ultima in session.execute(consulta)}

    # --- Borrar también sus archivos ----------------------------------
    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de las filas (cascade), borra la carpeta de adjuntos."""
        super().delete(registro_id)
        delete_folder(ADJUNTOS_DIR / str(registro_id))

    def __repr__(self) -> str:
        return f"<Proyecto id={self.id} {self.nombre} ({self.tipo})>"

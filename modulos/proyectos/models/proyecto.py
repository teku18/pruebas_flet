"""
Modelo Proyecto: cabecera de la bitácora (personal, familiar o trabajo).

Fechas:
  fecha_inicio -> cuándo empezó de verdad (puede ser antes de capturarlo)
  fecha_fin    -> se llena sola al pasar a Terminado o Cancelado
  creado_en    -> cuándo lo registraste en la app (no se muestra)
La duración, la última actividad y los días sin avance NO se guardan:
se calculan en services.py (como un compute sin store=True en Odoo).
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func, select
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
    "cancelado": "Cancelado",
}

# Estados en los que el proyecto ya acabó (llevan fecha_fin)
ESTADOS_CERRADOS = {"terminado", "cancelado"}

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
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Destacado = de los que quieres presumir en el resumen del año
    destacado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )

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

    def _validate(self) -> None:  # propio
        """
        Regla del estado y la fecha fin (como un onchange + constrains de Odoo):
          Terminado/Cancelado sin fecha fin -> se pone hoy
          Activo/En pausa                   -> sin fecha fin
        """
        if self.estado in ESTADOS_CERRADOS:
            if self.fecha_fin is None:
                self.fecha_fin = date.today()
        else:
            self.fecha_fin = None
        if self.fecha_fin and self.fecha_inicio and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha fin no puede ser antes del inicio")

    @property
    def cerrado(self) -> bool:  # propio
        return self.estado in ESTADOS_CERRADOS

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
        """Además de las filas (cascade), borra la carpeta de adjuntos y sus tareas."""
        # Import aquí adentro: la Agenda ya importa Proyectos, así no se enciclan
        from modulos.agenda.services import delete_project_tasks

        delete_project_tasks(registro_id)
        super().delete(registro_id)
        delete_folder(ADJUNTOS_DIR / str(registro_id))

    def __repr__(self) -> str:
        return f"<Proyecto id={self.id} {self.nombre} ({self.tipo})>"

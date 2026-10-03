"""
Catálogos de Proyectos (se configuran en Proyectos → Ajustes):

  EtapaProyecto  -> columnas del Kanban de proyectos (Activo, En pausa, Terminado…)
  EtapaTarea     -> columnas del Kanban de tareas (Por hacer, En proceso, Hecho…)
  TipoEntrada    -> tipos de entrada de la bitácora (Avance, Hito, Problema…)

Igual que los stage_id de Odoo: son registros, no una lista fija en el código.
Tú agregas, renombras, reordenas (secuencia) y borras (si nadie las usa).

La "clase" de una etapa de proyecto le dice a la app qué SIGNIFICA:
  en_curso   -> el proyecto está vivo: si no avanza, sale como estancado
  pausa      -> vivo pero en pausa: no avisa de estancado
  terminada  -> acabó bien: lleva fecha fin y cuenta en el resumen del año
  cancelada  -> acabó sin terminar: lleva fecha fin
Así puedes tener "Idea", "En desarrollo", "En revisión"… y la app sigue
sabiendo cuáles están cerradas.

Cada proyecto elige qué etapas de TAREA usa (tabla proyecto_etapas_tarea,
un Many2many). Si no elige ninguna, usa todas.

Colores e íconos se guardan como texto ("amber", "STAR") y se convierten
en la vista: los colores de Flet aceptan el texto tal cual.
"""
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

CLASE_ETAPA_SELECTION = {
    "en_curso": "En curso",
    "pausa": "En pausa",
    "terminada": "Terminada",
    "cancelada": "Cancelada",
}
CLASES_CERRADAS = {"terminada", "cancelada"}

# Opciones que ofrece Ajustes al crear/editar (texto guardado -> se ve así)
COLORES_CATALOGO = ["blue", "indigo", "teal", "green", "amber", "orange", "red",
                    "pink", "purple", "bluegrey", "grey"]
ICONOS_ENTRADA = ["TRENDING_UP", "STAR", "REPORT_PROBLEM", "FLAG", "LIGHTBULB",
                  "BUILD", "EVENT", "CHAT", "ATTACH_MONEY", "LABEL"]

# Many2many: qué etapas de tarea usa cada proyecto
proyecto_etapas_tarea = Table(
    "proyecto_etapas_tarea",
    Base.metadata,
    Column("proyecto_id", ForeignKey("proyectos.id"), primary_key=True),
    Column("etapa_id", ForeignKey("tarea_etapas.id"), primary_key=True),
)


class CatalogoMixin(CrudMixin):
    """Lo común de los 3 catálogos: orden por secuencia, nombre único y 'en uso'."""
    _orden = "secuencia asc, id asc"
    _usado_por: tuple = ()  # (modelo, columna) que apuntan a este catálogo

    @classmethod
    def create_last(cls, **valores):  # propio
        """Crea al final de la lista (secuencia = la mayor + 1)."""
        with SessionLocal() as session:
            mayor = session.scalar(select(func.max(cls.secuencia))) or 0
        return cls.create(secuencia=mayor + 1, **valores)

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        iguales = [r for r in cls.search(func.lower(cls.nombre) == nombre.strip().lower())
                   if r.id != excluir_id]
        if iguales:
            raise ValueError("Ya existe uno con ese nombre")

    @classmethod
    def move(cls, registro_id: int, paso: int) -> None:  # propio
        """Sube (paso=-1) o baja (paso=+1) un lugar: renumera 1, 2, 3… y cambia dos."""
        with SessionLocal() as session:
            todos = list(session.scalars(select(cls).order_by(cls.secuencia, cls.id)))
            i = next((n for n, r in enumerate(todos) if r.id == registro_id), None)
            j = None if i is None else i + paso
            if j is not None and 0 <= j < len(todos):
                todos[i], todos[j] = todos[j], todos[i]
            for n, r in enumerate(todos, start=1):
                r.secuencia = n
            session.commit()

    @classmethod
    def usage_count(cls) -> dict[int, int]:  # propio
        """{id: cuántos registros lo usan} (proyectos, tareas o entradas)."""
        modelo, columna = cls._used_by()
        with SessionLocal() as session:
            consulta = select(columna, func.count()).where(columna.is_not(None)).group_by(columna)
            return dict(session.execute(consulta).all())

    @classmethod
    def _used_by(cls):  # propio
        raise NotImplementedError

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Solo si nadie lo usa (como ondelete='restrict' en Odoo)."""
        usos = cls.usage_count().get(registro_id, 0)
        if usos:
            raise ValueError(f"Está en uso ({usos}). Mueve esos registros a otro primero.")
        if len(cls.search_all()) <= 1:
            raise ValueError("Debe quedar al menos uno")
        super().delete(registro_id)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")


class EtapaProyecto(CatalogoMixin, Base):
    __tablename__ = "proyecto_etapas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clase: Mapped[str] = mapped_column(String(20), nullable=False, default="en_curso")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="blue")

    @validates("clase")
    def _validate_clase(self, key, value):  # propio
        if value not in CLASE_ETAPA_SELECTION:
            raise ValueError(f"Clase no válida: {value}")
        return value

    @property
    def cerrada(self) -> bool:  # propio
        return self.clase in CLASES_CERRADAS

    @property
    def clase_label(self) -> str:  # propio
        return CLASE_ETAPA_SELECTION.get(self.clase, self.clase)

    @classmethod
    def _used_by(cls):  # propio
        from modulos.proyectos.models.proyecto import Proyecto

        return Proyecto, Proyecto.etapa_id

    @classmethod
    def default(cls) -> "EtapaProyecto | None":  # propio
        """La etapa de un proyecto nuevo: la primera 'en curso' (o la primera)."""
        todas = cls.search_all()
        return next((e for e in todas if e.clase == "en_curso"), todas[0] if todas else None)

    def __repr__(self) -> str:
        return f"<EtapaProyecto {self.nombre} ({self.clase})>"


class EtapaTarea(CatalogoMixin, Base):
    __tablename__ = "tarea_etapas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Cerrada = "Hecho": llevar una tarea aquí la marca como hecha
    cerrada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="grey")

    @classmethod
    def _used_by(cls):  # propio
        from modulos.agenda.models import Tarea

        return Tarea, Tarea.etapa_id

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de la regla de uso, la quita de los proyectos que la tenían elegida."""
        super().delete(registro_id)
        with SessionLocal() as session:
            session.execute(proyecto_etapas_tarea.delete().where(
                proyecto_etapas_tarea.c.etapa_id == registro_id))
            session.commit()

    def __repr__(self) -> str:
        return f"<EtapaTarea {self.nombre}{' (cerrada)' if self.cerrada else ''}>"


class TipoEntrada(CatalogoMixin, Base):
    __tablename__ = "proyecto_tipos_entrada"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hito = momento importante: arma la línea de tiempo y el resumen del año
    es_hito: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    icono: Mapped[str] = mapped_column(String(40), nullable=False, default="LABEL")
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="bluegrey")

    @classmethod
    def _used_by(cls):  # propio
        from modulos.proyectos.models.entrada import Entrada

        return Entrada, Entrada.tipo_id

    @classmethod
    def default(cls) -> "TipoEntrada | None":  # propio
        """El tipo de una entrada nueva: el primero que no es hito (normalmente Avance)."""
        todos = cls.search_all()
        return next((t for t in todos if not t.es_hito), todos[0] if todos else None)

    def __repr__(self) -> str:
        return f"<TipoEntrada {self.nombre}{' (hito)' if self.es_hito else ''}>"

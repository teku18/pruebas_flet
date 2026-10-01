"""
Modelos del módulo Desarrollo (el "roadmap" de la propia app):

  ModuloApp  -> un módulo de ControlKraken (Finanzas, Agenda...) con su
                descripción, prioridad y % de avance
  Pendiente  -> una tarea, error o comentario sobre ese módulo, con su
                propia prioridad. Al marcarlo hecho guarda cuándo.

  ModuloApp 1 ──< N Pendiente 1 ──< N DevAdjunto   (archivos en data/desarrollo/)
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from core.database import Base
from core.mixins import CrudMixin
from core.storage import delete_folder

PRIORIDAD_SELECTION = {
    "alta": "Alta",
    "media": "Media",
    "baja": "Baja",
}

# Para ordenar: alta primero. (No va en _orden porque es texto, no número)
PRIORIDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2}

TIPO_PENDIENTE_SELECTION = {
    "tarea": "Tarea",
    "error": "Error",
    "comentario": "Comentario",
}


def _validate_prioridad(value: str) -> str:  # propio
    if value not in PRIORIDAD_SELECTION:
        raise ValueError(f"Prioridad no válida: {value}")
    return value


class ModuloApp(CrudMixin, Base):
    __tablename__ = "dev_modulos"
    _orden = "nombre asc"  # el orden por prioridad lo hace services.py

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    prioridad: Mapped[str] = mapped_column(String(10), nullable=False, default="media")
    avance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-100 %
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )

    pendientes: Mapped[list["Pendiente"]] = relationship(
        back_populates="modulo", cascade="all, delete-orphan"
    )

    @validates("prioridad")
    def _validate_prioridad(self, key, value):  # propio
        return _validate_prioridad(value)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("El módulo necesita un nombre")
        if not 0 <= (self.avance or 0) <= 100:
            raise ValueError("El avance va de 0 a 100")

    @property
    def prioridad_label(self) -> str:  # propio
        return PRIORIDAD_SELECTION.get(self.prioridad, self.prioridad)

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Filas en cascada (pendientes y adjuntos) + las carpetas de archivos."""
        from modulos.desarrollo.models.adjunto import DEV_ADJUNTOS_DIR

        ids = [p.id for p in Pendiente.search(Pendiente.modulo_id == registro_id)]
        super().delete(registro_id)
        for pendiente_id in ids:
            delete_folder(DEV_ADJUNTOS_DIR / str(pendiente_id))

    def __repr__(self) -> str:
        return f"<ModuloApp id={self.id} {self.nombre} {self.avance}%>"


class Pendiente(CrudMixin, Base):
    __tablename__ = "dev_pendientes"
    _orden = "id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modulo_id: Mapped[int] = mapped_column(ForeignKey("dev_modulos.id"), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="tarea")
    prioridad: Mapped[str] = mapped_column(String(10), nullable=False, default="media")
    hecho: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )
    hecho_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    modulo: Mapped["ModuloApp"] = relationship(back_populates="pendientes")
    adjuntos: Mapped[list["DevAdjunto"]] = relationship(  # noqa: F821
        back_populates="pendiente", cascade="all, delete-orphan"
    )

    @validates("tipo")
    def _validate_tipo(self, key, value):  # propio
        if value not in TIPO_PENDIENTE_SELECTION:
            raise ValueError(f"Tipo no válido: {value}")
        return value

    @validates("prioridad")
    def _validate_prioridad(self, key, value):  # propio
        return _validate_prioridad(value)

    def _validate(self) -> None:  # propio
        """Texto obligatorio; 'hecho_en' se llena/limpia solo según 'hecho'."""
        if not (self.texto or "").strip():
            raise ValueError("Escribe la tarea o comentario")
        if self.hecho and self.hecho_en is None:
            self.hecho_en = datetime.now().replace(microsecond=0)
        elif not self.hecho:
            self.hecho_en = None

    @property
    def tipo_label(self) -> str:  # propio
        return TIPO_PENDIENTE_SELECTION.get(self.tipo, self.tipo)

    @property
    def prioridad_label(self) -> str:  # propio
        return PRIORIDAD_SELECTION.get(self.prioridad, self.prioridad)

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Filas (cascada) + la carpeta con sus archivos."""
        from modulos.desarrollo.models.adjunto import DEV_ADJUNTOS_DIR

        super().delete(registro_id)
        delete_folder(DEV_ADJUNTOS_DIR / str(registro_id))

    def __repr__(self) -> str:
        return f"<Pendiente id={self.id} modulo={self.modulo_id} {self.prioridad}>"

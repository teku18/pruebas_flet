"""
Modelos de la Agenda:
  Tarea         -> algo que hay que hacer, con o sin proyecto
  Cumplimiento  -> el historial: cada vez que marcaste una tarea como hecha

La "fecha" de una tarea es su PRÓXIMA fecha:
  - Única:      al marcarla hecha queda completada=True y ya no sale.
  - Recurrente: al marcarla hecha se guarda un Cumplimiento y "fecha"
                salta al siguiente periodo (la renta del 1 oct pasa al 1 nov).
Así el chismoso solo pregunta "¿qué tareas tienen fecha <= mañana?".
"""
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from core.database import Base
from core.mixins import CrudMixin

FRECUENCIA_SELECTION = {
    "unica": "Una vez",
    "diaria": "Diario",
    "lun_vie": "Lunes a viernes",
    "semanal": "Cada semana",
    "mensual": "Cada mes",
}


class Tarea(CrudMixin, Base):
    __tablename__ = "tareas"
    _orden = "fecha asc, hora_inicio asc, id asc"  # la más próxima arriba

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    titulo: Mapped[str] = mapped_column(String(150), nullable=False)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Opcional: NULL = tarea suelta ("sacar a los perros")
    proyecto_id: Mapped[int | None] = mapped_column(ForeignKey("proyectos.id"), nullable=True)

    fecha: Mapped[date] = mapped_column(Date, nullable=False)          # próxima fecha
    hora_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)  # None = todo el día
    hora_fin: Mapped[time | None] = mapped_column(Time, nullable=True)
    frecuencia: Mapped[str] = mapped_column(String(20), nullable=False, default="unica")
    completada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )

    # Many2one hacia Proyecto (sin back_populates: Proyectos no necesita conocer a la Agenda)
    proyecto: Mapped["Proyecto | None"] = relationship()  # noqa: F821
    cumplimientos: Mapped[list["Cumplimiento"]] = relationship(
        back_populates="tarea", cascade="all, delete-orphan"
    )

    @validates("frecuencia")
    def _validate_frecuencia(self, key, value):  # propio
        if value not in FRECUENCIA_SELECTION:
            raise ValueError(f"Frecuencia no válida: {value}")
        return value

    def _validate(self) -> None:  # propio
        if not (self.titulo or "").strip():
            raise ValueError("La tarea necesita un título")
        if self.hora_fin and not self.hora_inicio:
            raise ValueError("Pon la hora de inicio antes que la de fin")
        if self.hora_inicio and self.hora_fin and self.hora_fin < self.hora_inicio:
            raise ValueError("La hora fin no puede ser antes del inicio")

    @property
    def recurrente(self) -> bool:  # propio
        return self.frecuencia != "unica"

    @property
    def frecuencia_label(self) -> str:  # propio
        return FRECUENCIA_SELECTION.get(self.frecuencia, self.frecuencia)

    @property
    def horario(self) -> str:  # propio
        """'10:00–11:30', '10:00' o '' (todo el día)."""
        if not self.hora_inicio:
            return ""
        texto = f"{self.hora_inicio:%H:%M}"
        if self.hora_fin:
            texto += f"–{self.hora_fin:%H:%M}"
        return texto

    def __repr__(self) -> str:
        return f"<Tarea id={self.id} {self.titulo} {self.fecha} ({self.frecuencia})>"


class Cumplimiento(CrudMixin, Base):
    __tablename__ = "tarea_cumplimientos"
    _orden = "hecho_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tarea_id: Mapped[int] = mapped_column(ForeignKey("tareas.id"), nullable=False)
    fecha_programada: Mapped[date] = mapped_column(Date, nullable=False)  # la que tocaba
    hecho_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # cuándo lo marcaste

    tarea: Mapped["Tarea"] = relationship(back_populates="cumplimientos")

    def __repr__(self) -> str:
        return f"<Cumplimiento tarea={self.tarea_id} {self.fecha_programada} -> {self.hecho_en}>"

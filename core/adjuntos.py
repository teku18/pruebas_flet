"""
Adjuntos de TODA la app en una sola tabla (como ir.attachment de Odoo).

Cada adjunto dice de quién es con dos columnas:
    modelo       -> "dev.pendiente", "proyecto.entrada", "agenda.tarea"…
    registro_id  -> el id de ese registro

  adjuntos
  ┌────┬──────────────────┬─────────────┬──────────────┬──────────────────────────┐
  │ id │ modelo           │ registro_id │ nombre       │ ruta (relativa a data/)  │
  ├────┼──────────────────┼─────────────┼──────────────┼──────────────────────────┤
  │  1 │ dev.pendiente    │           3 │ captura.png  │ desarrollo/3/ab12_cap…   │
  │  2 │ agenda.tarea     │          12 │ plano.pdf    │ tareas/12/cd34_plano.pdf │
  └────┴──────────────────┴─────────────┴──────────────┴──────────────────────────┘

El archivo vive en data/ (como el filestore de Odoo) y la BD solo guarda la ruta.

Lo que cambia contra una tabla por módulo:
  - No hay llave foránea "real" (registro_id puede apuntar a cualquier tabla),
    así que al borrar un registro su dueño llama Adjunto.delete_for(...).
    Es lo mismo que hace Odoo con ir.attachment (res_model + res_id).
  - Para leerlos como pro.adjuntos se usa attachments_relation() (abajo).

Para usarlos en un modelo nuevo:
    MODELO = "memoria"
    adjuntos = attachments_relation("Memoria", MODELO)   # en la clase
    ...y en su delete():  Adjunto.delete_for(MODELO, registro_id)
La pantalla usa core/adjuntos_ui.py (AttachmentsBox).
"""
import mimetypes
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, SessionLocal
from core.mixins import CrudMixin
from core.storage import delete_file


class Adjunto(CrudMixin, Base):
    __tablename__ = "adjuntos"
    __table_args__ = (Index("ix_adjuntos_modelo_registro", "modelo", "registro_id"),)
    _orden = "id asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelo: Mapped[str] = mapped_column(String(60), nullable=False)      # "agenda.tarea"
    registro_id: Mapped[int] = mapped_column(Integer, nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)     # nombre original
    ruta: Mapped[str] = mapped_column(String(500), nullable=False)       # relativa a data/
    tamano: Mapped[int | None] = mapped_column(Integer, nullable=True)   # bytes
    mimetype: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "image/png"
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )

    @staticmethod
    def guess_mimetype(nombre: str) -> str | None:  # propio
        """'foto.jpg' -> 'image/jpeg' (sirve para saber si es imagen, audio…)."""
        return mimetypes.guess_type(nombre)[0]

    # --- Consultas -----------------------------------------------------
    @classmethod
    def of(cls, modelo: str, registro_id: int) -> list["Adjunto"]:  # propio
        """Los adjuntos de un registro."""
        return cls.search(cls.modelo == modelo, cls.registro_id == registro_id)

    @classmethod
    def count_by_record(cls, modelo: str) -> dict[int, int]:  # propio
        """{registro_id: cuántos adjuntos} de un modelo (para mostrar 📎 n en listas)."""
        with SessionLocal() as session:
            consulta = (select(cls.registro_id, func.count())
                        .where(cls.modelo == modelo).group_by(cls.registro_id))
            return dict(session.execute(consulta).all())

    # --- Borrar --------------------------------------------------------
    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de la fila, borra el archivo."""
        adjunto = cls.get(registro_id)
        super().delete(registro_id)
        if adjunto:
            delete_file(adjunto.ruta)

    @classmethod
    def delete_for(cls, modelo: str, *registro_ids: int) -> None:  # propio
        """
        Borra los adjuntos (filas y archivos) de uno o varios registros.
        Lo llama el dueño al borrarse (el "ondelete=cascade" hecho a mano).
        """
        if not registro_ids:
            return
        condicion = (cls.modelo == modelo) & cls.registro_id.in_(registro_ids)
        rutas = [a.ruta for a in cls.search(condicion)]
        with SessionLocal() as session:
            session.execute(delete(cls).where(condicion))
            session.commit()
        for ruta in rutas:
            delete_file(ruta)

    def __repr__(self) -> str:
        return f"<Adjunto id={self.id} {self.modelo}:{self.registro_id} {self.nombre}>"


def attachments_relation(clase_duena: str, modelo: str):  # propio
    """
    Relación de SOLO LECTURA "registro.adjuntos" para un modelo dueño.

        class Pendiente(...):
            adjuntos = attachments_relation("Pendiente", "dev.pendiente")

    SQLAlchemy arma el JOIN:  adjuntos.modelo = 'dev.pendiente'
                              AND adjuntos.registro_id = dev_pendientes.id
    Así siguen funcionando selectinload(Pendiente.adjuntos) y p.adjuntos.
    viewonly=True: para agregar o quitar se usa Adjunto.create / Adjunto.delete.
    """
    return relationship(
        Adjunto,
        primaryjoin=(f"and_(Adjunto.modelo == '{modelo}', "
                     f"foreign(Adjunto.registro_id) == {clase_duena}.id)"),
        viewonly=True,
        order_by=Adjunto.id,
    )

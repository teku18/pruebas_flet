"""
Modelo DevAdjunto: archivo, imagen, captura o grabación de un Pendiente.

Igual que los adjuntos de la bitácora: el archivo vive en data/ y la BD solo
guarda la ruta relativa (como el filestore de Odoo).

  data/desarrollo/<pendiente_id>/<id8>_<nombre>

Va por pendiente (no por módulo) para que, si mueves un pendiente a otro
módulo, sus archivos no cambien de lugar.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base
from core.mixins import CrudMixin
from core.storage import DATA_DIR, delete_file

DEV_ADJUNTOS_DIR = DATA_DIR / "desarrollo"


class DevAdjunto(CrudMixin, Base):
    __tablename__ = "dev_adjuntos"
    _orden = "id asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pendiente_id: Mapped[int] = mapped_column(ForeignKey("dev_pendientes.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)    # nombre original
    ruta: Mapped[str] = mapped_column(String(500), nullable=False)      # relativa a data/
    tamano: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes
    creado_en: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=datetime.now
    )

    pendiente: Mapped["Pendiente"] = relationship(back_populates="adjuntos")  # noqa: F821

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Además de la fila, borra el archivo."""
        adjunto = cls.get(registro_id)
        super().delete(registro_id)
        if adjunto:
            delete_file(adjunto.ruta)

    def __repr__(self) -> str:
        return f"<DevAdjunto id={self.id} {self.nombre}>"

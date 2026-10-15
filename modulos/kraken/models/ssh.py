"""
Comandos guardados de SSH: "Reiniciar Odoo" = sudo systemctl restart odoo.

  equipo_id vacío  -> sirve para TODOS tus servidores
  confirmar        -> pregunta "¿Seguro?" antes de correrlo (por defecto, sí)

Si el comando empieza con `sudo`, la app le da la contraseña del servidor a
sudo por su entrada (sudo -S), así no se queda esperando.
"""
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, or_
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.mixins import CrudMixin

COMANDOS_INICIALES = [
    ("Reiniciar Odoo", "sudo systemctl restart odoo"),
    ("Reiniciar PostgreSQL", "sudo systemctl restart postgresql"),
    ("Reiniciar Nginx", "sudo systemctl restart nginx"),
    ("¿Qué ocupa el disco?", "sudo du -xh / --max-depth=2 2>/dev/null | sort -rh | head -15"),
]


class ComandoSsh(CrudMixin, Base):
    __tablename__ = "kt_ssh_comandos"
    _orden = "secuencia asc, nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("kt_equipos.id"), nullable=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    comando: Mapped[str] = mapped_column(Text, nullable=False)
    confirmar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")
        if not (self.comando or "").strip():
            raise ValueError("Escribe el comando")

    @classmethod
    def for_server(cls, equipo_id: int) -> list["ComandoSsh"]:  # propio
        """Los de ese servidor + los de todos."""
        return cls.search(or_(cls.equipo_id.is_(None), cls.equipo_id == equipo_id))

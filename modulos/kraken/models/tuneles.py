"""
Túneles públicos: una URL https://… (ngrok o Cloudflare) hacia un puerto de
uno de tus equipos SSH. Lo mismo que correr `ngrok http 8069` en la terminal,
pero desde el cel.

  servicio   "ngrok" (tu cuenta; con dominio fijo si tienes uno) |
             "cloudflare" (sin cuenta; la URL cambia en cada arranque)
  receptor   si es el túnel de un receptor de webhooks (si no: "Exponer puerto")
  clave      su carpeta en el equipo: ~/.controlkraken/tuneles/<clave>/
  url        la última URL que dio el servicio (para mostrarla sin conectar)
"""
import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.mixins import CrudMixin

SERVICIOS = {"ngrok": "ngrok", "cloudflare": "Cloudflare"}


class TunelPublico(CrudMixin, Base):
    __tablename__ = "kt_tuneles_publicos"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("kt_equipos.id"), nullable=True)
    puerto: Mapped[int] = mapped_column(Integer, nullable=False, default=8069)
    servicio: Mapped[str] = mapped_column(String(12), nullable=False, default="ngrok")
    dominio: Mapped[str | None] = mapped_column(String(255), nullable=True)  # ngrok fijo
    receptor_id: Mapped[int | None] = mapped_column(ForeignKey("kt_webhooks.id"), nullable=True)
    clave: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def _validate(self) -> None:  # propio
        self.servicio = self.servicio or "ngrok"
        self.puerto = 8069 if self.puerto is None else self.puerto
        if not self.clave:
            self.clave = secrets.token_hex(6)
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre (p. ej. Odoo dev)")
        if not self.equipo_id:
            raise ValueError("Elige el equipo")
        if self.servicio not in SERVICIOS:
            raise ValueError("Elige ngrok o Cloudflare")
        if not 1 <= int(self.puerto) <= 65535:
            raise ValueError("El puerto debe estar entre 1 y 65535")
        if self.dominio:
            d = self.dominio.strip().removeprefix("https://").removeprefix("http://").strip("/")
            if " " in d or "." not in d:
                raise ValueError("El dominio fijo se ve como algo.ngrok-free.app")
            self.dominio = d
        if self.servicio != "ngrok":
            self.dominio = None

    @property
    def carpeta(self) -> str:  # propio
        return f".controlkraken/tuneles/{self.clave}"

    @classmethod
    def of_receiver(cls, receptor_id: int) -> "TunelPublico | None":  # propio
        encontrados = cls.search(cls.receptor_id == receptor_id)
        return encontrados[0] if encontrados else None

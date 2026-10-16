"""
Webhooks: receptores en tus servidores y lo que les llega.

  Receptor  1 ──< N  WebhookRecibido      Receptor 1 ── 0..1 TunelPublico (URL https)
  (en un equipo SSH:          (copia local de cada webhook: método, headers,
   puerto + clave secreta)     body… se guarda y se respalda como todo Kraken)

La URL pública es  http://<host del equipo>:<puerto>/<clave>.
`ultimo_id` = hasta qué webhook del servidor ya trajo la app (para pedir solo
lo nuevo).
"""
import secrets
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, delete,
                        func, select)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

PUERTO_POR_DEFECTO = 9555
RESPUESTA_POR_DEFECTO = '{"ok": true}'


def new_key() -> str:  # propio
    """Clave de la URL: difícil de adivinar (24 caracteres)."""
    return secrets.token_urlsafe(18)


class Receptor(CrudMixin, Base):
    __tablename__ = "kt_webhooks"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("kt_equipos.id"), nullable=True)
    puerto: Mapped[int] = mapped_column(Integer, nullable=False, default=PUERTO_POR_DEFECTO)
    clave: Mapped[str] = mapped_column(String(64), nullable=False, default=new_key)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    respuesta: Mapped[str | None] = mapped_column(Text, nullable=True,
                                                  default=RESPUESTA_POR_DEFECTO)
    max_guardados: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    reenviar: Mapped[list | None] = mapped_column(JSON, nullable=True)   # ["https://…", …]
    ultimo_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    instalado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def _validate(self) -> None:  # propio
        # los default de las columnas aún no se aplican aquí (ver nota técnica)
        self.puerto = PUERTO_POR_DEFECTO if self.puerto is None else self.puerto
        self.status = 200 if self.status is None else self.status
        self.max_guardados = 500 if self.max_guardados is None else self.max_guardados
        self.ultimo_id = self.ultimo_id or 0
        self.instalado = bool(self.instalado)
        if self.respuesta is None and self.id is None:
            self.respuesta = RESPUESTA_POR_DEFECTO
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre al receptor")
        if not self.equipo_id:
            raise ValueError("Elige el servidor donde va a escuchar")
        if not 1024 <= int(self.puerto or 0) <= 65535:
            raise ValueError("El puerto debe estar entre 1024 y 65535 (sin root)")
        if not 100 <= int(self.status or 0) <= 599:
            raise ValueError("El código de respuesta debe estar entre 100 y 599")
        if not 10 <= int(self.max_guardados or 0) <= 10_000:
            raise ValueError("Guarda entre 10 y 10,000 webhooks")
        if not self.clave:
            self.clave = new_key()

    @property
    def carpeta(self) -> str:  # propio
        """Dónde vive en el servidor (relativa al HOME del usuario SSH)."""
        return f".controlkraken/webhooks/{self.clave}"

    def url(self, host: str) -> str:  # propio
        return f"http://{host}:{self.puerto}/{self.clave}"

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Borra el receptor CON lo recibido (desinstalarlo del servidor va aparte)."""
        with SessionLocal() as session:
            session.execute(delete(WebhookRecibido).where(
                WebhookRecibido.receptor_id == registro_id))
            session.commit()
        super().delete(registro_id)


class WebhookRecibido(CrudMixin, Base):
    __tablename__ = "kt_webhooks_recibidos"
    _orden = "recibido_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    receptor_id: Mapped[int] = mapped_column(ForeignKey("kt_webhooks.id"), nullable=False)
    remoto_id: Mapped[int] = mapped_column(Integer, nullable=False)   # id en el servidor
    recibido_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # hora local
    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    ruta: Mapped[str] = mapped_column(Text, nullable=False, default="/")  # después de la clave
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[list | None] = mapped_column(JSON, nullable=True)     # [[k, v], …]
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    es_base64: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tamano: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # [{"url", "status", "ms", "error", "respuesta"}] (lo que contestó cada destino)
    reenvios: Mapped[list | None] = mapped_column(JSON, nullable=True)

    @classmethod
    def of(cls, receptor_id: int, limite: int = 500) -> list["WebhookRecibido"]:  # propio
        with SessionLocal() as session:
            return list(session.scalars(select(cls).where(cls.receptor_id == receptor_id)
                                        .order_by(cls.remoto_id.desc()).limit(limite)))

    @classmethod
    def unseen(cls, receptor_id: int) -> int:  # propio
        with SessionLocal() as session:
            return session.scalar(select(func.count(cls.id)).where(
                cls.receptor_id == receptor_id, cls.visto.is_(False))) or 0

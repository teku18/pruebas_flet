"""
Ajustes de Kraken Tools: UNA sola fila (id = 1), en la BD para que viajen en
el respaldo (a diferencia de la carpeta de respaldos, que es de cada equipo).

  historial_max      cuántos envíos HTTP se guardan          (0 = sin límite)
  respuesta_max_kb   cuánto de cada respuesta se guarda (KB)  (0 = completa)
  timeout_s          cuánto esperar una respuesta
  entorno_id         el entorno elegido ({{variables}})
  dns_servidor       a quién le pregunta la herramienta DNS (Cloudflare por defecto)
  red_historial_max  cuántas pruebas de Red se guardan            (0 = sin límite)
"""
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

HISTORIAL_OPCIONES = {50: "50", 100: "100", 200: "200", 500: "500", 1000: "1,000",
                      0: "Sin límite"}
RESPUESTA_OPCIONES = {64: "64 KB", 256: "256 KB", 1024: "1 MB", 5120: "5 MB",
                      20480: "20 MB", 0: "Completa"}
TIMEOUT_OPCIONES = {10: "10 s", 30: "30 s", 60: "1 min", 120: "2 min", 300: "5 min"}
DNS_POR_DEFECTO = "1.1.1.1"
DNS_SUGERIDOS = {"1.1.1.1": "Cloudflare", "8.8.8.8": "Google", "9.9.9.9": "Quad9",
                 "208.67.222.222": "OpenDNS"}


class Ajustes(CrudMixin, Base):
    __tablename__ = "kt_ajustes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    historial_max: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    respuesta_max_kb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    timeout_s: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    entorno_id: Mapped[int | None] = mapped_column(ForeignKey("kt_entornos.id"), nullable=True)
    dns_servidor: Mapped[str] = mapped_column(String(100), nullable=False,
                                              default=DNS_POR_DEFECTO)
    red_historial_max: Mapped[int] = mapped_column(Integer, nullable=False, default=200)

    @classmethod
    def current(cls) -> "Ajustes":  # propio
        """La fila de ajustes (la crea con los valores de fábrica si no está)."""
        with SessionLocal() as session:
            fila = session.get(cls, 1)
            if fila is None:
                fila = cls(id=1, historial_max=200, respuesta_max_kb=256, timeout_s=30,
                           dns_servidor=DNS_POR_DEFECTO, red_historial_max=200)
                session.add(fila)
                session.commit()
                session.refresh(fila)
            return fila

    @classmethod
    def change(cls, **valores) -> "Ajustes":  # propio
        cls.current()
        return cls.update(1, **valores)

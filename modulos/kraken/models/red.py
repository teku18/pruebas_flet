"""
Modelos de la herramienta Red:

  Equipo        tus servidores, router, PC… (los usan Red y SSH)
                con usuario SSH = aparece en la herramienta SSH
  HistorialRed  cada prueba que corres: herramienta, a qué, resumen y detalle

El detalle se guarda como JSON (el resultado completo de la prueba): así abrir
una prueba vieja pinta exactamente lo mismo que cuando la corriste.
"""
import re
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base
from core.mixins import CrudMixin

SERVICIOS_POR_DEFECTO = "odoo postgresql nginx"
LOG_POR_DEFECTO = "/var/log/odoo/odoo-server.log"
MAC = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$|^[0-9A-Fa-f]{12}$")


def parse_ports(texto: str | None) -> list[int]:  # propio
    """'22, 80,443 8000-8002' -> [22, 80, 443, 8000, 8001, 8002] (sin repetir, en orden)."""
    puertos: list[int] = []
    for parte in re.split(r"[,\s]+", (texto or "").strip()):
        if not parte:
            continue
        if "-" in parte:
            ini, _, fin = parte.partition("-")
            if not (ini.isdigit() and fin.isdigit()) or int(ini) > int(fin):
                raise ValueError(f"Rango no válido: {parte}")
            if int(fin) - int(ini) > 5000:
                raise ValueError("Un rango puede tener hasta 5,000 puertos")
            rango = range(int(ini), int(fin) + 1)
        elif parte.isdigit():
            rango = [int(parte)]
        else:
            raise ValueError(f"Puerto no válido: {parte}")
        for p in rango:
            if not 1 <= p <= 65535:
                raise ValueError(f"Los puertos van de 1 a 65535 ({p})")
            if p not in puertos:
                puertos.append(p)
    return puertos


class Equipo(CrudMixin, Base):
    __tablename__ = "kt_equipos"
    _orden = "nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)        # IP o dominio
    puertos: Mapped[str | None] = mapped_column(String(200), nullable=True)  # "22, 80, 443"
    mac: Mapped[str | None] = mapped_column(String(17), nullable=True)    # Wake-on-LAN
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    # --- SSH (1.7.0). Sin usuario = no es servidor SSH ---
    ssh_usuario: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ssh_puerto: Mapped[int | None] = mapped_column(Integer, nullable=True)       # 22
    ssh_clave: Mapped[str | None] = mapped_column(Text, nullable=True)            # texto normal
    ssh_huella: Mapped[str | None] = mapped_column(String(120), nullable=True)    # del servidor
    ssh_servicios: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ssh_log: Mapped[str | None] = mapped_column(String(300), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

    @property
    def tiene_ssh(self) -> bool:  # propio
        return bool((self.ssh_usuario or "").strip())

    @property
    def servicios(self) -> list[str]:  # propio
        """Servicios a vigilar en el panel ('odoo postgresql nginx' por defecto)."""
        return (self.ssh_servicios or SERVICIOS_POR_DEFECTO).replace(",", " ").split()

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre")
        if self.ssh_puerto is not None and not 1 <= int(self.ssh_puerto) <= 65535:
            raise ValueError("El puerto SSH va de 1 a 65535")
        if not (self.host or "").strip() or " " in self.host.strip():
            raise ValueError("Escribe la IP o el dominio (sin espacios)")
        parse_ports(self.puertos)  # lanza ValueError si están mal
        if self.mac and not MAC.match(self.mac.strip()):
            raise ValueError("La MAC va así: AA:BB:CC:DD:EE:FF")

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        iguales = [e for e in cls.search(func.lower(cls.nombre) == nombre.strip().lower())
                   if e.id != excluir_id]
        if iguales:
            raise ValueError("Ya tienes un equipo con ese nombre")


class HistorialRed(CrudMixin, Base):
    __tablename__ = "kt_historial_red"
    _orden = "creado_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    herramienta: Mapped[str] = mapped_column(String(20), nullable=False)  # ping, puertos…
    objetivo: Mapped[str] = mapped_column(String(255), nullable=False)    # host, dominio, MAC
    resumen: Mapped[str] = mapped_column(String(255), nullable=False)     # "4/4 · 12 ms"
    exito: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detalle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tiempo_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

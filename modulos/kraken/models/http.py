"""
Modelos del cliente HTTP (tipo Postman):

  Coleccion  1 ──< N  Peticion  1 ──< N  HistorialHttp
  (carpetas)          (guardadas)        (cada envío; sin petición = "suelto")
  Entorno  (Globales + los tuyos: Local, Producción…)

Las listas clave/valor (params, headers, formulario, variables) se guardan
como JSON:  [{"clave": "page", "valor": "2", "activo": true}, …]
Así una petición es UNA fila y se copia o respalda completa.

Los valores (tokens, contraseñas) se guardan tal cual, en texto normal: es tu
app y tu respaldo. Si un día quieres cifrarlos, todo pasa por services.py.
"""
from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func,
                        select, update)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base, SessionLocal
from core.mixins import CrudMixin

METODOS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
BODY_SELECTION = {"ninguno": "Ninguno", "json": "JSON", "texto": "Texto",
                  "form": "Formulario"}
AUTH_SELECTION = {"ninguna": "Ninguna", "bearer": "Bearer token", "basic": "Usuario y contraseña"}


class Coleccion(CrudMixin, Base):
    __tablename__ = "kt_colecciones"
    _orden = "secuencia asc, nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

    peticiones: Mapped[list["Peticion"]] = relationship(
        back_populates="coleccion", lazy="selectin", order_by="Peticion.secuencia, Peticion.id")

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre a la colección")

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        iguales = [c for c in cls.search(func.lower(cls.nombre) == nombre.strip().lower())
                   if c.id != excluir_id]
        if iguales:
            raise ValueError("Ya existe una colección con ese nombre")

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Borra la colección CON sus peticiones (el historial se queda, suelto)."""
        with SessionLocal() as session:
            ids = list(session.scalars(select(Peticion.id).where(
                Peticion.coleccion_id == registro_id)))
        for pid in ids:
            Peticion.delete(pid)
        super().delete(registro_id)


class Peticion(CrudMixin, Base):
    __tablename__ = "kt_peticiones"
    _orden = "secuencia asc, id asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coleccion_id: Mapped[int | None] = mapped_column(ForeignKey("kt_colecciones.id"),
                                                     nullable=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    metodo: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    params: Mapped[list | None] = mapped_column(JSON, nullable=True)
    headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    body_tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="ninguno")
    body: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON o texto
    form: Mapped[list | None] = mapped_column(JSON, nullable=True)     # body "form"
    auth_tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="ninguna")
    auth_usuario: Mapped[str | None] = mapped_column(Text, nullable=True)  # o el token
    auth_clave: Mapped[str | None] = mapped_column(Text, nullable=True)
    secuencia: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                     default=datetime.now)

    coleccion: Mapped["Coleccion | None"] = relationship(back_populates="peticiones",
                                                         lazy="joined")

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre a la petición")
        if self.metodo not in METODOS:
            raise ValueError(f"Método no válido: {self.metodo}")

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        """Su historial no se borra: queda como envío suelto."""
        with SessionLocal() as session:
            session.execute(update(HistorialHttp).where(HistorialHttp.peticion_id == registro_id)
                            .values(peticion_id=None))
            session.commit()
        super().delete(registro_id)


class Entorno(CrudMixin, Base):
    """
    Variables para {{así}}. "Globales" (es_global) siempre aplica; el entorno
    elegido (Ajustes.entorno_id) se pone encima: si ambos tienen `base_url`,
    gana el del entorno.
    """
    __tablename__ = "kt_entornos"
    _orden = "es_global desc, nombre asc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    es_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variables: Mapped[list | None] = mapped_column(JSON, nullable=True)

    def _validate(self) -> None:  # propio
        if not (self.nombre or "").strip():
            raise ValueError("Ponle un nombre al entorno")

    @classmethod
    def check_unique(cls, nombre: str, excluir_id: int | None = None) -> None:  # propio
        iguales = [e for e in cls.search(func.lower(cls.nombre) == nombre.strip().lower())
                   if e.id != excluir_id]
        if iguales:
            raise ValueError("Ya existe un entorno con ese nombre")

    @classmethod
    def globals_(cls) -> "Entorno":  # propio
        """El entorno de variables globales (lo crea la migración; aquí por si falta)."""
        existentes = cls.search(cls.es_global.is_(True))
        if existentes:
            return existentes[0]
        return cls.create(nombre="Globales", es_global=True, variables=[])

    @classmethod
    def delete(cls, registro_id: int) -> None:  # propio
        from modulos.kraken.models.ajustes import Ajustes

        entorno = cls.get(registro_id)
        if entorno and entorno.es_global:
            raise ValueError("Las variables globales no se pueden borrar")
        if Ajustes.current().entorno_id == registro_id:
            Ajustes.change(entorno_id=None)
        super().delete(registro_id)


class HistorialHttp(CrudMixin, Base):
    __tablename__ = "kt_historial_http"
    _orden = "creado_en desc, id desc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    peticion_id: Mapped[int | None] = mapped_column(ForeignKey("kt_peticiones.id"),
                                                    nullable=True)
    # Lo que se mandó, YA con las {{variables}} reemplazadas
    metodo: Mapped[str] = mapped_column(String(10), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    req_headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    req_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # La petición tal como estaba en el editor (para "abrir de nuevo")
    borrador: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Lo que regresó
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(80), nullable=True)   # "Not Found"
    tiempo_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tamano: Mapped[int | None] = mapped_column(Integer, nullable=True)      # bytes reales
    resp_headers: Mapped[list | None] = mapped_column(JSON, nullable=True)
    resp_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    recortado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)          # sin respuesta
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False,
                                                default=datetime.now)

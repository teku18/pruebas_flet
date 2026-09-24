"""
Mixins reutilizables para los modelos.

CrudMixin da a cualquier modelo los métodos de acceso a datos
(create, get, search, search_all, update, delete) sin repetirlos.
Es parecido a lo que un modelo de Odoo hereda de models.Model.

Uso:
    class MiModelo(CrudMixin, Base):
        _orden = "nombre asc"          # como _order en Odoo (opcional)

        def _validar(self):            # como @api.constrains (opcional)
            if ...:
                raise ValueError("...")
"""
from sqlalchemy import select, text

from database import SessionLocal


class CrudMixin:
    # Orden por defecto de search() / search_all(), en SQL.
    # Cada modelo puede redefinirlo, p. ej. "fecha desc, id desc".
    _orden = "id desc"

    # ------------------------------------------------------------------
    # Validación (se llama antes de guardar en create y update)
    # ------------------------------------------------------------------
    def _validar(self) -> None:
        """Redefínelo en el modelo para validar reglas entre campos."""

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @classmethod
    def get(cls, registro_id: int):
        """Un registro por id, o None si no existe."""
        with SessionLocal() as session:
            return session.get(cls, registro_id)

    @classmethod
    def search(cls, *condiciones) -> list:
        """
        Registros que cumplen las condiciones, en el orden de _orden.
        Ejemplo:  Movimiento.search(Movimiento.periodo_id == 3)
        """
        with SessionLocal() as session:
            consulta = select(cls).where(*condiciones).order_by(text(cls._orden))
            return list(session.scalars(consulta))

    @classmethod
    def search_all(cls) -> list:
        return cls.search()

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    @classmethod
    def create(cls, **valores):
        with SessionLocal() as session:
            registro = cls(**valores)
            registro._validar()
            session.add(registro)
            session.commit()
            session.refresh(registro)
            return registro

    @classmethod
    def update(cls, registro_id: int, **valores):
        with SessionLocal() as session:
            registro = cls._obtener_o_error(session, registro_id)
            for campo, valor in valores.items():
                setattr(registro, campo, valor)
            registro._validar()  # si falla, no se hace commit (se descarta)
            session.commit()
            session.refresh(registro)
            return registro

    @classmethod
    def delete(cls, registro_id: int) -> None:
        with SessionLocal() as session:
            registro = cls._obtener_o_error(session, registro_id)
            session.delete(registro)
            session.commit()

    # ------------------------------------------------------------------
    @classmethod
    def _obtener_o_error(cls, session, registro_id: int):
        registro = session.get(cls, registro_id)
        if registro is None:
            raise ValueError(f"No existe {cls.__name__} con id={registro_id}")
        return registro

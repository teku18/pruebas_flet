"""
Modelos de la aplicación (como la carpeta models/ de un addon de Odoo).

Importar ambos aquí es importante: SQLAlchemy necesita conocer las dos
clases para resolver las relaciones entre ellas ("Periodo" <-> "Movimiento").
"""
from models.movimiento import (
    INVERSION_SELECTION,
    PLATAFORMA_SELECTION,
    TIPO_SELECTION,
    Movimiento,
)
from models.periodo import Periodo

__all__ = [
    "INVERSION_SELECTION",
    "PLATAFORMA_SELECTION",
    "TIPO_SELECTION",
    "Movimiento",
    "Periodo",
]
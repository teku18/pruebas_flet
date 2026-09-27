"""
Modelos del módulo Finanzas (como la carpeta models/ de un addon de Odoo).

Importarlos todos aquí es importante: SQLAlchemy necesita conocer las clases
para resolver las relaciones entre ellas por nombre ("Periodo", "Plataforma"...).
"""
from modulos.finanzas.models.catalogo import Inversion, Plataforma
from modulos.finanzas.models.movimiento import (
    SIGNO_TIPO,
    TIPO_SELECTION,
    TIPOS_GASTO,
    TIPOS_INGRESO,
    TIPOS_MANUALES,
    TIPOS_TRASPASO,
    Movimiento,
)
from modulos.finanzas.models.periodo import Periodo

__all__ = [
    "SIGNO_TIPO",
    "TIPO_SELECTION",
    "TIPOS_GASTO",
    "TIPOS_INGRESO",
    "TIPOS_MANUALES",
    "TIPOS_TRASPASO",
    "Inversion",
    "Movimiento",
    "Periodo",
    "Plataforma",
]

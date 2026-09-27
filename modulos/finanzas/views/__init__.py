"""Pantallas del módulo Finanzas (vista + sus acciones, una clase por pantalla)."""
from modulos.finanzas.views.ajustes import FinanceSettingsView
from modulos.finanzas.views.catalogos import CatalogView
from modulos.finanzas.views.movimientos import MovementsView
from modulos.finanzas.views.periodos import PeriodsView
from modulos.finanzas.views.reportes import ReportsView
from modulos.finanzas.views.traspaso import TransferView

__all__ = [
    "CatalogView", "FinanceSettingsView", "MovementsView", "PeriodsView",
    "ReportsView", "TransferView",
]

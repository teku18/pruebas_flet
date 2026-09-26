"""
Módulos de ControlKraken (como los addons instalados en Odoo).

El orden de esta lista es el orden de las tarjetas en la pantalla de inicio.
Para agregar un módulo: créalo en modulos/<nombre>/ y súmalo aquí.
Si tiene modelos, agrégalo también en core/database.py -> import_models().
"""
from modulos.agenda import AgendaModule
from modulos.configuracion import ConfiguracionModule
from modulos.finanzas import FinanzasModule
from modulos.memorias import MemoriasModule
from modulos.proyectos import ProyectosModule

MODULES = [
    FinanzasModule,
    ProyectosModule,
    MemoriasModule,
    AgendaModule,
    ConfiguracionModule,
]

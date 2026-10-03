"""Pantallas del módulo Proyectos."""
from modulos.proyectos.views.ajustes import ProjectSettingsView
from modulos.proyectos.views.bitacora import LogView
from modulos.proyectos.views.proyectos import ProjectsView

__all__ = ["LogView", "ProjectSettingsView", "ProjectsView"]

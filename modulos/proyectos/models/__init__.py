"""Modelos del módulo Proyectos: Proyecto > Entrada (bitácora) > Adjunto + catálogos."""
from modulos.proyectos.models.catalogos import (
    CLASE_ETAPA_SELECTION,
    COLORES_CATALOGO,
    ICONOS_ENTRADA,
    EtapaProyecto,
    EtapaTarea,
    TipoEntrada,
)
from modulos.proyectos.models.entrada import Adjunto, Entrada
from modulos.proyectos.models.proyecto import (
    ADJUNTOS_DIR,
    TIPO_PROYECTO_SELECTION,
    Proyecto,
)

__all__ = [
    "ADJUNTOS_DIR",
    "CLASE_ETAPA_SELECTION",
    "COLORES_CATALOGO",
    "ICONOS_ENTRADA",
    "TIPO_PROYECTO_SELECTION",
    "Adjunto",
    "Entrada",
    "EtapaProyecto",
    "EtapaTarea",
    "Proyecto",
    "TipoEntrada",
]

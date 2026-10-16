"""
Modelos de Kraken Tools (todas las tablas empiezan con kt_).

  Ajustes          1 fila: tamaño del historial HTTP, de cada respuesta guardada…
  Coleccion  1 ──< N  Peticion        (tus peticiones guardadas, como en Postman)
  Entorno                              (variables {{base_url}}, {{token}}…)
  HistorialHttp                        (cada envío: lo mandado y lo recibido)
  ConexionSqlite 1 ──< N ConsultaSqlite (bases .db y sus consultas)
  Equipo, HistorialRed                  (Red: tus equipos y las pruebas que corres)
  ComandoSsh                            (SSH: "Reiniciar Odoo"… con confirmación)
  Receptor 1 ──< N WebhookRecibido      (Webhooks: receptor en tu servidor y lo que llega)
"""
from modulos.kraken.models.ajustes import Ajustes
from modulos.kraken.models.http import (
    AUTH_SELECTION,
    BODY_SELECTION,
    METODOS,
    Coleccion,
    Entorno,
    HistorialHttp,
    Peticion,
)
from modulos.kraken.models.red import Equipo, HistorialRed, parse_ports
from modulos.kraken.models.ssh import ComandoSsh
from modulos.kraken.models.sqlite import BASES_DIR, ConexionSqlite, ConsultaSqlite
from modulos.kraken.models.webhooks import Receptor, WebhookRecibido

__all__ = ["AUTH_SELECTION", "Ajustes", "BASES_DIR", "BODY_SELECTION", "Coleccion", "ComandoSsh",
           "ConexionSqlite", "ConsultaSqlite", "Entorno", "Equipo", "HistorialHttp",
           "HistorialRed", "METODOS", "Peticion", "Receptor", "WebhookRecibido", "parse_ports"]

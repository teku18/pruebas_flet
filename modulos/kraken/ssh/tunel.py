"""
Túnel SSH ("port forwarding" local, como `ssh -L 15432:localhost:5432 servidor`).

  celular 127.0.0.1:<puerto libre>  ══ SSH (22, cifrado) ══>  servidor -> localhost:5432

Abre un puerto en el celular (solo para la propia app: 127.0.0.1) y cada
conexión que llega ahí se manda por la sesión SSH como un canal
"direct-tcpip" hacia destino:puerto, VISTO DESDE EL SERVIDOR. Para el Postgres
del servidor la conexión viene de "localhost": no hay que abrir el 5432 a internet.

Funciona con cualquier librería (pg8000, PyMySQL, httpx…): ellas solo ven un
host y un puerto normales.

Los túneles se reusan (abrir SSH tarda): tunnel_for() regresa uno abierto si ya
existe para ese equipo y destino, y close_all() los cierra (al salir de la base).
"""
import logging
import select
import socket
import threading

from modulos.kraken.models import Equipo
from modulos.kraken.ssh.conexion import Sesion

# Al cerrar un túnel paramiko escribe "Socket exception: Connection reset" como ERROR: es ruido.
logging.getLogger("paramiko.transport").setLevel(logging.CRITICAL)


class Tunel:
    def __init__(self, equipo: Equipo, destino: str, puerto_destino: int):
        self.equipo = equipo
        self.destino, self.puerto_destino = destino, puerto_destino
        self.sesion: Sesion | None = None
        self.servidor: socket.socket | None = None
        self.puerto_local = 0
        self._vivo = False

    @property
    def activo(self) -> bool:  # propio
        return self._vivo and self.sesion is not None and self.sesion.abierta

    def start(self) -> "Tunel":  # propio
        self.sesion = Sesion(self.equipo)
        self.sesion.open()  # puede lanzar HuellaCambio o errores de conexión
        self.servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.servidor.bind(("127.0.0.1", 0))  # 0 = el sistema elige un puerto libre
        self.servidor.listen(8)
        self.puerto_local = self.servidor.getsockname()[1]
        self._vivo = True
        threading.Thread(target=self._accept, daemon=True).start()
        return self

    def _accept(self):  # propio
        while self._vivo:
            try:
                cliente, origen = self.servidor.accept()
            except OSError:
                return  # se cerró el túnel
            try:
                canal = self.sesion.cliente.get_transport().open_channel(
                    "direct-tcpip", (self.destino, self.puerto_destino), origen, timeout=10)
            except Exception:  # noqa: BLE001  (el servidor no deja o el destino no existe)
                cliente.close()
                continue
            threading.Thread(target=self._pump, args=(cliente, canal), daemon=True).start()

    @staticmethod
    def _pump(cliente: socket.socket, canal):  # propio
        """Pasa bytes en los dos sentidos hasta que uno cierre."""
        try:
            while True:
                listos, _, _ = select.select([cliente, canal], [], [], 60)
                if cliente in listos:
                    datos = cliente.recv(65536)
                    if not datos:
                        break
                    canal.sendall(datos)
                if canal in listos:
                    datos = canal.recv(65536)
                    if not datos:
                        break
                    cliente.sendall(datos)
        except OSError:
            pass
        finally:
            canal.close()
            cliente.close()

    def stop(self):  # propio
        self._vivo = False
        if self.servidor is not None:
            try:
                self.servidor.close()
            except OSError:
                pass
        if self.sesion is not None:
            self.sesion.close()


_ABIERTOS: dict[tuple, Tunel] = {}
_CANDADO = threading.Lock()


def tunnel_for(equipo_id: int, destino: str, puerto: int) -> Tunel:  # propio
    """Un túnel abierto hacia destino:puerto por ese equipo (lo reusa si ya hay uno)."""
    clave = (equipo_id, destino, puerto)
    with _CANDADO:
        actual = _ABIERTOS.get(clave)
        if actual is not None and actual.activo:
            return actual
        if actual is not None:
            actual.stop()
        equipo = Equipo.get(equipo_id)
        if equipo is None or not equipo.tiene_ssh:
            raise ValueError("El equipo del túnel ya no existe o no tiene acceso SSH")
        nuevo = Tunel(equipo, destino, puerto).start()
        _ABIERTOS[clave] = nuevo
        return nuevo


def close_all():  # propio
    with _CANDADO:
        for t in _ABIERTOS.values():
            t.stop()
        _ABIERTOS.clear()

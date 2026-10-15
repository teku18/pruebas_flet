"""
La sesión SSH con un servidor (paramiko).

Huella del servidor (como el "¿Confías en este equipo?" de `ssh` la primera vez):
  - la primera conexión GUARDA la huella del servidor en el equipo
  - las siguientes la COMPARAN: si cambió, NO se conecta (puede ser que
    reinstalaron el servidor... o que alguien se hace pasar por él) y la
    pantalla pregunta si confías en la nueva.

sudo: si el comando empieza con `sudo`, se cambia por `sudo -S -p ''` y se le
da la contraseña por la entrada estándar. Así no se queda esperando.

Todo es bloqueante (paramiko no es async): las pantallas lo llaman con
asyncio.to_thread para no congelarse.
"""
import socket
import time
from dataclasses import dataclass

import paramiko

from modulos.kraken.models import Equipo

TIMEOUT_CONEXION = 10


class HuellaCambio(Exception):
    """El servidor presentó otra huella que la guardada."""

    def __init__(self, guardada: str, nueva: str):
        super().__init__("La huella del servidor cambió")
        self.guardada, self.nueva = guardada, nueva


class _Recordar(paramiko.MissingHostKeyPolicy):
    """No rechaza llaves desconocidas: la revisión la hacemos nosotros (TOFU)."""

    def missing_host_key(self, client, hostname, key):  # noqa: D401
        return


def fingerprint(llave: paramiko.PKey) -> str:  # propio
    """'ssh-ed25519 SHA256:zTVm0z6…' (lo mismo que muestra `ssh`)."""
    return f"{llave.get_name()} {llave.fingerprint}"


@dataclass
class Salida:
    codigo: int
    texto: str
    errores: str
    tiempo_ms: int

    @property
    def ok(self) -> bool:  # propio
        return self.codigo == 0


def friendly(ex: Exception, e: Equipo) -> str:  # propio
    """El error de conexión en palabras."""
    destino = f"{e.host}:{e.ssh_puerto or 22}"
    if isinstance(ex, paramiko.AuthenticationException):
        return f"Usuario o contraseña incorrectos ({e.ssh_usuario}@{e.host})"
    if isinstance(ex, (socket.timeout, TimeoutError)):
        return f"{destino} no contestó a tiempo (¿encendido? ¿misma red? ¿firewall?)"
    if isinstance(ex, paramiko.ssh_exception.NoValidConnectionsError):
        return (f"Nadie atiende SSH en {destino}: el servidor SSH está apagado, el puerto es "
                "otro o un firewall lo bloquea")
    if isinstance(ex, socket.gaierror):
        return f"No se encontró «{e.host}»"
    if isinstance(ex, paramiko.SSHException):
        return f"Error de SSH: {ex}"
    return f"{type(ex).__name__}: {ex}"


class Sesion:
    """Una conexión abierta. Úsala y ciérrala (o `with Sesion(e) as s:`)."""

    def __init__(self, equipo: Equipo):
        self.equipo = equipo
        self.cliente: paramiko.SSHClient | None = None
        self.huella: str = ""
        self.ms_conexion = 0

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def open(self, aceptar_huella: str | None = None):  # propio
        """
        Conecta. Lanza HuellaCambio si la huella no es la guardada (salvo que
        `aceptar_huella` sea justo la nueva: el usuario dijo "confío").
        """
        e = self.equipo
        cliente = paramiko.SSHClient()
        cliente.set_missing_host_key_policy(_Recordar())
        inicio = time.perf_counter()
        cliente.connect(e.host, port=e.ssh_puerto or 22, username=e.ssh_usuario,
                        password=e.ssh_clave or None, timeout=TIMEOUT_CONEXION,
                        banner_timeout=TIMEOUT_CONEXION, auth_timeout=TIMEOUT_CONEXION,
                        look_for_keys=False, allow_agent=False)
        self.ms_conexion = round((time.perf_counter() - inicio) * 1000)
        self.huella = fingerprint(cliente.get_transport().get_remote_server_key())
        if e.ssh_huella and e.ssh_huella != self.huella and aceptar_huella != self.huella:
            cliente.close()
            raise HuellaCambio(e.ssh_huella, self.huella)
        if e.ssh_huella != self.huella:  # primera vez (o aceptada): se recuerda
            Equipo.update(e.id, ssh_huella=self.huella)
            e.ssh_huella = self.huella
        transporte = cliente.get_transport()
        transporte.set_keepalive(30)  # que el router no corte una sesión callada
        self.cliente = cliente

    @property
    def abierta(self) -> bool:  # propio
        return bool(self.cliente and self.cliente.get_transport()
                    and self.cliente.get_transport().is_active())

    def close(self):  # propio
        if self.cliente is not None:
            self.cliente.close()
            self.cliente = None

    def run(self, comando: str, timeout: float = 30, max_bytes: int = 512_000) -> Salida:  # propio
        """Corre un comando y espera a que termine. `sudo …` usa la contraseña guardada."""
        if not self.abierta:
            self.open()
        con_sudo = comando.lstrip().startswith("sudo ")
        if con_sudo:
            comando = comando.lstrip().replace("sudo ", "sudo -S -p '' ", 1)
        inicio = time.perf_counter()
        entrada, salida, error = self.cliente.exec_command(comando, timeout=timeout)
        if con_sudo:
            entrada.write((self.equipo.ssh_clave or "") + "\n")
            entrada.flush()
        texto = salida.read(max_bytes).decode("utf-8", errors="replace")
        errores = error.read(64_000).decode("utf-8", errors="replace")
        codigo = salida.channel.recv_exit_status()
        if con_sudo and "incorrect password" in errores.lower():
            errores = "sudo rechazó la contraseña guardada (¿es distinta la de sudo?)\n" + errores
        return Salida(codigo, texto, errores, round((time.perf_counter() - inicio) * 1000))

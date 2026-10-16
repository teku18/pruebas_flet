"""
Consola SSH: escribir cualquier comando, como en una terminal de otra PC.

Cada comando corre en un bash de login nuevo (`bash -l -s`), pero la consola
recuerda la carpeta: si haces `cd /opt/odoo`, el siguiente comando ya empieza
ahí. Por eso se ve como una sesión continua.

  - La salida llega en vivo (pedazo a pedazo) y stdout+stderr van juntos, en
    el orden en que salen (como en una terminal).
  - `sudo …` (en cualquier parte: `cd x && sudo systemctl …`) usa la
    contraseña guardada: una función `sudo` la valida con `sudo -S -v` y luego
    corre `sudo -n …`, así el comando nunca recibe la contraseña.
  - El script viaja por la entrada estándar, no en la línea de comandos: la
    contraseña no aparece en `ps` del servidor.
  - Ctrl+C = cancel(): cierra el canal y el servidor corta el proceso.
  - Programas de pantalla completa (vim, nano, htop, top, less…) no se
    pueden: no hay terminal (TTY). Se avisa con una alternativa.
  - Tab = complete(): `compgen` en el servidor (comandos o archivos).

Qué es / para qué / dónde: docs/notas_tecnicas.md (nota 51).
"""
import shlex
import threading
import time
from dataclasses import dataclass

from modulos.kraken.ssh.conexion import Sesion

MARCA = "__CK_FIN_7f3a__"
MAX_SALIDA = 512_000         # lo que se muestra de un comando (lo demás se descarta)
PANTALLA_COMPLETA = {
    "vim": "usa cat, head, tail o sed -n '1,80p' archivo",
    "vi": "usa cat, head, tail o sed -n '1,80p' archivo",
    "nvim": "usa cat, head, tail o sed -n '1,80p' archivo",
    "nano": "para cambiar una línea: sed -i 's/viejo/nuevo/' archivo",
    "htop": "usa top -bn1 | head -25 (o el panel de recursos)",
    "top": "usa top -bn1 | head -25 (o el panel de recursos)",
    "less": "usa cat, head o tail",
    "more": "usa cat, head o tail",
    "man": "usa  comando --help",
    "mc": "usa ls, cp, mv",
    "tmux": "no hay terminal real en la consola",
    "screen": "no hay terminal real en la consola",
    "watch": "repite el comando a mano (o usa el panel, que se actualiza solo)",
}
FRECUENTES = ["ls -la", "df -h", "free -h", "uptime", "top -bn1 | head -25",
              "sudo systemctl status odoo --no-pager", "sudo journalctl -n 50 --no-pager",
              "docker ps", "tail -n 50 /var/log/syslog"]


@dataclass
class Resultado:
    comando: str
    codigo: int | None        # None = cancelado o no se pudo correr
    salida: str
    cwd: str
    tiempo_ms: int
    cancelado: bool = False
    error: str | None = None


def full_screen_hint(comando: str) -> str | None:  # propio
    """Si el comando es vim/htop/… devuelve qué usar en su lugar."""
    try:
        partes = shlex.split(comando)
    except ValueError:
        partes = comando.split()
    while partes and (partes[0] == "sudo" or partes[0].startswith("-") or "=" in partes[0]):
        partes = partes[1:]
    if not partes:
        return None
    nombre = partes[0].rsplit("/", 1)[-1]
    if nombre in PANTALLA_COMPLETA:
        return f"«{nombre}» necesita pantalla completa: {PANTALLA_COMPLETA[nombre]}"
    return None


def script(comando: str, cwd: str | None, clave: str | None) -> str:  # propio
    """El bash que se manda por stdin. Todo va en un bloque { } < /dev/null: bash lo
    lee completo antes de correrlo y el comando no se "come" el resto del script."""
    lineas = []
    if clave is not None and "sudo" in comando:
        lineas.append(f"__ck_p={shlex.quote(clave)}")
        # 1) -v valida la contraseña (o refresca la que sudo ya recordaba)
        # 2) -n corre el comando sin volver a pedirla: así la contraseña NUNCA le
        #    llega al comando (p. ej. `sudo tee archivo` no la escribe en el archivo)
        lineas.append("sudo() { case \"$1\" in -k|-K|-v|-l) command sudo \"$@\"; return;; esac; "
                      "printf '%s\\n' \"$__ck_p\" | command sudo -S -p '' -v "
                      "|| { echo 'sudo rechazó la contraseña guardada' >&2; return 1; }; "
                      "command sudo -n \"$@\"; }")
    lineas.append("{")
    if cwd:
        lineas.append(f"cd {shlex.quote(cwd)} 2>/dev/null || cd")
    lineas.append(comando)
    lineas.append("__ck_c=$?")
    lineas.append(f"printf '\\n{MARCA} %s %s\\n' \"$__ck_c\" \"$(pwd)\"")
    lineas.append("} < /dev/null 2>&1")
    return "\n".join(lineas) + "\n"


def split_marker(texto: str) -> tuple[str, int | None, str | None]:  # propio
    """Separa la salida del renglón final '__CK_FIN__ <código> <carpeta>'."""
    i = texto.rfind(MARCA + " ")
    if i < 0:
        return texto, None, None
    salida = texto[:i]
    if salida.endswith("\n"):
        salida = salida[:-1]    # el \n que agrega el printf antes de la marca
    resto = texto[i + len(MARCA) + 1:].rstrip("\n")
    codigo, _, cwd = resto.partition(" ")
    try:
        return salida, int(codigo), cwd or None
    except ValueError:
        return salida, None, cwd or None


class Consola:
    """Una consola sobre una Sesion ya abierta (la del panel)."""

    def __init__(self, sesion: Sesion):
        self.sesion = sesion
        self.cwd: str | None = None      # None = la carpeta de inicio del usuario
        self._canal = None
        self._cancelar = threading.Event()

    @property
    def corriendo(self) -> bool:  # propio
        return self._canal is not None

    def prompt(self) -> str:  # propio
        e = self.sesion.equipo
        carpeta = self.cwd or "~"
        return f"{e.ssh_usuario}@{e.nombre}:{carpeta}$"

    def start(self) -> None:  # propio
        """Averigua la carpeta de inicio (para el prompt)."""
        r = self.run("pwd")
        if r.codigo == 0 and r.salida.strip():
            self.cwd = r.salida.strip().splitlines()[-1]

    def cancel(self) -> None:  # propio
        self._cancelar.set()
        canal = self._canal
        if canal is not None:
            try:
                canal.close()
            except Exception:  # noqa: BLE001
                pass

    def run(self, comando: str, on_chunk=None, timeout: float = 600) -> Resultado:  # propio
        """Corre `comando` (bloquea: llámalo en un hilo). on_chunk(texto) recibe la salida
        en vivo, renglón por renglón."""
        inicio = time.perf_counter()
        self._cancelar.clear()
        if not self.sesion.abierta:
            self.sesion.open()
        transporte = self.sesion.cliente.get_transport()
        canal = transporte.open_session(timeout=15)
        self._canal = canal
        bufer, enviado, total = "", 0, 0
        try:
            canal.set_combine_stderr(True)
            canal.exec_command("bash -l -s")
            canal.sendall(script(comando, self.cwd, self.sesion.equipo.ssh_clave).encode())
            canal.shutdown_write()
            canal.settimeout(0.3)
            while True:
                if self._cancelar.is_set():
                    break
                if time.perf_counter() - inicio > timeout:
                    self.cancel()
                    break
                try:
                    pedazo = canal.recv(32_768)
                except TimeoutError:
                    continue
                except OSError:
                    break           # cerrado por cancel()
                if not pedazo:
                    break
                if total < MAX_SALIDA:
                    bufer += pedazo.decode("utf-8", errors="replace")
                total += len(pedazo)
                # se manda hasta el último renglón completo que NO sea la marca
                corte = bufer.rfind("\n")
                if on_chunk and corte >= enviado:
                    listo = bufer[enviado:corte + 1]
                    if MARCA in listo:
                        listo = listo[:listo.find(MARCA)]
                        corte = enviado + len(listo) - 1
                    if listo:
                        on_chunk(listo)
                        enviado = corte + 1
        finally:
            self._canal = None
            try:
                canal.close()
            except Exception:  # noqa: BLE001
                pass
        salida, codigo, cwd = split_marker(bufer)
        if on_chunk and len(salida) > enviado:
            on_chunk(salida[enviado:])
        cancelado = self._cancelar.is_set()
        if cwd:
            self.cwd = cwd
        if total > MAX_SALIDA:
            salida += f"\n… (cortado: {total:,} bytes, se muestran {MAX_SALIDA:,})"
        return Resultado(comando, None if cancelado else codigo, salida, self.cwd or "~",
                         round((time.perf_counter() - inicio) * 1000), cancelado)

    def complete(self, linea: str) -> list[str]:  # propio
        """Tab: opciones para la última palabra (comandos si es la primera, si no archivos)."""
        palabras = linea.split(" ")
        ultima = palabras[-1]
        es_comando = len([p for p in palabras[:-1] if p]) == 0 and "/" not in ultima
        tipo = "-c" if es_comando else "-f"
        r = self.run(f"compgen {tipo} -- {shlex.quote(ultima)} 2>/dev/null | sort -u | head -60")
        opciones = [o for o in r.salida.splitlines() if o]
        if not es_comando:   # a las carpetas se les pone / (como hace bash)
            marcadas = self.run("for f in " + " ".join(shlex.quote(o) for o in opciones[:60])
                                + '; do [ -d "$f" ] && echo "$f/" || echo "$f"; done'
                                ) if opciones else None
            if marcadas and marcadas.codigo == 0:
                opciones = [o for o in marcadas.salida.splitlines() if o]
        return opciones


def common_prefix(opciones: list[str]) -> str:  # propio
    if not opciones:
        return ""
    a, b = min(opciones), max(opciones)
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return a[:i]

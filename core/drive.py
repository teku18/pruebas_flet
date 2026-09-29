"""
¿A qué cuenta de Google Drive se suben los respaldos? (vía rclone)

La app no se conecta a Google por su cuenta: le pregunta a rclone, que ya tiene
la sesión que autorizaste en `rclone config` (remoto "gdrive").

  1. rclone about gdrive:        -> prueba la conexión (y renueva el token si venció)
  2. rclone config dump          -> lee el token de acceso de ese remoto
  3. Drive API /about?fields=user -> correo y nombre de la cuenta
  4. rclone lsf gdrive:ControlKraken -> qué respaldos ya están en Drive

Sincronizar (sin depender de cron): la propia app corre
  upload()          -> rclone copy ~/Respaldos/ControlKraken gdrive:ControlKraken
  download_recent() -> rclone copy gdrive:ControlKraken ~/Respaldos/ControlKraken (últimas 24 h)
después de cada respaldo, al abrir y con [Sincronizar]. `copy` nunca borra en Drive.

Nada de esto guarda contraseñas en la app: el token vive en la configuración
de rclone (~/.config/rclone/rclone.conf), igual que antes.
"""
import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field

REMOTO = "gdrive"          # nombre que le diste en `rclone config`
CARPETA = "ControlKraken"  # carpeta dentro de tu Drive
ABOUT_URL = "https://www.googleapis.com/drive/v3/about?fields=user(displayName,emailAddress)"


@dataclass
class DriveStatus:
    cuenta: str | None = None          # correo de la cuenta de Google
    nombre: str | None = None          # nombre para mostrar
    en_drive: set[str] = field(default_factory=set)  # zips que ya están en Drive
    error: str | None = None


def _rclone(*args: str, timeout: int = 30) -> str:  # propio
    """Corre rclone y regresa su salida; si falla, ValueError con el motivo."""
    try:
        r = subprocess.run(["rclone", *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as ex:
        raise ValueError("rclone tardó demasiado (¿sin internet?)") from ex
    if r.returncode != 0:
        ultima = (r.stderr.strip().splitlines() or ["error desconocido"])[-1]
        raise ValueError(ultima[-160:])
    return r.stdout


PATRON = "ControlKraken_*.zip"


def ready(remoto: str = REMOTO) -> str | None:  # propio
    """None si rclone está instalado y el remoto existe; si no, el motivo."""
    if shutil.which("rclone") is None:
        return "rclone no está instalado (ver docs/respaldo.md)"
    try:
        config = json.loads(_rclone("config", "dump")).get(remoto)
    except (ValueError, json.JSONDecodeError) as ex:
        return f"No se pudo leer la configuración de rclone: {ex}"
    if not config:
        return f"No existe el remoto «{remoto}»: corre rclone config"
    if config.get("type") != "drive":
        return f"«{remoto}» no es de Google Drive"
    return None


def upload(carpeta_local: str, remoto: str = REMOTO, carpeta: str = CARPETA) -> str | None:  # propio
    """Sube a Drive los respaldos que falten. Regresa None si todo bien, o el error."""
    motivo = ready(remoto)
    if motivo:
        return motivo
    try:
        _rclone("copy", str(carpeta_local), f"{remoto}:{carpeta}", "--include", PATRON,
                timeout=180)
    except ValueError as ex:
        return f"No se pudo subir: {ex}"
    return None


def download_recent(carpeta_local: str, remoto: str = REMOTO,  # propio
                    carpeta: str = CARPETA) -> str | None:
    """Baja los respaldos de las últimas 24 h (los de otros equipos)."""
    motivo = ready(remoto)
    if motivo:
        return motivo
    try:
        _rclone("copy", f"{remoto}:{carpeta}", str(carpeta_local), "--include", PATRON,
                "--max-age", "24h", timeout=180)
    except ValueError as ex:
        return f"No se pudo bajar: {ex}"
    return None


def drive_status(remoto: str = REMOTO, carpeta: str = CARPETA) -> DriveStatus:  # propio
    """Cuenta de Google conectada y respaldos que ya subieron. Nunca lanza error:
    lo regresa en .error para mostrarlo en pantalla."""
    motivo = ready(remoto)
    if motivo:
        return DriveStatus(error=motivo)
    try:
        _rclone("about", f"{remoto}:")  # conecta y, si el token venció, lo renueva
        config = json.loads(_rclone("config", "dump")).get(remoto)  # token ya renovado
        token = json.loads(config["token"])["access_token"]

        peticion = urllib.request.Request(ABOUT_URL, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(peticion, timeout=15) as resp:
            usuario = json.load(resp).get("user", {})

        try:
            nombres = _rclone("lsf", f"{remoto}:{carpeta}", "--include", PATRON)
            en_drive = {n.strip() for n in nombres.splitlines() if n.strip()}
        except ValueError:
            en_drive = set()  # la carpeta aún no existe en Drive: nada subido
        return DriveStatus(usuario.get("emailAddress"), usuario.get("displayName"), en_drive)
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as ex:
        return DriveStatus(error=f"No se pudo consultar Drive: {ex}")

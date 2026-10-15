"""
PRUEBA (no es parte de ControlKraken): ¿funciona SSH (paramiko) dentro del APK?

Es una app aparte (otro id: com.teku18.cksshprueba), se instala junto a
ControlKraken sin tocarlo.

Qué revisa:
  1. Al abrir: ¿cargan las librerías con partes en C (cryptography, bcrypt,
     PyNaCl)? Si alguna falla, aquí sale el error y ya sabemos la respuesta.
  2. Conectar: entra a tu servidor con usuario y contraseña y corre comandos
     de solo lectura (uname, uptime, memoria, disco, servicios). NO cambia nada.

La contraseña NO se guarda: solo vive mientras la app está abierta.
"""
import asyncio
import time
import traceback

import flet as ft

COMANDOS = (
    "uname -a; echo; uptime; echo; free -m; echo; df -h /; echo; "
    "for s in odoo postgresql nginx; do echo \"$s: $(systemctl is-active $s 2>/dev/null "
    "|| true)\"; done"
)


def versions() -> list[str]:
    """Carga cada librería y dice su versión (o el error)."""
    lineas = []
    for nombre, modulo in (("paramiko", "paramiko"), ("cryptography", "cryptography"),
                           ("bcrypt", "bcrypt"), ("PyNaCl", "nacl"), ("cffi", "cffi")):
        try:
            m = __import__(modulo)
            lineas.append(f"✓ {nombre} {getattr(m, '__version__', '?')}")
        except Exception as ex:  # noqa: BLE001
            lineas.append(f"✗ {nombre}: {type(ex).__name__}: {ex}")
    try:  # una operación criptográfica real (usa la parte en C)
        from cryptography.hazmat.primitives.asymmetric import ed25519
        ed25519.Ed25519PrivateKey.generate()
        lineas.append("✓ criptografía funcionando (llave ed25519 generada)")
    except Exception as ex:  # noqa: BLE001
        lineas.append(f"✗ criptografía: {type(ex).__name__}: {ex}")
    return lineas


def connect(host: str, puerto: int, usuario: str, clave: str) -> list[str]:
    import paramiko

    lineas = []
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # solo para la prueba
    inicio = time.perf_counter()
    try:
        cliente.connect(host, port=puerto, username=usuario, password=clave, timeout=10,
                        banner_timeout=10, auth_timeout=10, look_for_keys=False,
                        allow_agent=False)
        lineas.append(f"✓ Conectado en {round((time.perf_counter() - inicio) * 1000)} ms")
        llave = cliente.get_transport().get_remote_server_key()
        lineas.append(f"Huella del servidor ({llave.get_name()}): "
                      f"{llave.fingerprint if hasattr(llave, 'fingerprint') else llave.get_fingerprint().hex()}")
        inicio = time.perf_counter()
        _, salida, error = cliente.exec_command(COMANDOS, timeout=15)
        texto = salida.read().decode(errors="replace")
        errores = error.read().decode(errors="replace")
        lineas.append(f"✓ Comandos en {round((time.perf_counter() - inicio) * 1000)} ms:")
        lineas.append(texto.strip())
        if errores.strip():
            lineas.append("stderr: " + errores.strip())
    finally:
        cliente.close()
    return lineas


def main(page: ft.Page):
    page.title = "CK · Prueba SSH"
    page.scroll = ft.ScrollMode.AUTO

    salida = ft.Column(spacing=4)
    txt_host = ft.TextField(label="Servidor (IP o dominio)", autocorrect=False,
                            capitalization=ft.TextCapitalization.NONE)
    txt_puerto = ft.TextField(label="Puerto", value="22", width=110,
                              keyboard_type=ft.KeyboardType.NUMBER)
    txt_usuario = ft.TextField(label="Usuario", autocorrect=False, expand=True,
                               capitalization=ft.TextCapitalization.NONE)
    txt_clave = ft.TextField(label="Contraseña", password=True, can_reveal_password=True)

    def write(lineas: list[str]):
        for linea in lineas:
            color = ft.Colors.RED if linea.startswith("✗") else None
            salida.controls.append(ft.Text(linea, selectable=True, size=13,
                                           font_family="monospace", color=color))
        page.update()

    async def run(e):
        btn.disabled = True
        salida.controls.append(ft.Text("Conectando…", italic=True))
        page.update()
        try:
            lineas = await asyncio.to_thread(connect, (txt_host.value or "").strip(),
                                             int(txt_puerto.value or 22),
                                             (txt_usuario.value or "").strip(),
                                             txt_clave.value or "")
        except Exception as ex:  # noqa: BLE001
            lineas = [f"✗ {type(ex).__name__}: {ex}", traceback.format_exc(limit=3)]
        btn.disabled = False
        write(lineas)

    btn = ft.FilledButton("Conectar y leer el servidor", icon=ft.Icons.TERMINAL, on_click=run)
    page.add(ft.SafeArea(content=ft.Column(spacing=10, controls=[
        ft.Text("Prueba de SSH", size=22, weight=ft.FontWeight.BOLD),
        ft.Text("Solo lee: no cambia nada en el servidor. La contraseña no se guarda.",
                size=12, color=ft.Colors.OUTLINE),
        txt_host, ft.Row([txt_usuario, txt_puerto]), txt_clave, btn,
        ft.Divider(), salida,
    ])))
    write(["Librerías:", *versions()])


ft.run(main)

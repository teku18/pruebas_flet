"""
Cómo se ve el resultado de cada prueba.

Cada función recibe el DETALLE como dict (lo mismo que se guarda en el
historial): así una prueba vieja se pinta igual que una recién hecha, y
mientras corre (ping, puertos) se repinta con el resultado parcial.

Los métodos marcados con  # propio  son nuestros; lo demás viene de Flet.
"""
from datetime import date, datetime

import flet as ft

from modulos.kraken.comun import MONO, copy_text
from modulos.kraken.red.ping import METODOS


# ============================================================================
# Piezas
# ============================================================================
def banner(texto: str, color, icono) -> ft.Control:  # propio
    return ft.Container(
        padding=12, border_radius=10, bgcolor=ft.Colors.with_opacity(0.12, color),
        content=ft.Row(spacing=10, controls=[
            ft.Icon(icono, color=color),
            ft.Text(texto, color=color, weight=ft.FontWeight.BOLD, expand=True)]))


def _host_ip(d: dict) -> str:  # propio
    """'servidor.com (10.0.0.5)', o solo la IP si escribiste una IP."""
    host, ip = d.get("host") or "", d.get("ip") or ""
    return f"{host} ({ip})" if ip and host != ip else (ip or host)


def error_box(texto: str) -> ft.Control:  # propio
    return banner(texto, ft.Colors.RED, ft.Icons.ERROR_OUTLINE)


def row(page: ft.Page, etiqueta: str, valor, copiable: bool = True,  # propio
        color=None) -> ft.Control:
    """etiqueta ........ valor   (tocar el valor lo copia)."""
    texto = "—" if valor in (None, "", []) else str(valor)
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=6), ink=copiable and texto != "—",
        on_click=(lambda e: page.run_task(copy_text, page, texto, f"{etiqueta} copiado"))
        if copiable and texto != "—" else None,
        content=ft.Row(vertical_alignment=ft.CrossAxisAlignment.START, controls=[
            ft.Text(etiqueta, size=13, color=ft.Colors.OUTLINE, width=110),
            ft.Text(texto, size=14, expand=True, selectable=not copiable, color=color,
                    font_family=MONO if copiable else None),
        ]))


def card(*controles: ft.Control) -> ft.Control:  # propio
    return ft.Card(content=ft.Container(padding=12, content=ft.Column(spacing=0,
                                                                      controls=list(controles))))


def nice_date(iso: str | None) -> str | None:  # propio
    """'2026-03-15' / '2026-03-15T04:00:00+00:00' -> '15/03/2026'."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso


def days_text(dias: int | None) -> tuple[str | None, object]:  # propio
    """(texto, color) para "cuánto falta para que venza"."""
    if dias is None:
        return None, None
    if dias < 0:
        return f"Venció hace {-dias} días", ft.Colors.RED
    if dias <= 30:
        return f"Vence en {dias} días", ft.Colors.ORANGE
    return f"{dias} días", ft.Colors.GREEN


# ============================================================================
# Una función por prueba
# ============================================================================
def render(page: ft.Page, clave: str, d: dict, corriendo: bool = False,  # propio
           on_save=None) -> list[ft.Control]:
    """on_save(ip, puertos, nombre): "Guardar" de un dispositivo encontrado."""
    if clave == "dispositivos":
        return _devices(page, d, corriendo, on_save)
    funcion = {"ping": _ping, "puertos": _ports, "dns": _dns, "mi_ip": _my_ip,
               "cert": _cert, "whois": _whois, "wol": _wol}[clave]
    return funcion(page, d, corriendo)


def _ping(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    tiempos = d.get("tiempos", [])
    recibidos = [t for t in tiempos if t is not None]
    controles: list[ft.Control] = []
    if not corriendo:
        if recibidos:
            prom = round(sum(recibidos) / len(recibidos), 1)
            controles.append(banner(f"Responde · {len(recibidos)}/{len(tiempos)} · {prom} ms",
                                    ft.Colors.GREEN, ft.Icons.CHECK_CIRCLE))
        else:
            controles.append(banner(f"No responde (0/{len(tiempos)})", ft.Colors.RED,
                                    ft.Icons.CANCEL))
    metodo = METODOS.get(d.get("metodo"), d.get("metodo") or "")
    nota = f"{_host_ip(d)} · {metodo}"
    if d.get("metodo") == "tcp":
        nota += (f" al puerto {d.get('puerto_tcp')} (este equipo no permitió ICMP: se mide "
                 "cuánto tarda en conectar)")
    controles.append(ft.Text(nota, size=12, color=ft.Colors.OUTLINE))
    mayor = max(recibidos or [1])
    for k, t in enumerate(tiempos, start=1):
        controles.append(ft.Row(spacing=8, controls=[
            ft.Text(f"#{k}", width=32, size=12, color=ft.Colors.OUTLINE),
            ft.Container(height=10, border_radius=5, width=max(6, 180 * (t / mayor)) if t else 6,
                         bgcolor=ft.Colors.GREEN if t is not None else ft.Colors.RED),
            ft.Text(f"{t} ms" if t is not None else "perdido", size=12, font_family=MONO,
                    color=None if t is not None else ft.Colors.RED),
        ]))
    if recibidos and not corriendo:
        controles.append(ft.Text(f"mín {min(recibidos)} · prom "
                                 f"{round(sum(recibidos) / len(recibidos), 1)} · máx "
                                 f"{max(recibidos)} ms", size=12))
    return controles


def _ports(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    puertos = d.get("puertos", [])
    abiertos = [p for p in puertos if p["estado"] == "abierto"]
    otros = [p for p in puertos if p["estado"] != "abierto"]
    controles: list[ft.Control] = []
    total, hechos = d.get("total", 0), d.get("revisados", 0)
    if corriendo and total:
        controles.append(ft.ProgressBar(value=hechos / total))
        controles.append(ft.Text(f"{hechos:,} de {total:,} revisados…", size=12))
    elif d.get("cancelado"):
        controles.append(banner(f"Cancelado: {len(abiertos)} abiertos en {hechos:,} revisados",
                                ft.Colors.ORANGE, ft.Icons.STOP_CIRCLE))
    else:
        color = ft.Colors.GREEN if abiertos else ft.Colors.OUTLINE
        controles.append(banner(f"{len(abiertos)} abierto{'s' if len(abiertos) != 1 else ''} "
                                f"de {hechos:,} · {_host_ip(d)}", color,
                                ft.Icons.LOCK_OPEN if abiertos else ft.Icons.LOCK))
    for p in sorted(abiertos, key=lambda x: x["puerto"]):
        controles.append(ft.Container(
            padding=ft.Padding.symmetric(vertical=6, horizontal=4),
            content=ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.CIRCLE, size=10, color=ft.Colors.GREEN),
                ft.Text(str(p["puerto"]), width=60, font_family=MONO, weight=ft.FontWeight.BOLD),
                ft.Text(p.get("servicio") or "", expand=True),
                ft.Text(f"{p['ms']} ms" if p.get("ms") is not None else "", size=12,
                        color=ft.Colors.OUTLINE)])))
    if otros and not corriendo:
        cuenta = {}
        for p in otros:
            cuenta[p["estado"]] = cuenta.get(p["estado"], 0) + 1
        resumen = " · ".join(f"{n} {estado}{'s' if n != 1 else ''}" for estado, n in cuenta.items())
        detalle = [ft.Text(f"{p['puerto']}  {p['estado']}" + (f"  ({p['servicio']})"
                                                               if p.get("servicio") else ""),
                           size=12, font_family=MONO) for p in otros[:300]]
        if len(otros) > 300:
            detalle.append(ft.Text(f"… y {len(otros) - 300} más", size=12))
        controles.append(ft.ExpansionTile(
            title=ft.Text(f"Los demás: {resumen}", size=13), dense=True,
            controls=[ft.Container(padding=ft.Padding.only(left=16, bottom=8),
                                   content=ft.Column(spacing=2, controls=detalle))]))
        controles.append(ft.Text("cerrado = el equipo contestó que no hay nada · filtrado = "
                                 "nadie contestó (firewall o equipo apagado)", size=11,
                                 color=ft.Colors.OUTLINE))
    return controles


DNS_AYUDA = {"A": "IP (IPv4)", "AAAA": "IP (IPv6)", "CNAME": "Es otro nombre de",
             "MX": "Correo (prioridad y servidor)", "TXT": "Textos (SPF, verificaciones…)",
             "NS": "Servidores que lo administran", "PTR": "Nombre de esta IP"}


def _dns(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"]),
                ft.Text(f"Servidor DNS: {d.get('servidor')}", size=12, color=ft.Colors.OUTLINE)]
    controles: list[ft.Control] = [ft.Text(
        f"{d.get('nombre')} · preguntado a {d.get('servidor')} · {d.get('tiempo_ms')} ms",
        size=12, color=ft.Colors.OUTLINE)]
    for tipo, registros in d.get("registros", {}).items():
        filas: list[ft.Control] = [ft.Row(controls=[
            ft.Text(tipo, weight=ft.FontWeight.BOLD, font_family=MONO, width=60),
            ft.Text(DNS_AYUDA.get(tipo, ""), size=12, color=ft.Colors.OUTLINE)])]
        if registros:
            for reg in registros:
                filas.append(ft.Container(
                    ink=True, padding=ft.Padding.symmetric(vertical=4),
                    on_click=lambda e, v=reg["valor"]: page.run_task(copy_text, page, v),
                    content=ft.Row(controls=[
                        ft.Text(reg["valor"], font_family=MONO, size=13, expand=True),
                        ft.Text(f"TTL {reg['ttl']}" if reg.get("ttl") is not None else "",
                                size=11, color=ft.Colors.OUTLINE)])))
        else:
            filas.append(ft.Text("(no tiene)", size=12, italic=True, color=ft.Colors.OUTLINE))
        controles.append(card(*filas))
    for aviso in d.get("avisos", []):
        controles.append(ft.Text(aviso, size=12, color=ft.Colors.ORANGE))
    return controles


def _my_ip(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    publica = card(
        ft.Text("Internet te ve como", weight=ft.FontWeight.BOLD),
        row(page, "IP pública", d.get("publica")),
        row(page, "Proveedor", d.get("proveedor"), copiable=False),
        row(page, "Ubicación", d.get("ciudad"), copiable=False),
        *([ft.Text(d["error_publica"], size=12, color=ft.Colors.ORANGE)]
          if d.get("error_publica") else []))
    local = card(
        ft.Text("En tu red", weight=ft.FontWeight.BOLD),
        row(page, "IP local", d.get("local") or "Sin red local"),
        row(page, "Red", d.get("red")),
        row(page, "Este equipo", d.get("equipo"), copiable=False))
    return [publica, local,
            ft.Text("La ubicación es aproximada (la de tu proveedor, no la tuya).", size=11,
                    color=ft.Colors.OUTLINE)]


def _cert(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    if d.get("valido"):
        estado = banner("Válido: el navegador lo acepta", ft.Colors.GREEN, ft.Icons.VERIFIED)
    else:
        estado = banner(f"No válido: {d.get('motivo')}", ft.Colors.RED, ft.Icons.GPP_BAD)
    dias, color = days_text(d.get("dias_restantes"))
    return [estado, card(
        row(page, "Para", d.get("para")),
        row(page, "Cubre", ", ".join(d.get("nombres") or []) or None),
        row(page, "Lo firmó", d.get("emisor"), copiable=False),
        row(page, "Desde", nice_date(d.get("desde")), copiable=False),
        row(page, "Hasta", nice_date(d.get("hasta")), copiable=False),
        row(page, "Le quedan", dias, copiable=False, color=color),
        row(page, "Protocolo", d.get("tls"), copiable=False),
        row(page, "Servidor", f"{d.get('host')}:{d.get('puerto')}"),
    )]


def _whois(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    dias, color = days_text(d.get("dias_restantes"))
    controles: list[ft.Control] = []
    if d.get("dias_restantes") is not None and d["dias_restantes"] <= 30:
        controles.append(banner(dias, color, ft.Icons.WARNING_AMBER))
    controles.append(card(
        row(page, "Dominio", d.get("dominio")),
        row(page, "Registrador", d.get("registrador"), copiable=False),
        row(page, "Registrado", nice_date(d.get("creado")), copiable=False),
        row(page, "Vence", nice_date(d.get("vence")), copiable=False, color=color),
        row(page, "Le quedan", dias, copiable=False, color=color),
        row(page, "Actualizado", nice_date(d.get("actualizado")), copiable=False),
        row(page, "Servidores DNS", "\n".join(d.get("servidores") or []) or None),
        row(page, "Estado", ", ".join(d.get("estado") or []) or None, copiable=False),
        row(page, "Fuente", d.get("fuente"), copiable=False),
    ))
    if d.get("texto") and d.get("fuente") == "WHOIS":
        controles.append(ft.ExpansionTile(
            title=ft.Text("Respuesta completa", size=13), dense=True,
            controls=[ft.Container(padding=8, content=ft.Text(d["texto"], size=11,
                                                              font_family=MONO,
                                                              selectable=True))]))
    if d.get("vence") and date.fromisoformat(d["vence"]).year >= 9000:
        controles.append(ft.Text("Fecha de vencimiento rara: revisa la respuesta completa.",
                                 size=12, color=ft.Colors.ORANGE))
    return controles


def _wol(page, d: dict, corriendo: bool) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    return [
        banner(f"Paquete mágico enviado a {d.get('mac')}", ft.Colors.GREEN, ft.Icons.BOLT),
        ft.Text("Si en un minuto no prende, revisa en ese equipo:", weight=ft.FontWeight.BOLD),
        ft.Text("• BIOS/UEFI: activar «Wake on LAN» (o «Power on by PCI-E»).\n"
                "• Linux: sudo ethtool -s <interfaz> wol g\n"
                "• Windows: Administrador de dispositivos, tu tarjeta de red, Administración "
                "de energía: «Permitir que este dispositivo reactive el equipo».\n"
                "• Casi siempre funciona solo por CABLE y con el celular en la misma red "
                "(tu Wi-Fi de casa, no datos móviles).", size=13),
    ]


def _suggested_name(x: dict) -> str | None:  # propio
    """'mi-laptop.lan' -> 'mi-laptop' · 'Probablemente tu router' -> 'Router'."""
    if x.get("nombre"):
        return x["nombre"].split(".")[0]
    parece = x.get("parece") or ""
    return "Router" if "router" in parece.lower() else (parece or None)


def _devices(page, d: dict, corriendo: bool, on_save) -> list[ft.Control]:  # propio
    if d.get("error"):
        return [error_box(d["error"])]
    lista = d.get("dispositivos", [])
    controles: list[ft.Control] = []
    total, hechos = d.get("total", 0), d.get("revisados", 0)
    if corriendo and total:
        controles += [ft.ProgressBar(value=hechos / total),
                      ft.Text(f"{hechos} de {total} direcciones · {len(lista)} encontrados…",
                              size=12)]
    else:
        texto = f"{len(lista)} dispositivo{'s' if len(lista) != 1 else ''} en {d.get('red')}"
        if d.get("cancelado"):
            texto += " (cancelado)"
        controles.append(banner(texto, ft.Colors.TEAL, ft.Icons.DEVICES_OTHER))
        controles.append(ft.Text(f"Buscado con {d.get('metodo')} en "
                                 f"{round((d.get('tiempo_ms') or 0) / 1000, 1)} s", size=12,
                                 color=ft.Colors.OUTLINE))
    if d.get("aviso"):
        controles.append(banner(d["aviso"], ft.Colors.ORANGE, ft.Icons.WARNING_AMBER))
    for x in lista:
        puertos = ", ".join(f"{p}" + (f" {s}" if s else "")
                            for p, s in zip(x.get("puertos", []), x.get("servicios", [])))
        lineas = [ft.Row(spacing=8, controls=[
            ft.Text(x["ip"], font_family=MONO, weight=ft.FontWeight.BOLD),
            ft.Text(x.get("nombre") or "", size=12, color=ft.Colors.OUTLINE, expand=True,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)])]
        if x.get("parece"):
            lineas.append(ft.Text(x["parece"], size=12,
                                  color=ft.Colors.TEAL if x.get("este") else None))
        if puertos:
            lineas.append(ft.Text(f"Abiertos: {puertos}", size=11, color=ft.Colors.OUTLINE))
        if x.get("mac"):
            lineas.append(ft.Text(f"MAC {x['mac']}", size=11, font_family=MONO,
                                  color=ft.Colors.OUTLINE))
        controles.append(ft.Card(content=ft.Container(
            padding=ft.Padding.only(left=12, top=8, bottom=8, right=4),
            content=ft.Row(controls=[
                ft.Icon(ft.Icons.SMARTPHONE if x.get("este") else ft.Icons.DEVICES,
                        color=ft.Colors.TEAL),
                ft.Column(spacing=2, expand=True, controls=lineas),
                ft.IconButton(ft.Icons.BOOKMARK_ADD, tooltip="Guardar en Mis equipos",
                              visible=bool(on_save) and not x.get("este") and not corriendo,
                              on_click=lambda e, v=x: on_save(v["ip"], v.get("puertos", []),
                                                              _suggested_name(v))),
            ]))))
    return controles

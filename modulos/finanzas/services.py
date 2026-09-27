"""
Cálculos de Finanzas (como los campos compute de Odoo, pero para reportes).

Reglas:
  - Cada periodo es un "libro" independiente. "Abre con" = SUS saldos iniciales
    (un periodo creado en la app abre en $0; uno abierto con un cierre, con los
    saldos del periodo anterior).
  - Saldo inicial: cuenta para el saldo, NO como ingreso del periodo.
  - Ingresos = depósitos + rendimientos. Gastos = retiros.
  - Traspasos: dentro de lo que estás viendo se cancelan (sale de uno, entra
    a otro). Pero si filtras por un concepto y el traspaso viene de otro
    concepto (Vacaciones -> Mio), para "Mio" sí es una entrada de dinero.
    Regla: la mitad de un traspaso cuenta como ingreso/gasto solo si su
    pareja queda FUERA de lo que estás viendo.
  - Acumulado global = suma de los periodos ABIERTOS (uno cerrado ya pasó
    sus saldos al siguiente; contarlo sería contar doble).
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import case, func, select

from core.database import SessionLocal
from modulos.finanzas.models import (
    SIGNO_TIPO,
    TIPOS_GASTO,
    TIPOS_INGRESO,
    Movimiento,
    Periodo,
    Plataforma,
)

# +monto o -monto según el tipo, calculado en SQL
MONTO_CON_SIGNO = case(
    *[(Movimiento.tipo == t, Movimiento.monto * s) for t, s in SIGNO_TIPO.items()],
    else_=Movimiento.monto,
)


def money(valor: float, signo: bool = False) -> str:  # propio
    """1234.5 -> '$1,234.50'  (con signo=True: '+$1,234.50' / '-$1,234.50')"""
    texto = f"${abs(valor):,.2f}"
    if valor < 0:
        return f"-{texto}"
    return f"+{texto}" if signo else texto


# ============================================================================
# Clasificar movimientos de un periodo (con o sin filtro de concepto)
# ============================================================================
def _view(periodo_id: int, inversion_id: int | None) -> list[tuple[Movimiento, str]]:  # propio
    """
    Movimientos del periodo que entran en la vista (todos, o solo un concepto),
    cada uno con su clase: "apertura" | "ingreso" | "gasto" | "interno".
    "interno" = traspaso cuya pareja también está en la vista (se cancela).
    """
    movimientos = Movimiento.search_by_period(periodo_id)
    en_vista = lambda m: inversion_id is None or m.inversion_id == inversion_id  # noqa: E731
    por_grupo = defaultdict(list)
    for m in movimientos:
        if m.traspaso_grupo:
            por_grupo[m.traspaso_grupo].append(m)

    resultado = []
    for m in movimientos:
        if not en_vista(m):
            continue
        if m.tipo == "saldo_inicial":
            clase = "apertura"
        elif m.tipo in TIPOS_INGRESO:
            clase = "ingreso"
        elif m.tipo in TIPOS_GASTO:
            clase = "gasto"
        else:  # traspaso
            pareja = [x for x in por_grupo[m.traspaso_grupo] if x.id != m.id]
            if pareja and en_vista(pareja[0]):
                clase = "interno"
            else:
                clase = "ingreso" if m.tipo == "traspaso_entrada" else "gasto"
        resultado.append((m, clase))
    return resultado


@dataclass
class PeriodSummary:
    saldo_apertura: float  # sus saldos iniciales
    ingresos: float        # depósitos + rendimientos (+ traspasos que llegan de fuera)
    gastos: float          # retiros (+ traspasos que salen hacia fuera)
    saldo_cierre: float    # saldo_apertura + ingresos - gastos

    @property
    def neto(self) -> float:  # propio
        return self.ingresos - self.gastos


def period_summary(periodo: Periodo, inversion_id: int | None = None) -> PeriodSummary:  # propio
    """Resumen del periodo; con inversion_id, solo de ese concepto (p. ej. "Casa")."""
    totales = defaultdict(float)
    for m, clase in _view(periodo.id, inversion_id):
        totales[clase] += abs(m.monto) if clase != "apertura" else m.monto
    apertura, ingresos, gastos = totales["apertura"], totales["ingreso"], totales["gasto"]
    return PeriodSummary(
        saldo_apertura=round(apertura, 2),
        ingresos=round(ingresos, 2),
        gastos=round(gastos, 2),
        saldo_cierre=round(apertura + ingresos - gastos, 2),
    )


# ============================================================================
# Acumulado global (periodos abiertos)
# ============================================================================
def global_balance() -> float:  # propio
    """Todo lo que tienes: suma de los periodos abiertos."""
    with SessionLocal() as session:
        return session.scalar(
            select(func.coalesce(func.sum(MONTO_CON_SIGNO), 0.0))
            .join(Periodo, Movimiento.periodo_id == Periodo.id)
            .where(Periodo.cerrado.is_(False))
        )


def balance_by_platform() -> list[tuple[str, float]]:  # propio
    """[(plataforma, saldo)] de los periodos abiertos, de mayor a menor.
    Útil para cuadrar con la app del banco: "Nu" suma Inversiones + Gastos."""
    with SessionLocal() as session:
        consulta = (
            select(Plataforma.nombre, func.sum(MONTO_CON_SIGNO))
            .join(Movimiento, Movimiento.plataforma_id == Plataforma.id)
            .join(Periodo, Movimiento.periodo_id == Periodo.id)
            .where(Periodo.cerrado.is_(False))
            .group_by(Plataforma.id)
            .order_by(func.sum(MONTO_CON_SIGNO).desc())
        )
        return [(nombre, round(total, 2)) for nombre, total in session.execute(consulta)]


# ============================================================================
# Reportes
# ============================================================================
@dataclass
class PlatformShare:
    plataforma_id: int
    nombre: str
    monto: float
    porcentaje: float  # 0-100


def distribution_by_platform(periodo: Periodo,  # propio
                             inversion_id: int | None = None) -> list[PlatformShare]:
    """
    ¿Dónde está el dinero al cierre del periodo? Saldo de cada plataforma con
    los movimientos DEL PERIODO (saldos iniciales incluidos; aquí sí cuentan
    los traspasos, son los que mueven el dinero de lugar).
    Ordenado de menor a mayor, como tu tabla de Excel.
    """
    saldos, nombres = defaultdict(float), {}
    for m, _ in _view(periodo.id, inversion_id):
        saldos[m.plataforma_id] += m.monto_con_signo
        nombres[m.plataforma_id] = m.plataforma_label
    # Plataformas vaciadas (saldo 0 o centavos por redondeo) no aparecen
    filas = [(pid, nombres[pid], round(v, 2)) for pid, v in saldos.items() if round(v, 2) > 0]
    total = sum(v for _, _, v in filas) or 1
    return sorted(
        (PlatformShare(pid, n, v, v * 100 / total) for pid, n, v in filas),
        key=lambda p: p.monto,
    )


@dataclass
class MonthSaving:
    año: int
    mes: int          # 1-12
    neto: float       # lo que ahorraste ese mes (ingresos - gastos)
    acumulado: float  # lo que llevas en el periodo hasta ese mes


def monthly_savings(periodo: Periodo,  # propio
                    inversion_id: int | None = None) -> list[MonthSaving]:
    """
    Ahorro de cada mes = ingresos - gastos (sin saldo inicial; los traspasos
    solo si vienen de / van hacia fuera de lo que estás viendo).
    Incluye los meses sin movimientos (neto 0) hasta el último mes con datos.
    """
    por_mes = defaultdict(float)
    for m, clase in _view(periodo.id, inversion_id):
        if clase == "ingreso":
            por_mes[(m.fecha.year, m.fecha.month)] += m.monto
        elif clase == "gasto":
            por_mes[(m.fecha.year, m.fecha.month)] -= m.monto
    if not por_mes:
        return []

    ultimo = max(por_mes)
    año, mes = periodo.fecha_inicio.year, periodo.fecha_inicio.month
    resultado, acumulado = [], 0.0
    while (año, mes) <= ultimo:
        neto = round(por_mes.get((año, mes), 0.0), 2)
        acumulado = round(acumulado + neto, 2)
        resultado.append(MonthSaving(año, mes, neto, acumulado))
        mes += 1
        if mes == 13:
            año, mes = año + 1, 1
    return resultado


# ============================================================================
# Cerrar / reabrir periodo
# ============================================================================
@dataclass
class ClosingBalance:
    inversion_id: int
    plataforma_id: int
    concepto: str
    plataforma: str
    saldo: float


def closing_balances(periodo: Periodo) -> list[ClosingBalance]:  # propio
    """Saldo final de cada concepto/plataforma: serán los saldos iniciales del siguiente."""
    saldos, nombres = defaultdict(float), {}
    for m in Movimiento.search_by_period(periodo.id):
        clave = (m.inversion_id, m.plataforma_id)
        saldos[clave] += m.monto_con_signo
        nombres[clave] = (m.inversion_label, m.plataforma_label)
    return sorted(
        (ClosingBalance(inv, pla, *nombres[(inv, pla)], round(v, 2))
         for (inv, pla), v in saldos.items() if abs(round(v, 2)) >= 0.01),
        key=lambda s: (s.concepto, s.plataforma),
    )


def close_period(periodo: Periodo, nombre: str, inicio: date, fin: date) -> Periodo:  # propio
    """
    Cierra el periodo y abre el siguiente, en UNA transacción:
      - el actual queda cerrado (solo lectura, fuera del global)
      - el nuevo nace con un saldo inicial por concepto/plataforma, fechado el
        primer día, que cuenta en el global pero no en el ahorro mensual
    """
    if periodo.cerrado:
        raise ValueError("Este periodo ya está cerrado")
    if fin < inicio:
        raise ValueError("La fecha fin no puede ser anterior a la fecha inicio")
    saldos = closing_balances(periodo)
    with SessionLocal() as session:
        actual = session.get(Periodo, periodo.id)
        actual.cerrado = True
        nuevo = Periodo(nombre=nombre.strip(), fecha_inicio=inicio, fecha_fin=fin,
                        cerrado=False, origen_id=periodo.id)
        nuevo._validate()
        session.add(nuevo)
        session.flush()  # para tener nuevo.id
        for s in saldos:
            session.add(Movimiento(
                periodo_id=nuevo.id, inversion_id=s.inversion_id,
                plataforma_id=s.plataforma_id, monto=s.saldo, fecha=inicio,
                tipo="saldo_inicial", comentarios=f"Cierre de {periodo.nombre}",
            ))
        session.commit()
        session.refresh(nuevo)
        return nuevo


def close_only(periodo: Periodo) -> None:  # propio
    """
    Cierra el periodo SIN abrir otro. Sale del acumulado global; tú abres después
    uno nuevo con + y capturas los saldos iniciales que quieras (o los repartes
    en varios periodos).
    """
    if periodo.cerrado:
        raise ValueError("Este periodo ya está cerrado")
    Periodo.update(periodo.id, cerrado=True)


def reopen_period(periodo: Periodo) -> None:  # propio
    """Vuelve a abrir un periodo cerrado (solo si no se abrió otro con su cierre)."""
    hijos = Periodo.children(periodo.id)
    if hijos:
        raise ValueError(
            f"No se puede reabrir: «{hijos[0].nombre}» se abrió con su cierre. "
            "Bórralo primero si quieres corregir este periodo."
        )
    Periodo.update(periodo.id, cerrado=False)


def suggest_next(periodo: Periodo) -> tuple[str, date, date]:  # propio
    """Nombre y fechas propuestos: 'Inversiones 2026' -> 'Inversiones 2027', mismo largo.
    Sin año en el nombre y de año completo: 'Gastos' -> 'Gastos 2027'."""
    import re

    inicio = date.fromordinal(periodo.fecha_fin.toordinal() + 1)
    duracion = periodo.fecha_fin.toordinal() - periodo.fecha_inicio.toordinal()
    # Año completo -> año completo siguiente (evita desfases por años bisiestos)
    año_completo = (periodo.fecha_inicio.month, periodo.fecha_inicio.day) == (1, 1) and \
        (periodo.fecha_fin.month, periodo.fecha_fin.day) == (12, 31)
    if año_completo:
        fin = date(inicio.year, 12, 31)
    else:
        fin = date.fromordinal(inicio.toordinal() + duracion)
    año = re.search(r"(19|20)\d{2}", periodo.nombre)
    if año:
        nombre = periodo.nombre.replace(año.group(), str(int(año.group()) + 1), 1)
    elif año_completo:
        nombre = f"{periodo.nombre} {inicio.year}"  # "Gastos" -> "Gastos 2027"
    else:
        nombre = f"{periodo.nombre} (siguiente)"
    return nombre, inicio, fin

"""
¿Todo lo que el código usa de Flet existe en la versión instalada?

    python scripts/verificar_flet.py

Busca cada `ft.Algo` y `ft.Algo.Otro` en core/, modulos/ y main.py y revisa que
exista en el `flet` instalado. Sirve para dos cosas:
  - atrapar errores como `ft.ActionChip` (no existe en Flet 1.0) ANTES de que
    truene una pantalla (pyflakes no los ve: son atributos, no nombres)
  - al actualizar Flet, ver de un jalón qué cambió de nombre o se quitó
Además avisa lo que Flet marca como "deprecated" (funciona, pero se va a quitar).
"""
import re
import sys
import warnings
from pathlib import Path

import flet as ft

RAIZ = Path(__file__).resolve().parent.parent
PATRON = re.compile(r"\bft\.([A-Za-z_][A-Za-z_0-9]*)(?:\.([A-Za-z_][A-Za-z_0-9]*))?")


def main() -> int:  # propio
    archivos = [RAIZ / "main.py", *RAIZ.glob("core/**/*.py"), *RAIZ.glob("modulos/**/*.py")]
    faltan, obsoletos = set(), set()
    for archivo in archivos:
        for n, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
            for m in PATRON.finditer(linea):
                donde = f"{archivo.relative_to(RAIZ)}:{n}"
                nombre, attr = m.group(1), m.group(2)
                with warnings.catch_warnings(record=True) as avisos:
                    warnings.simplefilter("always")
                    obj = getattr(ft, nombre, None)
                    falta = obj is None or (attr is not None and not hasattr(obj, attr))
                if falta:
                    faltan.add(f"✗ {donde}  ft.{nombre}{'.' + attr if attr else ''}")
                for a in avisos:
                    if issubclass(a.category, DeprecationWarning):
                        obsoletos.add(f"⚠ {donde}  {a.message}")
    print(f"Flet {ft.__version__} · {len(archivos)} archivos revisados")
    for linea in sorted(obsoletos):
        print(linea)
    for linea in sorted(faltan):
        print(linea)
    if faltan:
        print(f"\n✗ {len(faltan)} cosa(s) de Flet que no existen.")
        return 1
    print("✓ Todo lo que se usa de Flet existe.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

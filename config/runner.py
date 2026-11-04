"""Ejecutor de pruebas con informe legible: una línea por prueba (✔/✘), agrupado por módulo.

Uso: python manage.py test --settings=config.settings_ci --testrunner config.runner.InformeRunner
"""
import sys
import time
import unittest
from collections import OrderedDict

from django.test.runner import DiscoverRunner

VERDE, ROJO, AMARILLO, GRIS, NEGRITA, FIN = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m"


def _modulo(prueba):
    """Módulo legible: apps.menu.tests.test_api.PlatoTests -> menu / test_api / PlatoTests."""
    partes = prueba.__class__.__module__.split(".")
    app = partes[1] if len(partes) > 1 and partes[0] == "apps" else partes[0]
    archivo = partes[-1]
    return app, archivo, prueba.__class__.__name__


def _nombre(prueba):
    return prueba._testMethodName.removeprefix("test_").replace("_", " ")


class InformeResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.resumen = OrderedDict()   # app -> {"ok": n, "fallo": n, "omitida": n}
        self._grupo_actual = None
        self._inicio = None

    def _out(self, texto):
        self.stream.write(texto + "\n")
        self.stream.flush()

    def startTest(self, test):
        super().startTest(test)
        self._inicio = time.perf_counter()
        app, archivo, clase = _modulo(test)
        grupo = (app, archivo, clase)
        if grupo != self._grupo_actual:
            self._grupo_actual = grupo
            self._out(f"\n{NEGRITA}{app}{FIN} {GRIS}› {archivo} › {clase}{FIN}")

    def _linea(self, test, simbolo, color, extra=""):
        ms = (time.perf_counter() - self._inicio) * 1000
        self._out(f"  {color}{simbolo}{FIN} {_nombre(test)} {GRIS}({ms:.0f} ms){FIN}{extra}")

    def _contar(self, test, clave):
        app = _modulo(test)[0]
        self.resumen.setdefault(app, {"ok": 0, "fallo": 0, "omitida": 0})[clave] += 1

    def addSuccess(self, test):
        unittest.TestResult.addSuccess(self, test)
        self._contar(test, "ok")
        self._linea(test, "✔", VERDE)

    def addFailure(self, test, err):
        unittest.TestResult.addFailure(self, test, err)
        self._contar(test, "fallo")
        self._linea(test, "✘", ROJO, f" {ROJO}FALLÓ{FIN}")

    def addError(self, test, err):
        unittest.TestResult.addError(self, test, err)
        self._contar(test, "fallo")
        self._linea(test, "✘", ROJO, f" {ROJO}ERROR{FIN}")

    def addSkip(self, test, reason):
        unittest.TestResult.addSkip(self, test, reason)
        self._contar(test, "omitida")
        self._linea(test, "-", AMARILLO, f" {AMARILLO}omitida: {reason}{FIN}")

    def printErrors(self):
        if self.errors or self.failures:
            self._out(f"\n{ROJO}{NEGRITA}Detalle de los fallos{FIN}")
        super().printErrors()


class InformeRunner(DiscoverRunner):
    """DiscoverRunner con salida de informe y tabla resumen por módulo."""

    def get_resultclass(self):
        return InformeResult

    def run_suite(self, suite, **kwargs):
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        inicio = time.perf_counter()
        resultado = super().run_suite(suite, **kwargs)
        self._imprimir_resumen(resultado, time.perf_counter() - inicio)
        return resultado

    def _imprimir_resumen(self, resultado, segundos):
        resumen = getattr(resultado, "resumen", {})
        print(f"\n{NEGRITA}Resumen por módulo{FIN}")
        print(f"  {'módulo':<14}{'pasaron':>9}{'fallaron':>10}{'omitidas':>10}")
        for app, c in resumen.items():
            color = ROJO if c["fallo"] else VERDE
            print(f"  {color}{app:<14}{c['ok']:>9}{c['fallo']:>10}{c['omitida']:>10}{FIN}")
        total_ok = sum(c["ok"] for c in resumen.values())
        total = total_ok + sum(c["fallo"] + c["omitida"] for c in resumen.values())
        estado = f"{VERDE}{NEGRITA}TODAS PASARON{FIN}" if not (resultado.failures or resultado.errors) else f"{ROJO}{NEGRITA}HAY FALLOS{FIN}"
        print(f"\n  {estado}  {total_ok}/{total} pruebas · {segundos:.1f} s\n")

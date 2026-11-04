"""Pruebas del formulario de ingreso (/cuentas/ingresar/): acceso correcto y entradas rechazadas."""
import json
from pathlib import Path

import pytest
from selenium.common.exceptions import NoAlertPresentException

from paginas.ingreso import PaginaIngreso

CASOS = json.loads((Path(__file__).parent / "datos" / "ingreso_casos.json").read_text(encoding="utf-8"))

pytestmark = pytest.mark.ingreso


def test_ingreso_correcto(driver, base_url, evidencia, cuenta_registrada):
    correo, clave = cuenta_registrada
    pagina = PaginaIngreso(driver, base_url).abrir()
    pagina.ingresar(correo, clave)
    evidencia()

    assert pagina.sesion_iniciada(), f"No inició sesión: {pagina.mensajes_de_error()}"
    assert pagina.sin_error_de_servidor()


def test_ingreso_no_distingue_mayusculas_en_el_correo(driver, base_url, evidencia, cuenta_registrada):
    correo, clave = cuenta_registrada
    pagina = PaginaIngreso(driver, base_url).abrir()
    pagina.ingresar(correo.upper(), clave)
    evidencia()

    assert pagina.sesion_iniciada()


@pytest.mark.parametrize("caso", CASOS, ids=[c["id"] for c in CASOS])
def test_ingreso_rechaza_credenciales_invalidas(driver, base_url, evidencia, cuenta_registrada, caso):
    correo, _ = cuenta_registrada
    pagina = PaginaIngreso(driver, base_url).abrir()
    pagina.ingresar(caso["correo"].replace("{cuenta}", correo), caso["clave"])
    evidencia()

    assert not pagina.sesion_iniciada(), f"{caso['descripcion']}: el sistema dejó entrar"
    assert pagina.mensajes_de_error(), "No se mostró ningún mensaje de error"
    assert pagina.sin_error_de_servidor()
    with pytest.raises(NoAlertPresentException):     # un XSS ejecutado abriría un alert()
        driver.switch_to.alert

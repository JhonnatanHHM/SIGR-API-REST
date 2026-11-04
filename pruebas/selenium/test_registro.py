"""Pruebas del formulario de registro (/cuentas/registro/): datos válidos e inválidos, guiadas por datos."""
import json
from pathlib import Path

import pytest

from conftest import correo_unico
from paginas.registro import PaginaRegistro

CASOS = json.loads((Path(__file__).parent / "datos" / "registro_casos.json").read_text(encoding="utf-8"))
EXITOSOS = [c for c in CASOS if c["esperado"] == "exito"]
RECHAZADOS = [c for c in CASOS if c["esperado"] != "exito"]

pytestmark = pytest.mark.registro


def _con_correo(caso):
    """Cada ejecución usa un correo nuevo salvo que el caso defina el suyo (vacío o mal formado)."""
    cambios = dict(caso["cambios"])
    cambios.setdefault("email", correo_unico())
    return cambios


@pytest.mark.parametrize("caso", EXITOSOS, ids=[c["id"] for c in EXITOSOS])
def test_registro_exitoso(driver, base_url, evidencia, caso):
    pagina = PaginaRegistro(driver, base_url).abrir()
    pagina.completar(**_con_correo(caso))
    pagina.enviar()
    evidencia()

    assert "/registro/" not in driver.current_url, f"{caso['descripcion']}: siguió en el formulario con {pagina.mensajes_de_error()}"
    assert "Tu cuenta fue creada" in pagina.mensaje_de_exito()
    assert pagina.sin_error_de_servidor()


@pytest.mark.parametrize("caso", RECHAZADOS, ids=[c["id"] for c in RECHAZADOS])
def test_registro_rechaza_datos_invalidos(driver, base_url, evidencia, caso):
    pagina = PaginaRegistro(driver, base_url).abrir()
    pagina.completar(**_con_correo(caso))
    pagina.enviar()
    evidencia()

    assert "/registro/" in driver.current_url, f"{caso['descripcion']}: el sistema aceptó datos inválidos"
    con_error = set(pagina.campos_con_error())
    assert set(caso["esperado"]) <= con_error, f"Se esperaba error en {caso['esperado']} y hubo en {sorted(con_error)}"
    assert pagina.sin_error_de_servidor()
    assert not pagina.mensaje_de_exito()


def test_registro_rechaza_correo_repetido_sin_distinguir_mayusculas(driver, base_url, evidencia, cuenta_registrada):
    correo, _ = cuenta_registrada
    pagina = PaginaRegistro(driver, base_url).abrir()
    pagina.completar(email=correo.upper())
    pagina.enviar()
    evidencia()

    assert "/registro/" in driver.current_url
    assert "email" in pagina.campos_con_error()
    assert any("Ya existe" in m for m in pagina.mensajes_de_error())

"""Configuración común: navegador, URL base, evidencias (capturas) y una cuenta de apoyo."""
import os
import re
import time
import uuid
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as OpcionesChrome
from selenium.webdriver.edge.options import Options as OpcionesEdge

from paginas.registro import PaginaRegistro

CAPTURAS = Path(__file__).parent / "capturas"
CLAVE = "Prueba-Segura-2026!"


def pytest_addoption(parser):
    parser.addoption("--navegador", default=os.getenv("SIGR_NAVEGADOR", "chrome"), choices=["chrome", "edge"])
    parser.addoption("--visible", action="store_true", help="Muestra el navegador en lugar de ejecutarlo sin ventana")
    parser.addoption("--url", default=os.getenv("SIGR_WEB_URL", "http://127.0.0.1:8000"), help="URL base del sistema web")


@pytest.fixture(scope="session")
def base_url(request):
    return request.config.getoption("--url")


@pytest.fixture
def driver(request):
    """Un navegador limpio por prueba, siempre cerrado al terminar."""
    visible = request.config.getoption("--visible")
    if request.config.getoption("--navegador") == "edge":
        opciones, navegador = OpcionesEdge(), webdriver.Edge
    else:
        opciones, navegador = OpcionesChrome(), webdriver.Chrome
    if not visible:
        opciones.add_argument("--headless=new")
    opciones.add_argument("--window-size=1280,900")
    opciones.add_argument("--lang=es")
    instancia = navegador(options=opciones)
    instancia.implicitly_wait(0)          # solo esperas explícitas
    yield instancia
    instancia.quit()


def _nombre_archivo(texto):
    return re.sub(r"[^\w\-]+", "_", texto).strip("_")[:90]


@pytest.fixture
def evidencia(driver, request):
    """Guarda una captura de pantalla con el nombre de la prueba: evidencia para el informe."""
    CAPTURAS.mkdir(exist_ok=True)

    def capturar(etiqueta=""):
        nombre = _nombre_archivo(f"{request.node.name}_{etiqueta}" if etiqueta else request.node.name)
        driver.save_screenshot(str(CAPTURAS / f"{nombre}.png"))

    return capturar


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Si una prueba falla, deja siempre una captura del estado en que quedó el navegador."""
    resultado = (yield).get_result()
    driver = item.funcargs.get("driver")
    if resultado.when == "call" and resultado.failed and driver:
        CAPTURAS.mkdir(exist_ok=True)
        driver.save_screenshot(str(CAPTURAS / f"FALLO_{_nombre_archivo(item.name)}.png"))


def correo_unico(prefijo="selenium"):
    return f"{prefijo}.{int(time.time())}.{uuid.uuid4().hex[:6]}@prueba.test"


@pytest.fixture
def cuenta_registrada(driver, base_url):
    """Crea una cuenta nueva por el propio formulario y cierra la sesión; devuelve (correo, clave)."""
    correo = correo_unico("apoyo")
    pagina = PaginaRegistro(driver, base_url).abrir()
    pagina.completar(email=correo)
    pagina.enviar()
    assert "/registro/" not in driver.current_url, f"No se pudo crear la cuenta de apoyo: {pagina.mensajes_de_error()}"
    driver.delete_all_cookies()           # equivale a cerrar sesión
    return correo, CLAVE

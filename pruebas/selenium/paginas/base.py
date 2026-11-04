"""Página base: esperas explícitas y acciones comunes. Ninguna prueba usa sleep()."""
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ESPERA_SEGUNDOS = 10


class PaginaBase:
    RUTA = "/"

    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.espera = WebDriverWait(driver, ESPERA_SEGUNDOS)

    def abrir(self):
        self.driver.get(self.base_url + self.RUTA)
        self.esperar_visible((By.CSS_SELECTOR, "form"))
        return self

    def esperar_visible(self, localizador):
        try:
            return self.espera.until(EC.visibility_of_element_located(localizador))
        except TimeoutException:
            raise AssertionError(f"No apareció {localizador} en {ESPERA_SEGUNDOS} s (URL actual: {self.driver.current_url})") from None

    def escribir(self, localizador, texto):
        campo = self.esperar_visible(localizador)
        campo.clear()
        if texto:
            campo.send_keys(texto)

    def textos(self, localizador):
        return [e.text.strip() for e in self.driver.find_elements(*localizador) if e.text.strip()]

    def esperar_resultado(self, localizador_error, ruta_formulario):
        """Espera a que el envío termine: o se sale del formulario o aparece un mensaje de error."""
        try:
            self.espera.until(lambda d: ruta_formulario not in d.current_url or d.find_elements(*localizador_error))
        except TimeoutException:
            raise AssertionError("El formulario no respondió: ni redirigió ni mostró errores") from None

    def sin_error_de_servidor(self):
        fuente = self.driver.page_source
        return not any(marca in fuente for marca in ("Traceback", "Server Error", "OperationalError", "DoesNotExist"))

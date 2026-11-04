"""Page Object del formulario de ingreso (/cuentas/ingresar/)."""
from selenium.webdriver.common.by import By

from .base import PaginaBase
from .registro import BOTON_ENVIAR, ERROR_CAMPO, ERROR_GENERAL, HAY_ERRORES


class PaginaIngreso(PaginaBase):
    RUTA = "/cuentas/ingresar/"

    def ingresar(self, correo, clave):
        self.escribir((By.ID, "id_username"), correo)
        self.escribir((By.ID, "id_password"), clave)
        self.driver.find_element(*BOTON_ENVIAR).click()
        self.esperar_resultado(HAY_ERRORES, self.RUTA)
        return self

    def mensajes_de_error(self):
        return self.textos(ERROR_CAMPO) + self.textos(ERROR_GENERAL)

    def sesion_iniciada(self):
        """Tras un ingreso correcto el sistema sale del formulario y lleva al inicio."""
        return self.RUTA not in self.driver.current_url

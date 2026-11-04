"""Page Object del formulario de registro (/cuentas/registro/)."""
from selenium.webdriver.common.by import By

from .base import PaginaBase

CAMPOS = ("first_name", "last_name", "email", "telefono", "password1", "password2")
VALIDOS = {
    "first_name": "Laura", "last_name": "Gómez", "email": "", "telefono": "+573001234567",
    "password1": "Prueba-Segura-2026!", "password2": "Prueba-Segura-2026!",
}
ERROR_CAMPO = (By.CSS_SELECTOR, ".campo__error")
ERROR_GENERAL = (By.CSS_SELECTOR, ".formulario__errores")
HAY_ERRORES = (By.CSS_SELECTOR, ".campo__error, .formulario__errores")
MENSAJE_EXITO = (By.CSS_SELECTOR, ".mensaje--success")
BOTON_ENVIAR = (By.CSS_SELECTOR, "form.auth__tarjeta button[type=submit]")


class PaginaRegistro(PaginaBase):
    RUTA = "/cuentas/registro/"

    def completar(self, **cambios):
        """Llena el formulario con datos válidos, sustituyendo solo lo que cambia el caso."""
        datos = {**VALIDOS, **cambios}
        for campo in CAMPOS:
            self.escribir((By.ID, f"id_{campo}"), datos[campo])
        return datos

    def enviar(self):
        self.driver.find_element(*BOTON_ENVIAR).click()
        self.esperar_resultado(HAY_ERRORES, self.RUTA)
        return self

    def campos_con_error(self):
        """Nombres de los campos que muestran un mensaje de error."""
        con_error = []
        for campo in CAMPOS:
            mensajes = self.driver.find_elements(
                By.XPATH, f"//*[@id='id_{campo}']/ancestor::div[contains(@class,'campo')][1]//p[contains(@class,'campo__error')]")
            if mensajes:
                con_error.append(campo)
        return con_error

    def mensajes_de_error(self):
        return self.textos(ERROR_CAMPO) + self.textos(ERROR_GENERAL)

    def mensaje_de_exito(self):
        return " ".join(self.textos(MENSAJE_EXITO))

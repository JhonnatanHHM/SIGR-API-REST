from datetime import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.usuarios.models import Rol
from apps.usuarios.tests.base import CLAVE, cliente_api, crear_usuario  # noqa: F401

AHORA = timezone.make_aware(datetime(2026, 11, 10, 10, 0))      # el reloj de las pruebas queda fijo


def cliente_con_token(token):
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    return cliente


class EntornoMixin:
    """Reloj fijo, menú de demostración y un usuario de cada rol."""

    def setUp(self):
        parche = patch("django.utils.timezone.now", return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        call_command("cargar_menu_demo", stdout=StringIO())
        self.cliente = crear_usuario("cli@ejemplo.com", Rol.CLIENTE)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)

    def ingresar(self, correo):
        """Inicia sesión por la API (como lo haría Postman) y devuelve un cliente autenticado."""
        r = APIClient().post("/api/v1/auth/login/", {"email": correo, "password": CLAVE}, format="json")
        assert r.status_code == 200, r.content
        return cliente_con_token(r.json()["token"])

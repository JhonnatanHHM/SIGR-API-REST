from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.usuarios.models import Rol, Usuario

CLAVE = "Contr4seña-Muy-Segura!"


def crear_usuario(email, rol=Rol.CLIENTE, **extra):
    return Usuario.objects.create_user(email, CLAVE, first_name="Nombre", last_name="Apellido", rol=rol, **extra)


def cliente_api(usuario=None):
    """Cliente HTTP de pruebas; si se indica un usuario, queda autenticado con su token real."""
    cliente = APIClient()
    if usuario is not None:
        token, _ = Token.objects.get_or_create(user=usuario)
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return cliente


def datos_registro(**cambios):
    base = {
        "first_name": "María José",
        "last_name": "O'Connor-Pérez",
        "email": "maria@ejemplo.com",
        "telefono": "+57 300-123-4567",
        "password": CLAVE,
        "password_confirmacion": CLAVE,
    }
    base.update(cambios)
    return base

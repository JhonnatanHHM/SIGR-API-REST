"""Configuración para integración continua y pruebas rápidas sobre PostgreSQL real.

Usa la base definida en las variables de entorno (DB_*), igual que el desarrollo, pero con un cifrador de
contraseñas rápido: el cifrado lento de producción hace las pruebas varias veces más lentas.
Uso: python manage.py test --settings=config.settings_ci"""
import tempfile

from .settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]      # solo para pruebas
ALLOWED_HOSTS = ["testserver", "localhost"]
MEDIA_ROOT = tempfile.mkdtemp(prefix="media_api_ci_")

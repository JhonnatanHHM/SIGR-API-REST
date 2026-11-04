"""Configuración para pruebas rápidas: base SQLite en memoria (no hace falta PostgreSQL) y fotos en una carpeta temporal.
Uso: python manage.py test --settings=config.settings_test"""
import tempfile

from .settings import *  # noqa: F401,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]      # más rápido; solo para pruebas
ALLOWED_HOSTS = ["testserver", "localhost"]
MEDIA_ROOT = tempfile.mkdtemp(prefix="media_api_prueba_")

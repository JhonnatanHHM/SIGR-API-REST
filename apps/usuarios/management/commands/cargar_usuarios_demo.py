"""Crea un usuario de cada rol con una contraseña conocida, para probar la API (Postman, Swagger). Solo en desarrollo.
Uso: python manage.py cargar_usuarios_demo [--reiniciar-claves]"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.usuarios.models import Rol, Usuario

CLAVE_DEMO = "Prueba-Segura-2026!"
USUARIOS_DEMO = [
    ("admin@sigr.test", "Ada", "Administradora", Rol.ADMINISTRADOR),
    ("mesero@sigr.test", "Mario", "Mesero", Rol.MESERO),
    ("cliente@sigr.test", "Clara", "Cliente", Rol.CLIENTE),
]


class Command(BaseCommand):
    help = "Crea usuarios de demostración (administrador, mesero y cliente) con una contraseña conocida"

    def add_arguments(self, parser):
        parser.add_argument("--reiniciar-claves", action="store_true", help="Restablece la contraseña de los usuarios que ya existen")

    def handle(self, *args, **opciones):
        if not settings.DEBUG:
            raise CommandError("Los usuarios de demostración tienen una contraseña pública: solo se crean con DJANGO_DEBUG=1.")
        creados = 0
        for correo, nombre, apellido, rol in USUARIOS_DEMO:
            usuario, nuevo = Usuario.objects.get_or_create(
                email=correo, defaults={"first_name": nombre, "last_name": apellido, "rol": rol}
            )
            if nuevo or opciones["reiniciar_claves"]:
                usuario.set_password(CLAVE_DEMO)
                usuario.rol, usuario.is_active = rol, True
                usuario.save()
            creados += nuevo
        self.stdout.write(self.style.SUCCESS(f"Usuarios de demostración listos ({creados} nuevos). Contraseña: {CLAVE_DEMO}"))
        for correo, _, _, rol in USUARIOS_DEMO:
            self.stdout.write(f"  {rol:<14} {correo}")

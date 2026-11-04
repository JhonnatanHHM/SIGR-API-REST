from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.usuarios.management.commands.cargar_usuarios_demo import CLAVE_DEMO
from apps.usuarios.models import Rol, Usuario


def ejecutar(*args):
    salida = StringIO()
    call_command("cargar_usuarios_demo", *args, stdout=salida)
    return salida.getvalue()


@override_settings(DEBUG=True)
class CargarUsuariosDemoTests(TestCase):
    def test_crea_un_usuario_por_rol_que_puede_ingresar_por_la_api(self):
        ejecutar()
        self.assertEqual(
            {u.email: u.rol for u in Usuario.objects.all()},
            {"admin@sigr.test": Rol.ADMINISTRADOR, "mesero@sigr.test": Rol.MESERO, "cliente@sigr.test": Rol.CLIENTE},
        )
        for correo in ("admin@sigr.test", "mesero@sigr.test", "cliente@sigr.test"):
            r = APIClient().post("/api/v1/auth/login/", {"email": correo, "password": CLAVE_DEMO}, format="json")
            self.assertEqual(r.status_code, 200, correo)

    def test_es_idempotente_y_respeta_las_claves_cambiadas(self):
        ejecutar()
        usuario = Usuario.objects.get(email="cliente@sigr.test")
        usuario.set_password("otra-clave-Segura-77")
        usuario.save()
        self.assertIn("0 nuevos", ejecutar())
        self.assertEqual(Usuario.objects.count(), 3)
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password("otra-clave-Segura-77"))

    def test_reiniciar_claves_restablece_la_contrasena_y_reactiva_la_cuenta(self):
        ejecutar()
        usuario = Usuario.objects.get(email="mesero@sigr.test")
        usuario.set_password("otra-clave-Segura-77")
        usuario.is_active = False
        usuario.save()
        ejecutar("--reiniciar-claves")
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(CLAVE_DEMO) and usuario.is_active)

    @override_settings(DEBUG=False)
    def test_no_se_ejecuta_fuera_de_desarrollo(self):
        with self.assertRaises(CommandError):
            ejecutar()
        self.assertEqual(Usuario.objects.count(), 0)

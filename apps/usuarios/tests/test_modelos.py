from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.usuarios.models import Rol, Usuario


class UsuarioModeloTests(TestCase):
    def test_create_user_es_cliente_y_normaliza_correo(self):
        u = Usuario.objects.create_user("  Ana@Correo.COM ".strip(), "Clave-segura-123", first_name="Ana", last_name="Pérez")
        self.assertEqual(u.email, "ana@correo.com")
        self.assertEqual(u.rol, Rol.CLIENTE)
        self.assertTrue(u.check_password("Clave-segura-123"))

    def test_create_superuser_es_administrador(self):
        u = Usuario.objects.create_superuser("admin@correo.com", "Clave-segura-123", first_name="Ada", last_name="Min")
        self.assertTrue(u.is_staff and u.is_superuser)
        self.assertEqual(u.rol, Rol.ADMINISTRADOR)

    def test_correo_obligatorio(self):
        with self.assertRaises(ValueError):
            Usuario.objects.create_user("", "x")

    def test_correo_unico_sin_importar_mayusculas(self):
        Usuario.objects.create_user("a@b.com", "Clave-segura-123", first_name="A", last_name="B")
        u = Usuario(email="A@B.com", first_name="Otra", last_name="Persona")
        u.email = u.email.lower()
        with self.assertRaises(ValidationError):
            u.full_clean(exclude=["password"])

    def test_validadores_de_nombre_y_telefono(self):
        u = Usuario(email="x@y.com", first_name="Ana1", last_name="Pérez", telefono="abc")
        with self.assertRaises(ValidationError) as ctx:
            u.full_clean(exclude=["password"])
        self.assertIn("first_name", ctx.exception.message_dict)
        self.assertIn("telefono", ctx.exception.message_dict)

    def test_propiedades_de_rol(self):
        self.assertTrue(Usuario(rol=Rol.MESERO).es_mesero)
        self.assertTrue(Usuario(rol=Rol.ADMINISTRADOR).es_administrador)
        self.assertTrue(Usuario(rol=Rol.CLIENTE).es_cliente)

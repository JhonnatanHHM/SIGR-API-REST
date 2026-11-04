from django.test import TestCase

from apps.usuarios.models import Rol, Usuario
from apps.usuarios.serializers import FiltroUsuarioSerializer, LoginSerializer, PersonalSerializer, RegistroSerializer

from .base import CLAVE, crear_usuario, datos_registro


def errores(serializador):
    serializador.is_valid()
    return serializador.errors


class RegistroSerializerTests(TestCase):
    def test_datos_validos_se_normalizan(self):
        s = RegistroSerializer(data=datos_registro(first_name="  María   José ", email="  MARIA@Ejemplo.COM "))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["first_name"], "María José")
        self.assertEqual(s.validated_data["email"], "maria@ejemplo.com")
        self.assertEqual(s.validated_data["telefono"], "+573001234567")

    def test_formatos_de_correo_invalidos(self):
        for malo in ["sin-arroba", "a@", "@b.com", "a b@c.com", "' OR '1'='1", "x@y.com'; DROP TABLE usuarios_usuario;--", "a" * 250 + "@b.com"]:
            with self.subTest(correo=malo):
                self.assertIn("email", errores(RegistroSerializer(data=datos_registro(email=malo))))

    def test_nombres_solo_letras(self):
        for malo in ["Ana1", "<script>alert(1)</script>", "Robert'); DROP TABLE x;--", "Ana_Maria", "12345", "A" * 61]:
            for campo in ("first_name", "last_name"):
                with self.subTest(campo=campo, valor=malo):
                    self.assertIn(campo, errores(RegistroSerializer(data=datos_registro(**{campo: malo}))))

    def test_telefono_formato(self):
        for malo in ["abc", "12", "+1234567890123456", "300-ABC-1234", "1; DROP TABLE"]:
            with self.subTest(telefono=malo):
                self.assertIn("telefono", errores(RegistroSerializer(data=datos_registro(telefono=malo))))

    def test_telefono_es_opcional(self):
        self.assertTrue(RegistroSerializer(data=datos_registro(telefono="")).is_valid())
        sin_telefono = datos_registro()
        del sin_telefono["telefono"]
        self.assertTrue(RegistroSerializer(data=sin_telefono).is_valid())

    def test_tipos_de_dato_incorrectos_no_provocan_errores(self):
        for campo in ("first_name", "last_name", "email", "telefono", "password"):
            for malo in (None, 123, ["a"], {"a": 1}, True):
                with self.subTest(campo=campo, valor=malo):
                    encontrados = set(errores(RegistroSerializer(data=datos_registro(**{campo: malo}))))
                    # DRF convierte el número 123 en el texto "123": para la clave queda como «no coincide» con su confirmación
                    self.assertTrue(encontrados & {campo, "password_confirmacion"}, encontrados)

    def test_campos_obligatorios(self):
        self.assertEqual(set(errores(RegistroSerializer(data={}))), {"first_name", "last_name", "email", "password", "password_confirmacion"})

    def test_correo_duplicado_ignora_mayusculas(self):
        crear_usuario("maria@ejemplo.com")
        self.assertIn("email", errores(RegistroSerializer(data=datos_registro(email="MARIA@EJEMPLO.COM"))))

    def test_claves_distintas_o_debiles(self):
        self.assertIn("password_confirmacion", errores(RegistroSerializer(data=datos_registro(password_confirmacion="otra"))))
        self.assertIn("password", errores(RegistroSerializer(data=datos_registro(password="12345678", password_confirmacion="12345678"))))

    def test_siempre_crea_cliente_aunque_envien_rol_o_permisos(self):
        s = RegistroSerializer(data=datos_registro(rol=Rol.ADMINISTRADOR, is_superuser=True, is_staff=True))
        self.assertTrue(s.is_valid(), s.errors)
        usuario = s.crear_usuario()
        self.assertEqual(usuario.rol, Rol.CLIENTE)
        self.assertFalse(usuario.is_staff or usuario.is_superuser)


class PersonalSerializerTests(TestCase):
    def test_rol_solo_mesero_o_administrador(self):
        self.assertTrue(PersonalSerializer(data=datos_registro(rol=Rol.MESERO)).is_valid())
        for rol in (Rol.CLIENTE, "superjefe", None, 5):
            self.assertIn("rol", errores(PersonalSerializer(data=datos_registro(rol=rol))), rol)
        self.assertIn("rol", errores(PersonalSerializer(data=datos_registro())))


class LoginSerializerTests(TestCase):
    def test_exige_formato_de_correo(self):
        self.assertIn("email", errores(LoginSerializer(data={"email": "' OR 1=1 --", "password": "x"})))

    def test_campos_obligatorios(self):
        self.assertEqual(set(errores(LoginSerializer(data={}))), {"email", "password"})


class FiltroUsuarioSerializerTests(TestCase):
    def test_busqueda_valida(self):
        s = FiltroUsuarioSerializer(data={"q": "  ana   pérez ", "rol": Rol.MESERO})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["q"], "ana pérez")

    def test_rechaza_caracteres_peligrosos_y_roles_invalidos(self):
        for malo in ["' OR 1=1 --", "a; DROP TABLE x", "<script>", "a%b", "x" * 101]:
            with self.subTest(q=malo):
                self.assertIn("q", errores(FiltroUsuarioSerializer(data={"q": malo})))
        self.assertIn("rol", errores(FiltroUsuarioSerializer(data={"rol": "hacker"})))

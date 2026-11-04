from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.usuarios.models import Rol, Usuario

from .base import CLAVE, cliente_api, crear_usuario, datos_registro


class RegistroTests(TestCase):
    def test_registro_crea_cliente_y_devuelve_token_que_funciona(self):
        r = APIClient().post(reverse("auth-registro"), datos_registro(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertEqual(cuerpo["usuario"]["rol"], Rol.CLIENTE)
        self.assertEqual(cuerpo["usuario"]["telefono"], "+573001234567")
        self.assertNotIn("password", str(cuerpo))
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {cuerpo['token']}")
        self.assertEqual(cliente.get(reverse("auth-yo")).json()["email"], "maria@ejemplo.com")

    def test_registro_no_permite_asignarse_rol_ni_permisos(self):
        r = APIClient().post(reverse("auth-registro"), datos_registro(rol="administrador", is_staff=True, is_superuser=True), format="json")
        self.assertEqual(r.status_code, 201)
        usuario = Usuario.objects.get(email="maria@ejemplo.com")
        self.assertEqual(usuario.rol, Rol.CLIENTE)
        self.assertFalse(usuario.is_staff or usuario.is_superuser)

    def test_registro_invalido_no_crea_usuarios(self):
        for cambios in [{"email": "no-es-correo"}, {"first_name": "Ana1"}, {"telefono": "abc"}, {"password": "12345678", "password_confirmacion": "12345678"}, {"password_confirmacion": "distinta"}]:
            r = APIClient().post(reverse("auth-registro"), datos_registro(**cambios), format="json")
            self.assertEqual(r.status_code, 400, cambios)
        self.assertEqual(Usuario.objects.count(), 0)

    def test_correo_repetido_responde_400(self):
        crear_usuario("maria@ejemplo.com")
        r = APIClient().post(reverse("auth-registro"), datos_registro(email="MARIA@ejemplo.com"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())

    def test_cuerpo_que_no_es_json_valido_responde_error_controlado(self):
        r = APIClient().post(reverse("auth-registro"), "esto no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = APIClient().post(reverse("auth-registro"), "x=1", content_type="text/plain")
        self.assertEqual(r.status_code, 415)

    def test_un_token_viejo_o_invalido_no_bloquea_el_registro_publico(self):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION="Token tokeninvalido")
        self.assertEqual(cliente.post(reverse("auth-registro"), datos_registro(), format="json").status_code, 201)

    def test_solo_acepta_post(self):
        for metodo in ("get", "put", "patch", "delete"):
            self.assertEqual(getattr(APIClient(), metodo)(reverse("auth-registro")).status_code, 405, metodo)


class LoginTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("cli@ejemplo.com")

    def login(self, **cambios):
        datos = {"email": "cli@ejemplo.com", "password": CLAVE}
        datos.update(cambios)
        return APIClient().post(reverse("auth-login"), datos, format="json")

    def test_login_correcto_devuelve_token_y_usuario(self):
        r = self.login(email="CLI@ejemplo.com")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["token"], Token.objects.get(user=self.usuario).key)
        self.assertEqual(r.json()["usuario"]["email"], "cli@ejemplo.com")

    def test_el_token_es_estable_entre_ingresos(self):
        self.assertEqual(self.login().json()["token"], self.login().json()["token"])

    def test_credenciales_invalidas_responden_401(self):
        for cambios in [{"password": "incorrecta"}, {"email": "otro@ejemplo.com"}]:
            r = self.login(**cambios)
            self.assertEqual(r.status_code, 401, cambios)
            self.assertEqual(r.json()["detail"], "Credenciales inválidas.")

    def test_usuario_inactivo_no_entra(self):
        self.usuario.is_active = False
        self.usuario.save()
        self.assertEqual(self.login().status_code, 401)

    def test_entradas_hostiles_no_entran_ni_fallan(self):
        for carga in ["' OR '1'='1' --", "admin@x.com'; DROP TABLE usuarios_usuario;--", "<script>alert(1)</script>", "A" * 5000]:
            for campo in ("email", "password"):
                r = self.login(**{campo: carga})
                self.assertIn(r.status_code, (400, 401), (campo, carga[:20]))
                self.assertNotIn("token", r.json())
        self.assertTrue(Usuario.objects.filter(email="cli@ejemplo.com").exists())

    def test_tipos_incorrectos_responden_400(self):
        for datos in [{}, {"email": None, "password": "x"}, {"email": ["a@b.com"], "password": "x"}, {"email": "a@b.com", "password": {"a": 1}}]:
            self.assertEqual(APIClient().post(reverse("auth-login"), datos, format="json").status_code, 400, datos)


class LogoutYPerfilTests(TestCase):
    def setUp(self):
        self.usuario = crear_usuario("cli@ejemplo.com")
        self.cliente = cliente_api(self.usuario)

    def test_logout_invalida_el_token(self):
        self.assertEqual(self.cliente.post(reverse("auth-logout")).status_code, 204)
        self.assertEqual(self.cliente.get(reverse("auth-yo")).status_code, 401)

    def test_logout_sin_credenciales_responde_401(self):
        self.assertEqual(APIClient().post(reverse("auth-logout")).status_code, 401)

    def test_ver_y_editar_mi_cuenta(self):
        self.assertEqual(self.cliente.get(reverse("auth-yo")).json()["rol"], Rol.CLIENTE)
        r = self.cliente.patch(reverse("auth-yo"), {"first_name": "  Nuevo   Nombre ", "telefono": "300 111 2222"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["first_name"], r.json()["telefono"]), ("Nuevo Nombre", "3001112222"))

    def test_correo_y_rol_no_se_pueden_cambiar(self):
        self.cliente.patch(reverse("auth-yo"), {"email": "otro@ejemplo.com", "rol": "administrador"}, format="json")
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.email, self.usuario.rol), ("cli@ejemplo.com", Rol.CLIENTE))

    def test_datos_invalidos_responden_400(self):
        for cambios in [{"first_name": "Ana1"}, {"telefono": "abc"}, {"last_name": "<b>x</b>"}]:
            self.assertEqual(self.cliente.patch(reverse("auth-yo"), cambios, format="json").status_code, 400, cambios)

    def test_put_y_delete_no_estan_permitidos(self):
        self.assertEqual(self.cliente.put(reverse("auth-yo"), {}, format="json").status_code, 405)
        self.assertEqual(self.cliente.delete(reverse("auth-yo")).status_code, 405)


class AutenticacionTests(TestCase):
    def test_sin_credenciales_responde_401_con_cabecera_www_authenticate(self):
        for url in (reverse("auth-yo"), reverse("usuario-list")):
            r = APIClient().get(url)
            self.assertEqual(r.status_code, 401, url)
            self.assertEqual(r["WWW-Authenticate"], "Token")

    def test_token_invalido_o_con_formato_incorrecto_responde_401(self):
        for cabecera in ("Token tokeninvalido", "Bearer abc", "Token", "Token a b", "basura"):
            cliente = APIClient()
            cliente.credentials(HTTP_AUTHORIZATION=cabecera)
            self.assertEqual(cliente.get(reverse("auth-yo")).status_code, 401, cabecera)

    def test_usuario_desactivado_pierde_el_acceso_aunque_conserve_el_token(self):
        usuario = crear_usuario("cli@ejemplo.com")
        cliente = cliente_api(usuario)
        usuario.is_active = False
        usuario.save()
        self.assertEqual(cliente.get(reverse("auth-yo")).status_code, 401)


class AdministracionDeUsuariosTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.cliente = crear_usuario("lucia@ejemplo.com", Rol.CLIENTE)

    def test_solo_el_administrador_accede(self):
        for usuario, esperado in ((self.cliente, 403), (self.mesero, 403), (self.admin, 200)):
            c = cliente_api(usuario)
            self.assertEqual(c.get(reverse("usuario-list")).status_code, esperado, usuario.rol)
            self.assertEqual(c.get(reverse("usuario-detail", args=[self.cliente.pk])).status_code, 200 if esperado == 200 else 403)
            self.assertEqual(c.post(reverse("usuario-list"), datos_registro(rol="mesero"), format="json").status_code, 201 if esperado == 200 else 403)
            Usuario.objects.filter(email="maria@ejemplo.com").delete()

    def test_crear_personal_informa_su_ubicacion(self):
        r = cliente_api(self.admin).post(reverse("usuario-list"), datos_registro(rol="mesero"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r["Location"], f"/api/v1/usuarios/{r.json()['id']}/")

    def test_listado_paginado_con_orden_estable(self):
        r = cliente_api(self.admin).get(reverse("usuario-list"))
        cuerpo = r.json()
        self.assertEqual(set(cuerpo), {"count", "next", "previous", "results"})
        self.assertEqual(cuerpo["count"], 3)
        self.assertNotIn("password", str(cuerpo))

    def test_tamano_de_pagina_y_pagina_inexistente(self):
        c = cliente_api(self.admin)
        self.assertEqual(len(c.get(reverse("usuario-list"), {"page_size": 2}).json()["results"]), 2)
        self.assertEqual(c.get(reverse("usuario-list"), {"page": 99}).status_code, 404)

    def test_busqueda_y_filtro_por_rol(self):
        c = cliente_api(self.admin)
        self.assertEqual([u["email"] for u in c.get(reverse("usuario-list"), {"q": "lucia"}).json()["results"]], ["lucia@ejemplo.com"])
        self.assertEqual([u["email"] for u in c.get(reverse("usuario-list"), {"rol": "mesero"}).json()["results"]], ["mes@ejemplo.com"])
        self.assertEqual(c.get(reverse("usuario-list"), {"q": "lucia", "rol": "mesero"}).json()["count"], 0)

    def test_filtros_hostiles_responden_400_y_no_tocan_la_base(self):
        c = cliente_api(self.admin)
        for params in [{"q": "' OR 1=1 --"}, {"q": "x'; DROP TABLE usuarios_usuario; --"}, {"q": "<script>alert(1)</script>"}, {"rol": "hacker"}, {"q": "x" * 101}]:
            r = c.get(reverse("usuario-list"), params)
            self.assertEqual(r.status_code, 400, params)
            self.assertTrue(set(r.json()) & {"q", "rol"})
        self.assertEqual(Usuario.objects.count(), 3)

    def test_ver_un_usuario_y_ids_inexistentes(self):
        c = cliente_api(self.admin)
        self.assertEqual(c.get(reverse("usuario-detail", args=[self.mesero.pk])).json()["rol"], Rol.MESERO)
        self.assertEqual(c.get(reverse("usuario-detail", args=[999999])).status_code, 404)
        self.assertEqual(c.get("/api/v1/usuarios/abc/").status_code, 404)

    def test_admin_da_de_alta_a_un_mesero_que_puede_ingresar(self):
        r = cliente_api(self.admin).post(reverse("usuario-list"), datos_registro(email="mario@ejemplo.com", rol="mesero"), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["rol"], Rol.MESERO)
        self.assertNotIn("token", r.json())
        login = APIClient().post(reverse("auth-login"), {"email": "mario@ejemplo.com", "password": CLAVE}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_alta_de_personal_rechaza_roles_invalidos_y_datos_malos(self):
        c = cliente_api(self.admin)
        for cambios in [{"rol": "cliente"}, {"rol": "superjefe"}, {}, {"rol": "mesero", "email": "malo"}, {"rol": "mesero", "first_name": "<b>"}]:
            datos = datos_registro(email="nuevo@ejemplo.com")
            datos.update(cambios)
            if cambios == {}:
                datos.pop("rol", None)
            self.assertEqual(c.post(reverse("usuario-list"), datos, format="json").status_code, 400, cambios)
        self.assertFalse(Usuario.objects.filter(email="nuevo@ejemplo.com").exists())

    def test_no_hay_edicion_ni_borrado_de_usuarios(self):
        c = cliente_api(self.admin)
        for metodo in ("put", "patch", "delete"):
            self.assertEqual(getattr(c, metodo)(reverse("usuario-detail", args=[self.cliente.pk])).status_code, 405, metodo)

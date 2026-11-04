"""Matriz de permisos: qué rol puede llamar a cada endpoint.

Los endpoints se leen del esquema OpenAPI: si se agrega uno sin declarar aquí sus permisos, la prueba falla.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.usuarios.models import Rol

from .base import EntornoMixin, cliente_api

VISITANTE = "visitante"
TODOS = {VISITANTE, Rol.CLIENTE, Rol.MESERO, Rol.ADMINISTRADOR}
CON_SESION = {Rol.CLIENTE, Rol.MESERO, Rol.ADMINISTRADOR}
PERSONAL = {Rol.MESERO, Rol.ADMINISTRADOR}
SOLO_ADMIN = {Rol.ADMINISTRADOR}
SOLO_CLIENTE = {Rol.CLIENTE}

# (método, ruta del esquema) -> roles que pueden llamarla
ENDPOINTS = {
    ("GET", "/api/v1/salud/"): TODOS,
    ("POST", "/api/v1/auth/registro/"): TODOS,
    ("POST", "/api/v1/auth/login/"): TODOS,
    ("POST", "/api/v1/auth/logout/"): CON_SESION,
    ("GET", "/api/v1/auth/yo/"): CON_SESION,
    ("PATCH", "/api/v1/auth/yo/"): CON_SESION,
    ("GET", "/api/v1/usuarios/"): SOLO_ADMIN,
    ("POST", "/api/v1/usuarios/"): SOLO_ADMIN,
    ("GET", "/api/v1/usuarios/{id}/"): SOLO_ADMIN,
    ("GET", "/api/v1/categorias/"): TODOS,
    ("POST", "/api/v1/categorias/"): SOLO_ADMIN,
    ("GET", "/api/v1/categorias/{id}/"): TODOS,
    ("PUT", "/api/v1/categorias/{id}/"): SOLO_ADMIN,
    ("PATCH", "/api/v1/categorias/{id}/"): SOLO_ADMIN,
    ("DELETE", "/api/v1/categorias/{id}/"): SOLO_ADMIN,
    ("GET", "/api/v1/platos/"): TODOS,
    ("POST", "/api/v1/platos/"): SOLO_ADMIN,
    ("GET", "/api/v1/platos/destacados/"): TODOS,
    ("GET", "/api/v1/platos/{id}/"): TODOS,
    ("PUT", "/api/v1/platos/{id}/"): SOLO_ADMIN,
    ("PATCH", "/api/v1/platos/{id}/"): SOLO_ADMIN,
    ("DELETE", "/api/v1/platos/{id}/"): SOLO_ADMIN,
    ("POST", "/api/v1/platos/{id}/disponibilidad/"): PERSONAL,
    ("GET", "/api/v1/pedidos/"): CON_SESION,
    ("POST", "/api/v1/pedidos/"): CON_SESION,
    ("GET", "/api/v1/pedidos/{id}/"): CON_SESION,
    ("POST", "/api/v1/pedidos/{id}/avanzar/"): PERSONAL,
    ("POST", "/api/v1/pedidos/{id}/cancelar/"): CON_SESION,
    ("GET", "/api/v1/reservas/"): CON_SESION,
    ("POST", "/api/v1/reservas/"): SOLO_CLIENTE,
    ("GET", "/api/v1/reservas/{id}/"): CON_SESION,
    ("POST", "/api/v1/reservas/{id}/confirmar/"): PERSONAL,
    ("POST", "/api/v1/reservas/{id}/completar/"): PERSONAL,
    ("POST", "/api/v1/reservas/{id}/cancelar/"): CON_SESION,
    ("GET", "/api/v1/caja/resumen/"): PERSONAL,
    ("GET", "/api/v1/caja/facturas/"): SOLO_ADMIN,
    ("GET", "/api/v1/caja/facturas/{id}/"): CON_SESION,
    ("GET", "/api/v1/caja/cierres/"): SOLO_ADMIN,
    ("POST", "/api/v1/caja/cierres/"): SOLO_ADMIN,
    ("GET", "/api/v1/caja/cierres/{id}/"): SOLO_ADMIN,
    ("GET", "/api/v1/caja/reportes/ventas/"): SOLO_ADMIN,
}
METODOS_HTTP = {"get", "post", "put", "patch", "delete"}


def endpoints_del_esquema():
    esquema = APIClient().get(reverse("esquema"), {"format": "json"}).json()
    return {(metodo.upper(), ruta) for ruta, operaciones in esquema["paths"].items() for metodo in operaciones if metodo in METODOS_HTTP}


class MatrizDeAccesoTests(EntornoMixin, TestCase):
    def navegador(self, rol):
        usuario = {Rol.CLIENTE: self.cliente, Rol.MESERO: self.mesero, Rol.ADMINISTRADOR: self.admin}.get(rol)
        return cliente_api(usuario)

    def test_todo_endpoint_de_la_api_esta_declarado_en_la_matriz(self):
        del_esquema = endpoints_del_esquema()
        self.assertEqual(del_esquema - set(ENDPOINTS), set(), "Hay endpoints sin declarar en la matriz de acceso")
        self.assertEqual(set(ENDPOINTS) - del_esquema, set(), "La matriz declara endpoints que ya no existen")

    def test_cada_rol_solo_llega_a_lo_que_le_corresponde(self):
        for (metodo, ruta), permitidos in ENDPOINTS.items():
            url = ruta.replace("{id}", "999999")
            for rol in TODOS:
                with self.subTest(endpoint=f"{metodo} {ruta}", rol=rol):
                    r = getattr(self.navegador(rol), metodo.lower())(url, {}, format="json")
                    self.assertNotEqual(r.status_code, 500)
                    if rol in permitidos:
                        # autorizado: la petición vacía o el id inexistente dan 200/201/204/400/404/405/409, nunca 401 ni 403
                        self.assertNotIn(r.status_code, (401, 403))
                    elif rol == VISITANTE:
                        self.assertEqual(r.status_code, 401)
                    else:
                        self.assertEqual(r.status_code, 403)

    def test_las_rutas_protegidas_piden_credenciales_con_www_authenticate(self):
        for (metodo, ruta), permitidos in ENDPOINTS.items():
            if VISITANTE in permitidos:
                continue
            r = getattr(APIClient(), metodo.lower())(ruta.replace("{id}", "1"), {}, format="json")
            self.assertEqual((r.status_code, r["WWW-Authenticate"]), (401, "Token"), f"{metodo} {ruta}")

    def test_un_usuario_desactivado_pierde_el_acceso_aunque_conserve_el_token(self):
        cliente = cliente_api(self.mesero)
        self.mesero.is_active = False
        self.mesero.save()
        self.assertEqual(cliente.get("/api/v1/caja/resumen/").status_code, 401)

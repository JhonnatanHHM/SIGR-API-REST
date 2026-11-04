"""Barrido de seguridad: entradas hostiles en todos los filtros y cuerpos de la API.

Regla general: ninguna carga puede provocar un error del servidor (5xx).
- Parámetros y campos estrictos (números, fechas, horas, elecciones, correos): se rechazan con 400 y no se guarda nada.
- Texto libre (notas, nombres de platos): puede ser texto válido y guardarse, pero siempre viaja como parámetro (nunca como SQL).
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.caja.models import CierreCaja, Factura
from apps.menu.models import Categoria, Plato
from apps.pedidos.models import Pedido
from apps.reservas.models import Reserva
from apps.usuarios.models import Usuario

from .base import CLAVE, EntornoMixin, cliente_api

CARGAS = [
    "' OR 1=1 --",
    "'; DROP TABLE usuarios_usuario; --",
    "1 UNION SELECT NULL, password FROM usuarios_usuario",
    "<script>alert(1)</script>",
    "\"><img src=x onerror=alert(1)>",
    "../../etc/passwd",
    "{{7*7}}",
    "${7*7}",
    "%00",
    "%",
    "A" * 5000,
    "-1",
    "1e999",
]

# (ruta, parámetros estrictos que siempre responden 400, parámetros de texto que pueden ser 200 o 400)
BUSCADORES = [
    ("/api/v1/usuarios/", ["rol"], ["q"]),
    ("/api/v1/platos/", ["categoria", "disponible"], ["q"]),
    ("/api/v1/pedidos/", ["estado", "mesa"], []),
    ("/api/v1/reservas/", ["estado", "fecha", "mesa"], []),
    ("/api/v1/caja/reportes/ventas/", ["desde", "hasta"], []),
]


def totales():
    return (Usuario.objects.count(), Categoria.objects.count(), Plato.objects.count(), Pedido.objects.count(),
            Reserva.objects.count(), Factura.objects.count(), CierreCaja.objects.count())


def tablas_intactas(prueba):
    for modelo in (Usuario, Categoria, Plato, Pedido, Reserva, Factura, CierreCaja):
        prueba.assertGreaterEqual(modelo.objects.count(), 0)
    prueba.assertTrue(Usuario.objects.filter(email="adm@ejemplo.com").exists())


class BarridoDeFiltrosTests(EntornoMixin, TestCase):
    def test_los_filtros_resisten_cargas_hostiles(self):
        c = cliente_api(self.admin)
        for ruta, estrictos, texto in BUSCADORES:
            for parametro in estrictos:
                for carga in CARGAS:
                    with self.subTest(ruta=ruta, parametro=parametro, carga=carga[:25]):
                        self.assertEqual(c.get(ruta, {parametro: carga}).status_code, 400)
            for parametro in texto:
                for carga in CARGAS:
                    with self.subTest(ruta=ruta, parametro=parametro, carga=carga[:25]):
                        r = c.get(ruta, {parametro: carga})
                        self.assertIn(r.status_code, (200, 400))
                        self.assertNotIn("<script>alert(1)</script>", r.content.decode().replace("\\u003c", "<")) if r.status_code == 200 else None
        tablas_intactas(self)

    def test_un_filtro_invalido_no_devuelve_todo_el_listado(self):
        r = cliente_api(self.admin).get("/api/v1/usuarios/", {"q": "' OR 1=1 --"})
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("results", r.json())
        self.assertEqual(APIClient().get("/api/v1/platos/", {"q": "' OR 1=1 --"}).status_code, 400)

    def test_todos_los_parametros_juntos(self):
        c = cliente_api(self.admin)
        for ruta, estrictos, texto in BUSCADORES:
            for carga in CARGAS:
                self.assertLess(c.get(ruta, {p: carga for p in estrictos + texto}).status_code, 500, (ruta, carga[:25]))
        tablas_intactas(self)


class BarridoDeCuerposTests(EntornoMixin, TestCase):
    def test_el_registro_rechaza_cargas_hostiles_en_todos_sus_campos(self):
        antes = Usuario.objects.count()
        base = {"first_name": "Ana", "last_name": "Pérez", "email": "ana@ejemplo.com", "telefono": "3001234567",
                "password": CLAVE, "password_confirmacion": CLAVE}
        for carga in CARGAS:
            for campo in ("first_name", "last_name", "email", "telefono"):
                with self.subTest(campo=campo, carga=carga[:25]):
                    r = APIClient().post("/api/v1/auth/registro/", {**base, campo: carga}, format="json")
                    self.assertEqual(r.status_code, 400)
        self.assertEqual(Usuario.objects.count(), antes)

    def test_el_login_con_cargas_hostiles_no_entra_ni_falla(self):
        for carga in CARGAS:
            r = APIClient().post("/api/v1/auth/login/", {"email": carga, "password": carga}, format="json")
            self.assertIn(r.status_code, (400, 401))
            self.assertNotIn("token", r.json())

    def test_pedidos_con_mesa_cantidad_o_plato_hostiles_nunca_se_guardan(self):
        c = cliente_api(self.cliente)
        plato = Plato.objects.first()
        for carga in CARGAS:
            for datos in ({"mesa": carga, "items": [{"plato": plato.pk, "cantidad": 1}]},
                          {"mesa": 4, "items": [{"plato": plato.pk, "cantidad": carga}]},
                          {"mesa": 4, "items": [{"plato": carga, "cantidad": 1}]}):
                with self.subTest(datos=str(datos)[:60]):
                    self.assertEqual(c.post("/api/v1/pedidos/", datos, format="json").status_code, 400)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_notas_de_pedido_hostiles_no_rompen_nada(self):
        c = cliente_api(self.cliente)
        plato = Plato.objects.first()
        for carga in CARGAS:
            r = c.post("/api/v1/pedidos/", {"mesa": 4, "notas": carga, "items": [{"plato": plato.pk, "cantidad": 1}]}, format="json")
            self.assertIn(r.status_code, (201, 400), carga[:25])
        self.assertEqual(Pedido.objects.filter(notas__contains="<").count(), 0)      # ni < ni > se aceptan
        tablas_intactas(self)

    def test_reservas_con_fecha_hora_personas_o_mesa_hostiles_nunca_se_guardan(self):
        c = cliente_api(self.cliente)
        base = {"fecha": "2026-11-12", "hora": "13:00", "personas": 2, "mesa": 3}
        for carga in CARGAS:
            for campo in base:
                with self.subTest(campo=campo, carga=carga[:25]):
                    self.assertEqual(c.post("/api/v1/reservas/", {**base, campo: carga}, format="json").status_code, 400)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_formularios_del_administrador_con_campos_estrictos_hostiles_nunca_guardan(self):
        c = cliente_api(self.admin)
        categoria = Categoria.objects.first()
        casos = [
            ("/api/v1/categorias/", {"nombre": "Nueva", "orden": 1}, "orden", Categoria),
            ("/api/v1/platos/", {"categoria": categoria.pk, "nombre": "Nuevo", "precio": "1000"}, "precio", Plato),
            ("/api/v1/platos/", {"categoria": categoria.pk, "nombre": "Nuevo", "precio": "1000"}, "categoria", Plato),
            ("/api/v1/caja/cierres/", {"fecha": "2026-11-10", "efectivo_contado": "1"}, "efectivo_contado", CierreCaja),
            ("/api/v1/caja/cierres/", {"fecha": "2026-11-10", "efectivo_contado": "1"}, "fecha", CierreCaja),
            ("/api/v1/usuarios/", {"first_name": "Mario", "last_name": "Mesa", "email": "m@ejemplo.com", "rol": "mesero",
                                    "password": CLAVE, "password_confirmacion": CLAVE}, "email", Usuario),
            ("/api/v1/usuarios/", {"first_name": "Mario", "last_name": "Mesa", "email": "m@ejemplo.com", "rol": "mesero",
                                    "password": CLAVE, "password_confirmacion": CLAVE}, "rol", Usuario),
        ]
        for ruta, base, campo, modelo in casos:
            antes = modelo.objects.count()
            for carga in CARGAS:
                with self.subTest(ruta=ruta, campo=campo, carga=carga[:25]):
                    self.assertEqual(c.post(ruta, {**base, campo: carga}, format="json").status_code, 400)
            self.assertEqual(modelo.objects.count(), antes, (ruta, campo))

    def test_nombres_libres_del_administrador_no_rompen_nada(self):
        c = cliente_api(self.admin)
        for carga in CARGAS:
            for ruta, datos in [
                ("/api/v1/categorias/", {"nombre": carga, "descripcion": carga, "orden": 1}),
                ("/api/v1/caja/cierres/", {"fecha": "2026-11-10", "efectivo_contado": "1", "observaciones": carga}),
            ]:
                r = c.post(ruta, datos, format="json")
                self.assertIn(r.status_code, (201, 400, 409), (ruta, carga[:25]))
        tablas_intactas(self)

    def test_tipos_de_contenido_no_soportados_responden_415(self):
        for ruta in ("/api/v1/auth/registro/", "/api/v1/auth/login/"):
            self.assertEqual(APIClient().post(ruta, "<a/>", content_type="application/xml").status_code, 415)

    def test_json_malformado_responde_400(self):
        r = APIClient().post("/api/v1/auth/login/", "{no es json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_cuerpos_json_con_estructura_inesperada_no_provocan_errores_del_servidor(self):
        c = cliente_api(self.admin)
        for cuerpo in ([], [1, 2], "texto", 5, None):
            for ruta in ("/api/v1/auth/login/", "/api/v1/pedidos/", "/api/v1/platos/", "/api/v1/caja/cierres/", "/api/v1/usuarios/"):
                r = c.post(ruta, cuerpo, format="json")
                self.assertLess(r.status_code, 500, (ruta, cuerpo))

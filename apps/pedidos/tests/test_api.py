from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.menu.models import Plato
from apps.pedidos.models import Estado, Pedido
from apps.pedidos.services import crear_pedido

from .base import DatosPedidosMixin, cliente_api


class CrearPedidoTests(DatosPedidosMixin, TestCase):
    def test_sin_credenciales_responde_401(self):
        for metodo, url in (("get", reverse("pedido-list")), ("post", reverse("pedido-list"))):
            self.assertEqual(getattr(cliente_api(), metodo)(url).status_code, 401)

    def test_cliente_crea_su_pedido_con_total_y_location(self):
        r = cliente_api(self.cliente).post(reverse("pedido-list"), self.datos(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertEqual(r["Location"], f"/api/v1/pedidos/{cuerpo['id']}/")
        self.assertEqual((cuerpo["estado"], cuerpo["mesa"], cuerpo["total"]), ("pendiente", 5, "65500.50"))
        self.assertEqual(cuerpo["cliente"], self.cliente.pk)
        self.assertEqual(cuerpo["siguiente_estado"], "en_preparacion")
        self.assertTrue(cuerpo["puede_cancelarse"])
        self.assertEqual([(i["plato_nombre"], i["cantidad"], i["precio_unitario"], i["subtotal"]) for i in cuerpo["items"]],
                         [("Pasta alfredo", 2, "28000.00", "56000.00"), ("Sopa", 1, "9500.50", "9500.50")])

    def test_el_mesero_registra_pedido_de_mesa_sin_cliente(self):
        r = cliente_api(self.mesero).post(reverse("pedido-list"), self.datos(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["cliente"])
        self.assertEqual(r.json()["creado_por"], self.mesero.pk)
        self.assertIsNone(r.json()["cliente_nombre"])

    def test_pedido_invalido_no_se_guarda(self):
        c = cliente_api(self.cliente)
        malos = [self.datos(mesa=0), self.datos(mesa="abc"), self.datos(notas="<script>"), self.datos(items=[]),
                 self.datos(items=[{"plato": self.pasta.pk, "cantidad": -3}]), self.datos(items=[{"plato": self.agotado.pk, "cantidad": 1}]),
                 self.datos(items=[{"plato": self.pasta.pk, "cantidad": 1}, {"plato": self.pasta.pk, "cantidad": 1}])]
        for datos in malos:
            self.assertEqual(c.post(reverse("pedido-list"), datos, format="json").status_code, 400, datos)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_el_precio_siempre_viene_de_la_base(self):
        datos = self.datos(precio=1, total=1)
        datos["items"][0]["precio_unitario"] = 1
        r = cliente_api(self.cliente).post(reverse("pedido-list"), datos, format="json")
        self.assertEqual(r.json()["items"][0]["precio_unitario"], "28000.00")

    def test_el_cliente_y_el_estado_no_se_aceptan_de_la_peticion(self):
        r = cliente_api(self.cliente).post(reverse("pedido-list"), self.datos(cliente=self.otro_cliente.pk, estado="cerrado"), format="json")
        self.assertEqual((r.json()["cliente"], r.json()["estado"]), (self.cliente.pk, "pendiente"))

    def test_cuerpo_con_tipos_incorrectos_responde_400_sin_error_del_servidor(self):
        c = cliente_api(self.cliente)
        for cuerpo in ({}, {"mesa": None, "items": None}, {"mesa": [1], "items": "x"}, {"items": [{"plato": {"a": 1}, "cantidad": []}]}):
            self.assertEqual(c.post(reverse("pedido-list"), cuerpo, format="json").status_code, 400, cuerpo)


class VisibilidadTests(DatosPedidosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.mio = crear_pedido(self.cliente, 1, "", [(self.pasta, 1)])
        self.ajeno = crear_pedido(self.otro_cliente, 2, "", [(self.sopa, 1)])

    def ids(self, usuario, **params):
        r = cliente_api(usuario).get(reverse("pedido-list"), params)
        self.assertEqual(r.status_code, 200, r.content)
        return [p["id"] for p in r.json()["results"]]

    def test_cliente_solo_ve_sus_pedidos_y_los_ajenos_responden_404(self):
        self.assertEqual(self.ids(self.cliente), [self.mio.pk])
        c = cliente_api(self.cliente)
        self.assertEqual(c.get(reverse("pedido-detail", args=[self.mio.pk])).status_code, 200)
        self.assertEqual(c.get(reverse("pedido-detail", args=[self.ajeno.pk])).status_code, 404)

    def test_el_personal_ve_todos(self):
        for usuario in (self.mesero, self.admin):
            self.assertEqual(set(self.ids(usuario)), {self.mio.pk, self.ajeno.pk})

    def test_filtros_por_mesa_y_estado(self):
        self.assertEqual(self.ids(self.mesero, mesa=2), [self.ajeno.pk])
        self.assertEqual(self.ids(self.mesero, estado="listo"), [])
        self.assertEqual(len(self.ids(self.mesero, estado="activos")), 2)
        self.ajeno.cancelar()
        self.assertEqual(self.ids(self.mesero, estado="activos"), [self.mio.pk])
        self.assertEqual(self.ids(self.mesero, estado="cancelado"), [self.ajeno.pk])

    def test_filtros_hostiles_responden_400_y_no_tocan_la_base(self):
        c = cliente_api(self.mesero)
        for params in [{"estado": "' OR 1=1 --"}, {"mesa": "1; DROP TABLE pedidos_pedido"}, {"mesa": -1}, {"mesa": 100}, {"estado": "<script>"}]:
            self.assertEqual(c.get(reverse("pedido-list"), params).status_code, 400, params)
        self.assertEqual(Pedido.objects.count(), 2)

    def test_paginacion(self):
        r = cliente_api(self.mesero).get(reverse("pedido-list"), {"page_size": 1}).json()
        self.assertEqual((r["count"], len(r["results"])), (2, 1))
        self.assertIsNotNone(r["next"])

    def test_ids_inexistentes_o_mal_formados(self):
        c = cliente_api(self.mesero)
        self.assertEqual(c.get(reverse("pedido-detail", args=[999999])).status_code, 404)
        self.assertEqual(c.get("/api/v1/pedidos/abc/").status_code, 404)


class CambioDeEstadoTests(DatosPedidosMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pedido = crear_pedido(self.cliente, 4, "", [(self.pasta, 1)])
        self.url = reverse("pedido-avanzar", args=[self.pedido.pk])

    def test_sin_credenciales_401_y_cliente_403(self):
        self.assertEqual(cliente_api().post(self.url).status_code, 401)
        self.assertEqual(cliente_api(self.cliente).post(self.url).status_code, 403)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Estado.PENDIENTE)

    def test_el_personal_recorre_el_flujo_completo(self):
        for esperado in ("en_preparacion", "listo", "servido", "cerrado"):
            r = cliente_api(self.mesero).post(self.url)
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.json()["estado"], esperado)
        self.assertIsNone(r.json()["siguiente_estado"])
        self.assertFalse(r.json()["puede_cancelarse"])

    def test_el_pedido_cerrado_no_avanza_mas(self):
        for _ in range(4):
            self.pedido.avanzar()
        r = cliente_api(self.admin).post(self.url)
        self.assertEqual(r.status_code, 409)
        self.assertIn("estado final", r.json()["detail"])

    def test_pantalla_desactualizada_responde_409_y_no_salta_pasos(self):
        cliente_api(self.mesero).post(self.url, {"desde": "pendiente"}, format="json")      # pendiente -> en_preparacion
        r = cliente_api(self.admin).post(self.url, {"desde": "pendiente"}, format="json")    # segundo clic con la pantalla vieja
        self.assertEqual(r.status_code, 409)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, Estado.EN_PREPARACION)

    def test_desde_correcto_avanza_y_desde_invalido_responde_400(self):
        self.assertEqual(cliente_api(self.mesero).post(self.url, {"desde": "pendiente"}, format="json").status_code, 200)
        for malo in ("volando", 5, ["x"], ""):
            self.assertEqual(cliente_api(self.mesero).post(self.url, {"desde": malo}, format="json").status_code, 400, malo)

    def test_avanzar_no_acepta_get_ni_ids_inexistentes(self):
        self.assertEqual(cliente_api(self.mesero).get(self.url).status_code, 405)
        self.assertEqual(cliente_api(self.mesero).post(reverse("pedido-avanzar", args=[999999])).status_code, 404)

    def test_el_cliente_cancela_su_pedido_pendiente(self):
        r = cliente_api(self.cliente).post(reverse("pedido-cancelar", args=[self.pedido.pk]))
        self.assertEqual((r.status_code, r.json()["estado"]), (200, "cancelado"))

    def test_no_se_cancela_un_pedido_que_ya_avanzo_ni_uno_ya_cancelado(self):
        self.pedido.avanzar()
        url = reverse("pedido-cancelar", args=[self.pedido.pk])
        self.assertEqual(cliente_api(self.cliente).post(url).status_code, 409)
        otro = crear_pedido(self.cliente, 4, "", [(self.sopa, 1)])
        otro.cancelar()
        self.assertEqual(cliente_api(self.cliente).post(reverse("pedido-cancelar", args=[otro.pk])).status_code, 409)

    def test_un_cliente_no_cancela_el_pedido_de_otro(self):
        ajeno = crear_pedido(self.otro_cliente, 6, "", [(self.sopa, 1)])
        self.assertEqual(cliente_api(self.cliente).post(reverse("pedido-cancelar", args=[ajeno.pk])).status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.estado, Estado.PENDIENTE)

    def test_el_personal_cancela_cualquier_pedido_pendiente(self):
        r = cliente_api(self.mesero).post(reverse("pedido-cancelar", args=[self.pedido.pk]))
        self.assertEqual(r.json()["estado"], "cancelado")

    def test_cancelar_no_acepta_get(self):
        self.assertEqual(cliente_api(self.cliente).get(reverse("pedido-cancelar", args=[self.pedido.pk])).status_code, 405)


class PlatoConPedidosTests(DatosPedidosMixin, TestCase):
    def test_no_se_elimina_un_plato_con_pedidos(self):
        crear_pedido(self.cliente, 1, "", [(self.pasta, 1)])
        r = cliente_api(self.admin).delete(reverse("plato-detail", args=[self.pasta.pk]))
        self.assertEqual(r.status_code, 409)
        self.assertIn("pedidos asociados", r.json()["detail"])
        self.assertTrue(Plato.objects.filter(pk=self.pasta.pk).exists())

    def test_cambiar_el_precio_del_plato_no_altera_pedidos_anteriores(self):
        pedido = crear_pedido(self.cliente, 1, "", [(self.pasta, 2)])
        self.pasta.precio = Decimal("99999")
        self.pasta.save()
        r = cliente_api(self.cliente).get(reverse("pedido-detail", args=[pedido.pk]))
        self.assertEqual((r.json()["total"], r.json()["items"][0]["precio_unitario"]), ("56000.00", "28000.00"))

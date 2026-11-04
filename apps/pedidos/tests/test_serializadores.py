from django.test import TestCase

from apps.pedidos.serializers import CambioEstadoSerializer, FiltroPedidoSerializer, PedidoCrearSerializer

from .base import DatosPedidosMixin


def errores(serializador):
    serializador.is_valid()
    return serializador.errors


class PedidoCrearSerializerTests(DatosPedidosMixin, TestCase):
    def test_pedido_valido_con_notas_normalizadas(self):
        s = PedidoCrearSerializer(data=self.datos(notas="  Sin   cebolla "))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["mesa"], 5)
        self.assertEqual(s.validated_data["notas"], "Sin cebolla")
        self.assertEqual([(i["plato"].nombre, i["cantidad"]) for i in s.validated_data["items"]], [("Pasta alfredo", 2), ("Sopa", 1)])

    def test_mesa_invalida(self):
        for mala in [0, 100, -1, "abc", 1.5, "", None, "5; DROP TABLE pedidos_pedido", "' OR 1=1", [5], {"a": 1}, True]:
            with self.subTest(mesa=mala):
                self.assertIn("mesa", errores(PedidoCrearSerializer(data=self.datos(mesa=mala))))

    def test_cantidades_invalidas(self):
        for mala in [0, -1, 51, "abc", 1.5, "1e1", None, "2; DROP TABLE x", [2], True]:
            with self.subTest(cantidad=mala):
                datos = self.datos(items=[{"plato": self.pasta.pk, "cantidad": mala}])
                self.assertIn("items", errores(PedidoCrearSerializer(data=datos)))

    def test_exige_al_menos_un_plato(self):
        self.assertIn("items", errores(PedidoCrearSerializer(data=self.datos(items=[]))))
        self.assertIn("items", errores(PedidoCrearSerializer(data={"mesa": 5})))

    def test_el_campo_items_debe_ser_una_lista_de_objetos(self):
        for malo in ["texto", 5, {"plato": 1}, [1, 2], None, [None], [[]]]:
            with self.subTest(items=malo):
                self.assertIn("items", errores(PedidoCrearSerializer(data=self.datos(items=malo))))

    def test_platos_inexistentes_agotados_u_ocultos_se_rechazan(self):
        for plato in (self.agotado.pk, self.secreto.pk, 99999, "abc", None, "1 OR 1=1"):
            with self.subTest(plato=plato):
                datos = self.datos(items=[{"plato": plato, "cantidad": 1}])
                self.assertIn("items", errores(PedidoCrearSerializer(data=datos)))

    def test_un_plato_no_puede_repetirse(self):
        datos = self.datos(items=[{"plato": self.pasta.pk, "cantidad": 1}, {"plato": self.pasta.pk, "cantidad": 2}])
        self.assertIn("items", errores(PedidoCrearSerializer(data=datos)))

    def test_el_precio_y_otros_datos_del_cliente_se_ignoran(self):
        datos = self.datos(precio=1, estado="cerrado", cliente=self.otro_cliente.pk, total=1)
        datos["items"][0]["precio_unitario"] = 1
        s = PedidoCrearSerializer(data=datos)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(set(s.validated_data), {"mesa", "notas", "items"})
        self.assertEqual(set(s.validated_data["items"][0]), {"plato", "cantidad"})

    def test_notas_peligrosas(self):
        self.assertIn("notas", errores(PedidoCrearSerializer(data=self.datos(notas="<script>alert(1)</script>"))))
        self.assertIn("notas", errores(PedidoCrearSerializer(data=self.datos(notas="x" * 201))))


class OtrosSerializadoresTests(TestCase):
    def test_filtro_valido_e_invalido(self):
        self.assertTrue(FiltroPedidoSerializer(data={"estado": "activos", "mesa": 7}).is_valid())
        self.assertTrue(FiltroPedidoSerializer(data={"estado": "en_preparacion"}).is_valid())
        for datos in [{"estado": "hackeado"}, {"estado": "' OR 1=1"}, {"mesa": 0}, {"mesa": 100}, {"mesa": "x"}]:
            with self.subTest(datos=datos):
                self.assertFalse(FiltroPedidoSerializer(data=datos).is_valid())

    def test_cambio_de_estado_solo_acepta_estados_conocidos(self):
        self.assertTrue(CambioEstadoSerializer(data={"desde": "pendiente"}).is_valid())
        self.assertTrue(CambioEstadoSerializer(data={}).is_valid())
        self.assertFalse(CambioEstadoSerializer(data={"desde": "volando"}).is_valid())

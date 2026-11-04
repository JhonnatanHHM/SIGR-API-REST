from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.pedidos.models import Estado, ItemPedido, Pedido
from apps.pedidos.services import crear_pedido

from .base import DatosPedidosMixin


class PedidoModeloTests(DatosPedidosMixin, TestCase):
    def nuevo(self, usuario=None):
        return crear_pedido(usuario or self.mesero, 3, "", [(self.pasta, 2), (self.sopa, 1)])

    def test_total_suma_subtotales(self):
        self.assertEqual(self.nuevo().total, Decimal("28000") * 2 + Decimal("9500.50"))

    def test_precio_queda_congelado_aunque_cambie_el_plato(self):
        pedido = self.nuevo()
        self.pasta.precio = Decimal("99999")
        self.pasta.save()
        self.assertEqual(Pedido.objects.get(pk=pedido.pk).items.get(plato=self.pasta).precio_unitario, Decimal("28000"))

    def test_flujo_completo_de_estados(self):
        pedido = self.nuevo()
        esperados = [Estado.EN_PREPARACION, Estado.LISTO, Estado.SERVIDO, Estado.CERRADO]
        for estado in esperados:
            pedido.avanzar()
            self.assertEqual(pedido.estado, estado)
        self.assertIsNone(pedido.siguiente_estado)
        with self.assertRaises(ValueError):
            pedido.avanzar()

    def test_solo_se_cancela_si_esta_pendiente(self):
        pedido = self.nuevo()
        pedido.avanzar()
        with self.assertRaises(ValueError):
            pedido.cancelar()
        otro = self.nuevo()
        otro.cancelar()
        self.assertEqual(otro.estado, Estado.CANCELADO)
        with self.assertRaises(ValueError):
            otro.avanzar()

    def test_pedido_de_cliente_queda_asociado_y_el_del_personal_no(self):
        self.assertEqual(self.nuevo(self.cliente).cliente, self.cliente)
        self.assertIsNone(self.nuevo(self.mesero).cliente)

    def test_validaciones_de_mesa_y_cantidad(self):
        for mesa in (0, 100):
            with self.assertRaises(ValidationError):
                Pedido(creado_por=self.mesero, mesa=mesa).full_clean()
        pedido = self.nuevo()
        for cantidad in (0, 51):
            with self.assertRaises(ValidationError):
                ItemPedido(pedido=pedido, plato=self.agotado, cantidad=cantidad, precio_unitario=1).full_clean()

    def test_un_plato_no_se_repite_en_el_mismo_pedido(self):
        pedido = self.nuevo()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ItemPedido.objects.create(pedido=pedido, plato=self.pasta, cantidad=1, precio_unitario=1)

    def test_pasos_de_la_linea_de_tiempo(self):
        pedido = self.nuevo()
        pedido.avanzar()
        pasos = pedido.pasos()
        self.assertEqual([p["completado"] for p in pasos], [True, True, False, False, False])
        self.assertEqual([p["etiqueta"] for p in pasos if p["actual"]], ["En preparación"])

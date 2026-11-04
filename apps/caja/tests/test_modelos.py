from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.caja.models import CierreCaja, Factura
from apps.caja.services import (
    CajaCerrada, caja_cerrada, cerrar_caja, emitir_factura, pedidos_activos_del_dia, platos_mas_vendidos,
    totales_del_rango, ventas_del_dia, ventas_por_dia,
)
from apps.pedidos.services import crear_pedido

from .base import HOY, DatosCajaMixin


class FacturaTests(DatosCajaMixin, TestCase):
    def test_numero_consecutivo_con_formato(self):
        f1, f2 = self.pedido_cerrado(), self.pedido_cerrado()
        self.assertEqual(f1.numero, f"F-{f1.pk:06d}")
        self.assertNotEqual(f1.numero, f2.numero)

    def test_total_queda_congelado(self):
        factura = self.pedido_cerrado()
        self.assertEqual(factura.total, Decimal("28000") * 2 + Decimal("9500.50"))
        self.pasta.precio = Decimal("1")
        self.pasta.save()
        factura.refresh_from_db()
        self.assertEqual(factura.total, Decimal("65500.50"))

    def test_una_sola_factura_por_pedido(self):
        factura = self.pedido_cerrado()
        self.assertEqual(emitir_factura(factura.pedido, self.admin).pk, factura.pk)
        self.assertEqual(Factura.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Factura.objects.create(pedido=factura.pedido, total=1, emitida_por=self.admin)

    def test_no_se_factura_con_la_caja_cerrada(self):
        cerrar_caja(HOY, Decimal("0"), "", self.admin)
        pedido = crear_pedido(self.cliente, 1, "", [(self.pasta, 1)])
        with self.assertRaises(CajaCerrada):
            emitir_factura(pedido, self.mesero)


class CierreCajaModeloTests(DatosCajaMixin, TestCase):
    def test_diferencia_y_resultado(self):
        self.pedido_cerrado()                                    # 65.500,50 en ventas
        cierre = cerrar_caja(HOY, Decimal("65500.50"), "", self.admin)
        self.assertEqual((cierre.numero_facturas, cierre.diferencia, cierre.resultado), (1, Decimal("0"), "Cuadrado"))

    def test_sobrante_y_faltante(self):
        self.pedido_cerrado()
        sobrante = cerrar_caja(date(2026, 11, 10), Decimal("70000"), "", self.admin)
        self.assertEqual((sobrante.diferencia, sobrante.resultado), (Decimal("4499.50"), "Sobrante"))
        faltante = cerrar_caja(date(2026, 11, 9), Decimal("10"), "", self.admin)    # sin ventas ese día
        self.assertEqual((faltante.total_ventas, faltante.resultado), (Decimal("0"), "Sobrante"))

    def test_un_dia_no_se_cierra_dos_veces(self):
        cerrar_caja(HOY, Decimal("0"), "", self.admin)
        with self.assertRaises(IntegrityError), transaction.atomic():
            cerrar_caja(HOY, Decimal("0"), "", self.admin)
        self.assertTrue(caja_cerrada(HOY))

    def test_un_cierre_no_se_modifica_ni_se_elimina(self):
        cierre = cerrar_caja(HOY, Decimal("5"), "", self.admin)
        cierre.efectivo_contado = Decimal("999")
        with self.assertRaises(ValueError):
            cierre.save()
        with self.assertRaises(ValueError):
            cierre.delete()
        self.assertEqual(CierreCaja.objects.get().efectivo_contado, Decimal("5"))


class ServiciosDeReporteTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pedido_cerrado(dia=8)                                       # 65.500,50
        self.pedido_cerrado(dia=9, items=[(self.sopa, 3)])               # 28.501,50
        self.pedido_cerrado(dia=9, items=[(self.pasta, 1)])              # 28.000
        self.pedido_cerrado()                                            # hoy: 65.500,50

    def test_ventas_del_dia(self):
        self.assertEqual(ventas_del_dia(HOY), (Decimal("65500.50"), 1))
        self.assertEqual(ventas_del_dia(date(2026, 11, 9)), (Decimal("56501.50"), 2))
        self.assertEqual(ventas_del_dia(date(2026, 11, 1)), (Decimal("0"), 0))

    def test_ventas_por_dia_y_totales(self):
        dias = ventas_por_dia(date(2026, 11, 8), HOY)
        self.assertEqual([(d["dia"].day, d["facturas"], d["total"]) for d in dias],
                         [(8, 1, Decimal("65500.50")), (9, 2, Decimal("56501.50")), (10, 1, Decimal("65500.50"))])
        self.assertEqual(totales_del_rango(date(2026, 11, 8), HOY), (Decimal("187502.50"), 4))
        self.assertEqual(totales_del_rango(date(2026, 11, 9), date(2026, 11, 9)), (Decimal("56501.50"), 2))

    def test_platos_mas_vendidos(self):
        top = platos_mas_vendidos(date(2026, 11, 8), HOY)
        self.assertEqual([(p["plato__nombre"], p["unidades"]) for p in top], [("Pasta", 5), ("Sopa", 5)])
        self.assertEqual(top[0]["ingresos"], Decimal("140000"))
        self.assertEqual(len(platos_mas_vendidos(date(2026, 11, 8), HOY, limite=1)), 1)

    def test_pedidos_activos_del_dia(self):
        crear_pedido(self.cliente, 1, "", [(self.pasta, 1)])
        self.assertEqual(pedidos_activos_del_dia(HOY), 1)

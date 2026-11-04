from decimal import Decimal

from django.test import TestCase

from apps.caja.serializers import CierreCajaCrearSerializer, RangoFechasSerializer
from apps.caja.services import cerrar_caja
from apps.comun.excepciones import Conflicto
from apps.pedidos.services import crear_pedido

from .base import HOY, DatosCajaMixin


def errores(serializador):
    serializador.is_valid()
    return serializador.errors


def datos(**cambios):
    base = {"fecha": "2026-11-10", "efectivo_contado": "150000", "observaciones": " Todo   en orden "}
    base.update(cambios)
    return base


class CierreCajaCrearSerializerTests(DatosCajaMixin, TestCase):
    def test_cierre_valido_y_normalizado(self):
        s = CierreCajaCrearSerializer(data=datos(efectivo_contado="150000,50"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["efectivo_contado"], Decimal("150000.50"))
        self.assertEqual(s.validated_data["observaciones"], "Todo en orden")

    def test_efectivo_cero_y_hasta_diez_digitos_enteros(self):
        self.assertTrue(CierreCajaCrearSerializer(data=datos(efectivo_contado="0")).is_valid())
        self.assertTrue(CierreCajaCrearSerializer(data=datos(efectivo_contado="9999999999.99")).is_valid())

    def test_efectivo_invalido(self):
        for malo in ["-5", "abc", "1e3", "$100", "10.999", "12 500", "NaN", "Infinity", "12345678901", "", "' OR 1=1 --",
                     "0; DROP TABLE caja_cierrecaja", None, True, [], {}]:
            with self.subTest(efectivo=malo):
                self.assertIn("efectivo_contado", errores(CierreCajaCrearSerializer(data=datos(efectivo_contado=malo))))

    def test_fecha_invalida_o_futura(self):
        for mala in ["11/10/2026", "2026-02-30", "hoy", "", None, "2026-11-11", "2026-11-10' OR '1'='1", 20261110, ["2026-11-10"]]:
            with self.subTest(fecha=mala):
                self.assertIn("fecha", errores(CierreCajaCrearSerializer(data=datos(fecha=mala))))

    def test_fecha_ya_cerrada_es_un_conflicto(self):
        cerrar_caja(HOY, Decimal("0"), "", self.admin)
        with self.assertRaises(Conflicto):
            CierreCajaCrearSerializer(data=datos()).is_valid(raise_exception=True)

    def test_no_cierra_con_pedidos_sin_cerrar(self):
        crear_pedido(self.cliente, 2, "", [(self.pasta, 1)])
        mensaje = str(errores(CierreCajaCrearSerializer(data=datos()))["fecha"])
        self.assertIn("sin cerrar", mensaje)

    def test_observaciones_peligrosas(self):
        self.assertIn("observaciones", errores(CierreCajaCrearSerializer(data=datos(observaciones="<script>x</script>"))))
        self.assertIn("observaciones", errores(CierreCajaCrearSerializer(data=datos(observaciones="x" * 201))))

    def test_campos_calculados_se_ignoran(self):
        s = CierreCajaCrearSerializer(data=datos(total_ventas=1, diferencia=999, cerrado_por=self.mesero.pk))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(set(s.validated_data), {"fecha", "efectivo_contado", "observaciones"})


class RangoFechasSerializerTests(DatosCajaMixin, TestCase):
    def test_rangos_validos(self):
        self.assertTrue(RangoFechasSerializer(data={"desde": "2026-11-01", "hasta": "2026-11-10"}).is_valid())
        self.assertTrue(RangoFechasSerializer(data={"desde": "2026-11-10", "hasta": "2026-11-10"}).is_valid())
        self.assertTrue(RangoFechasSerializer(data={"desde": "2025-11-09", "hasta": "2026-11-10"}).is_valid())     # un año exacto

    def test_rangos_invalidos(self):
        casos = [
            {"desde": "2026-11-10", "hasta": "2026-11-01"},      # al revés
            {"desde": "2026-11-01", "hasta": "2026-11-11"},      # futuro
            {"desde": "2025-01-01", "hasta": "2026-11-10"},      # más de un año
            {"desde": "01/11/2026", "hasta": "2026-11-10"},
            {"desde": "' OR 1=1 --", "hasta": "2026-11-10"},
            {"desde": "2026-11-01", "hasta": ""},
            {"desde": None, "hasta": None},
            {},
        ]
        for caso in casos:
            with self.subTest(caso=caso):
                self.assertFalse(RangoFechasSerializer(data=caso).is_valid())

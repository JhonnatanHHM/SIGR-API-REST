from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers

from apps.comun.excepciones import Conflicto
from apps.reservas.serializers import CambioEstadoReservaSerializer, FiltroReservaSerializer, ReservaCrearSerializer

from .base import DatosReservasMixin


def payload(**cambios):
    base = {"fecha": "2026-11-11", "hora": "13:00", "personas": 4, "mesa": 7, "notas": "Cumpleaños"}
    base.update(cambios)
    return base


def errores(serializador):
    serializador.is_valid()
    return serializador.errors


class ReservaCrearSerializerTests(DatosReservasMixin, TestCase):
    def s(self, **cambios):
        return ReservaCrearSerializer(data=payload(**cambios), context={"cliente": self.cliente})

    def test_reserva_valida(self):
        s = self.s(notas="  Cumpleaños   de Ana ")
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["hora"], time(13, 0))
        self.assertEqual(s.validated_data["notas"], "Cumpleaños de Ana")

    def test_horas_fuera_de_las_franjas(self):
        for mala in ["10:30", "20:30", "21:00", "13:15", "25:00", "13:00:00", "abc", "", None, 13, ["13:00"], "13:00'; DROP TABLE x"]:
            with self.subTest(hora=mala):
                self.assertIn("hora", errores(self.s(hora=mala)))

    def test_formatos_de_fecha_invalidos(self):
        for mala in ["11/11/2026", "2026-02-30", "2026-13-01", "mañana", "", None, 20261111, "2026-11-11; DROP TABLE x", "2026-11-11T13:00:00", ["2026-11-11"]]:
            with self.subTest(fecha=mala):
                self.assertIn("fecha", errores(self.s(fecha=mala)))

    def test_fecha_pasada_o_muy_proxima(self):
        self.assertIn("fecha", errores(self.s(fecha="2026-11-09")))
        self.assertTrue(self.s(fecha="2026-11-10", hora="11:00").is_valid())             # son las 9:00: faltan 2 horas
        mas_tarde = timezone.make_aware(datetime(2026, 11, 10, 10, 30))
        with patch("django.utils.timezone.now", return_value=mas_tarde):
            self.assertIn("fecha", errores(self.s(fecha="2026-11-10", hora="11:00")))     # solo faltan 30 minutos
            self.assertTrue(self.s(fecha="2026-11-10", hora="11:30").is_valid())          # justo 1 hora

    def test_limite_de_anticipacion(self):
        self.assertTrue(self.s(fecha="2026-12-10").is_valid())                            # exactamente 30 días
        self.assertIn("fecha", errores(self.s(fecha="2026-12-11")))                       # 31 días

    def test_personas_y_mesa_invalidas(self):
        for campo, malos in {"personas": [0, 13, -2, "abc", 1.5, "", None, [], True], "mesa": [0, 100, -1, "x", 1.5, "", None, [], True]}.items():
            for malo in malos:
                with self.subTest(campo=campo, valor=malo):
                    self.assertIn(campo, errores(self.s(**{campo: malo})))

    def test_notas_peligrosas(self):
        self.assertIn("notas", errores(self.s(notas="<script>alert(1)</script>")))
        self.assertIn("notas", errores(self.s(notas="x" * 201)))

    def test_campos_obligatorios(self):
        self.assertEqual(set(errores(ReservaCrearSerializer(data={}, context={"cliente": self.cliente}))), {"fecha", "hora", "personas", "mesa"})

    def test_mesa_ocupada_es_un_conflicto(self):
        self.reservar(dia=11, hora=time(13, 0), mesa=7)
        with self.assertRaises(Conflicto):
            self.s(hora="14:00").is_valid(raise_exception=True)
        self.assertTrue(self.s(hora="15:00").is_valid())                                  # borde exacto: termina a las 15:00

    def test_cliente_con_reserva_cruzada_es_un_conflicto(self):
        self.reservar(dia=11, hora=time(13, 0), mesa=1)
        with self.assertRaises(Conflicto):
            self.s(hora="14:00", mesa=9).is_valid(raise_exception=True)

    def test_el_cliente_y_el_estado_enviados_se_ignoran(self):
        s = self.s(cliente=self.otro_cliente.pk, estado="confirmada")
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(set(s.validated_data), {"fecha", "hora", "personas", "mesa", "notas"})


class OtrosSerializadoresTests(TestCase):
    def test_filtros_validos_e_invalidos(self):
        self.assertTrue(FiltroReservaSerializer(data={"estado": "vigentes", "fecha": "2026-11-11", "mesa": 4}).is_valid())
        for datos in [{"estado": "x"}, {"fecha": "11/11/2026"}, {"fecha": "' OR 1=1"}, {"mesa": 0}, {"mesa": "1; DROP TABLE x"}]:
            with self.subTest(datos=datos):
                self.assertFalse(FiltroReservaSerializer(data=datos).is_valid())

    def test_cambio_de_estado(self):
        self.assertTrue(CambioEstadoReservaSerializer(data={"desde": "pendiente"}).is_valid())
        self.assertTrue(CambioEstadoReservaSerializer(data={}).is_valid())
        self.assertFalse(CambioEstadoReservaSerializer(data={"desde": "volando"}).is_valid())

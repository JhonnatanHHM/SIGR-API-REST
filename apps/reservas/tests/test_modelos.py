from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.reservas.models import EstadoReserva, Reserva
from apps.reservas.reglas import franjas
from apps.reservas.services import ReservaNoDisponible, conflictos, crear_reserva

from .base import DatosReservasMixin


class ReservaModeloTests(DatosReservasMixin, TestCase):
    def test_inicio_y_fin_duran_dos_horas(self):
        r = self.reservar(hora=time(13, 30))
        self.assertEqual((r.fin - r.inicio).total_seconds(), 7200)

    def test_flujo_de_estados(self):
        r = self.reservar()
        r.confirmar()
        self.assertEqual(r.estado, EstadoReserva.CONFIRMADA)
        r.completar()
        self.assertEqual(r.estado, EstadoReserva.COMPLETADA)
        for accion in (r.confirmar, r.completar, r.cancelar):
            with self.assertRaises(ValueError):
                accion()

    def test_no_se_completa_una_pendiente_ni_se_confirma_una_cancelada(self):
        r = self.reservar()
        with self.assertRaises(ValueError):
            r.completar()
        r.cancelar()
        with self.assertRaises(ValueError):
            r.confirmar()

    def test_validaciones_de_personas_y_mesa(self):
        for personas in (0, 13):
            with self.assertRaises(ValidationError):
                Reserva(cliente=self.cliente, fecha=self.reservar().fecha, hora=time(12), personas=personas, mesa=1).full_clean()
        for mesa in (0, 100):
            with self.assertRaises(ValidationError):
                Reserva(cliente=self.cliente, fecha=self.reservar().fecha, hora=time(12), personas=2, mesa=mesa).full_clean()

    def test_franjas_de_media_hora_entre_11_y_20(self):
        horas = franjas()
        self.assertEqual((horas[0], horas[-1], len(horas)), (time(11, 0), time(20, 0), 19))


class CrucesTests(DatosReservasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.base = self.reservar(hora=time(13, 0), mesa=4)    # ocupa 13:00 a 15:00

    def ocupada(self, hora, mesa=4, **extra):
        return conflictos(mesa, self.base.fecha, hora, **extra)[0]

    def test_se_cruza_dentro_de_las_dos_horas(self):
        for hora in (time(11, 30), time(12, 0), time(13, 0), time(14, 30)):
            self.assertTrue(self.ocupada(hora), hora)

    def test_borde_exacto_es_valido(self):
        self.assertFalse(self.ocupada(time(11, 0)))     # termina justo a las 13:00
        self.assertFalse(self.ocupada(time(15, 0)))     # empieza justo cuando termina la otra

    def test_otra_mesa_u_otro_dia_no_chocan(self):
        self.assertFalse(self.ocupada(time(13, 0), mesa=5))
        self.assertFalse(conflictos(4, self.base.fecha.replace(day=12), time(13, 0))[0])

    def test_reservas_canceladas_o_completadas_no_bloquean(self):
        self.base.cancelar()
        self.assertFalse(self.ocupada(time(13, 0)))

    def test_se_puede_editar_ignorando_la_propia_reserva(self):
        self.assertFalse(conflictos(4, self.base.fecha, time(13, 0), excluir_pk=self.base.pk)[0])

    def test_cliente_no_puede_tener_dos_reservas_cruzadas(self):
        _, cliente_ocupado = conflictos(9, self.base.fecha, time(14, 0), cliente=self.cliente)
        self.assertTrue(cliente_ocupado)
        _, otro = conflictos(9, self.base.fecha, time(14, 0), cliente=self.otro_cliente)
        self.assertFalse(otro)

    def test_servicio_rechaza_cruces(self):
        nueva = Reserva(cliente=self.otro_cliente, fecha=self.base.fecha, hora=time(14, 0), mesa=4, personas=2)
        with self.assertRaises(ReservaNoDisponible):
            crear_reserva(nueva)
        propia = Reserva(cliente=self.cliente, fecha=self.base.fecha, hora=time(14, 0), mesa=8, personas=2)
        with self.assertRaises(ReservaNoDisponible):
            crear_reserva(propia)
        libre = Reserva(cliente=self.otro_cliente, fecha=self.base.fecha, hora=time(15, 0), mesa=4, personas=2)
        crear_reserva(libre)
        self.assertIsNotNone(libre.pk)

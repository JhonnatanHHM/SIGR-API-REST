from datetime import date, datetime, time
from unittest.mock import patch

from django.utils import timezone

from apps.reservas.models import Reserva
from apps.usuarios.models import Rol, Usuario

CLAVE = "Contr4seña-Muy-Segura!"
HOY = date(2026, 11, 10)
AHORA = timezone.make_aware(datetime(2026, 11, 10, 9, 0))      # el reloj de las pruebas queda fijo


def crear_usuario(email, rol):
    return Usuario.objects.create_user(email, CLAVE, first_name="Nombre", last_name="Apellido", rol=rol)


class DatosReservasMixin:
    def setUp(self):
        parche = patch("django.utils.timezone.now", return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.cliente = crear_usuario("cli@ejemplo.com", Rol.CLIENTE)
        self.otro_cliente = crear_usuario("otro@ejemplo.com", Rol.CLIENTE)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)

    def reservar(self, cliente=None, dia=11, hora=time(13, 0), mesa=4, personas=2, **extra):
        return Reserva.objects.create(
            cliente=cliente or self.cliente, fecha=date(2026, 11, dia), hora=hora, mesa=mesa, personas=personas, **extra
        )

    def datos(self, **cambios):
        base = {"fecha": "2026-11-11", "hora": "13:00", "personas": "4", "mesa": "7", "notas": "Cumpleaños"}
        base.update(cambios)
        return base

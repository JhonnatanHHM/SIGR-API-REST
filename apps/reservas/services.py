from datetime import datetime

from django.db import connection, transaction

from .models import VIGENTES, Reserva
from .reglas import DURACION


class ReservaNoDisponible(Exception):
    """La mesa o el cliente ya tienen una reserva vigente que se cruza con la solicitada."""


def conflictos(mesa, fecha, hora, cliente=None, excluir_pk=None):
    """Devuelve (mesa_ocupada, cliente_ocupado).

    Dos reservas se cruzan si empiezan con menos de DURACION de diferencia; terminar justo cuando
    otra empieza es válido. Solo cuentan las reservas vigentes (pendientes o confirmadas).
    """
    inicio = datetime.combine(fecha, hora)
    cercanas = Reserva.objects.filter(
        fecha=fecha,
        estado__in=VIGENTES,
        hora__gt=(inicio - DURACION).time(),
        hora__lt=(inicio + DURACION).time(),
    )
    if excluir_pk:
        cercanas = cercanas.exclude(pk=excluir_pk)
    mesa_ocupada = cercanas.filter(mesa=mesa).exists()
    cliente_ocupado = bool(cliente) and cercanas.filter(cliente=cliente).exists()
    return mesa_ocupada, cliente_ocupado


def _bloquear(clave_a, clave_b):
    """En PostgreSQL serializa las altas concurrentes sobre la misma mesa/día o cliente/día."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [clave_a, clave_b])


@transaction.atomic
def crear_reserva(reserva):
    """Guarda la reserva si sigue libre; revalida dentro de la transacción para evitar carreras."""
    _bloquear(reserva.mesa, reserva.fecha.toordinal())
    _bloquear(100000 + reserva.cliente_id, reserva.fecha.toordinal())
    mesa_ocupada, cliente_ocupado = conflictos(reserva.mesa, reserva.fecha, reserva.hora, reserva.cliente)
    if mesa_ocupada:
        raise ReservaNoDisponible(
            f"La mesa {reserva.mesa} ya está reservada cerca de las {reserva.hora:%H:%M}. Elige otra mesa u otro horario."
        )
    if cliente_ocupado:
        raise ReservaNoDisponible("Ya tienes una reserva vigente que se cruza con este horario.")
    reserva.save()
    return reserva

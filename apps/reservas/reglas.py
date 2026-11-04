"""Reglas de negocio de las reservas, en un solo lugar."""
from datetime import datetime, time, timedelta

DURACION = timedelta(hours=2)                  # cada reserva ocupa la mesa durante 2 horas
HORA_PRIMERA = time(11, 0)                     # primera franja del día
HORA_ULTIMA = time(20, 0)                      # última franja (termina a las 22:00)
INTERVALO_MINUTOS = 30                         # las reservas se hacen en franjas de media hora
DIAS_MAX_ANTICIPACION = 30
ANTICIPACION_MINIMA = timedelta(hours=1)
PERSONAS_MAX = 12


def franjas():
    """Horas permitidas: de 11:00 a 20:00 cada 30 minutos."""
    actual = datetime.combine(datetime.today(), HORA_PRIMERA)
    ultima = datetime.combine(datetime.today(), HORA_ULTIMA)
    resultado = []
    while actual <= ultima:
        resultado.append(actual.time())
        actual += timedelta(minutes=INTERVALO_MINUTOS)
    return resultado

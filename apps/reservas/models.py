from datetime import datetime

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.comun.validators import MESA_MAX, MESA_MIN, validar_texto_libre

from .reglas import DURACION, PERSONAS_MAX


class EstadoReserva(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    CONFIRMADA = "confirmada", "Confirmada"
    COMPLETADA = "completada", "Completada"
    CANCELADA = "cancelada", "Cancelada"


VIGENTES = (EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA)   # las que ocupan la mesa


class Reserva(models.Model):
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="cliente", on_delete=models.PROTECT, related_name="reservas"
    )
    fecha = models.DateField("fecha")
    hora = models.TimeField("hora")
    personas = models.PositiveSmallIntegerField(
        "personas", validators=[MinValueValidator(1), MaxValueValidator(PERSONAS_MAX)]
    )
    mesa = models.PositiveSmallIntegerField("mesa", validators=[MinValueValidator(MESA_MIN), MaxValueValidator(MESA_MAX)])
    estado = models.CharField("estado", max_length=12, choices=EstadoReserva.choices, default=EstadoReserva.PENDIENTE, db_index=True)
    notas = models.CharField("notas", max_length=200, blank=True, validators=[validar_texto_libre])
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["fecha", "hora"]
        indexes = [models.Index(fields=["mesa", "fecha"])]

    def __str__(self):
        return f"Reserva #{self.pk} · mesa {self.mesa} · {self.fecha:%d/%m/%Y} {self.hora:%H:%M}"

    @property
    def inicio(self):
        return timezone.make_aware(datetime.combine(self.fecha, self.hora))

    @property
    def fin(self):
        return self.inicio + DURACION

    @property
    def puede_confirmarse(self):
        return self.estado == EstadoReserva.PENDIENTE

    @property
    def puede_completarse(self):
        return self.estado == EstadoReserva.CONFIRMADA

    @property
    def puede_cancelarse(self):
        return self.estado in VIGENTES

    def _cambiar(self, permitido, nuevo_estado, mensaje):
        if not permitido:
            raise ValueError(mensaje)
        self.estado = nuevo_estado
        self.save(update_fields=["estado", "actualizado"])

    def confirmar(self):
        self._cambiar(self.puede_confirmarse, EstadoReserva.CONFIRMADA, "Solo se confirma una reserva pendiente.")

    def completar(self):
        self._cambiar(self.puede_completarse, EstadoReserva.COMPLETADA, "Solo se completa una reserva confirmada.")

    def cancelar(self):
        self._cambiar(self.puede_cancelarse, EstadoReserva.CANCELADA, "Solo se cancela una reserva pendiente o confirmada.")

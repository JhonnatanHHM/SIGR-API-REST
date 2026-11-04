from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.comun.validators import MESA_MAX, MESA_MIN, validar_texto_libre
from apps.menu.models import Plato

MAX_CANTIDAD = 50


class Estado(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    EN_PREPARACION = "en_preparacion", "En preparación"
    LISTO = "listo", "Listo"
    SERVIDO = "servido", "Servido"
    CERRADO = "cerrado", "Cerrado"
    CANCELADO = "cancelado", "Cancelado"


# Flujo permitido: cada estado solo puede avanzar al siguiente.
SIGUIENTE = {
    Estado.PENDIENTE: Estado.EN_PREPARACION,
    Estado.EN_PREPARACION: Estado.LISTO,
    Estado.LISTO: Estado.SERVIDO,
    Estado.SERVIDO: Estado.CERRADO,
}
FLUJO = [Estado.PENDIENTE, Estado.EN_PREPARACION, Estado.LISTO, Estado.SERVIDO, Estado.CERRADO]


class Pedido(models.Model):
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="cliente", null=True, blank=True,
        on_delete=models.PROTECT, related_name="pedidos",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="registrado por", on_delete=models.PROTECT, related_name="pedidos_registrados",
    )
    mesa = models.PositiveSmallIntegerField("mesa", validators=[MinValueValidator(MESA_MIN), MaxValueValidator(MESA_MAX)])
    estado = models.CharField("estado", max_length=15, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True)
    notas = models.CharField("notas", max_length=200, blank=True, validators=[validar_texto_libre])
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-creado"]

    def __str__(self):
        return f"Pedido #{self.pk} · mesa {self.mesa}"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), 0)

    @property
    def siguiente_estado(self):
        return SIGUIENTE.get(self.estado)

    @property
    def siguiente_etiqueta(self):
        siguiente = self.siguiente_estado
        return Estado(siguiente).label if siguiente else None

    @property
    def puede_cancelarse(self):
        return self.estado == Estado.PENDIENTE

    @property
    def activo(self):
        return self.estado in SIGUIENTE

    def avanzar(self):
        siguiente = self.siguiente_estado
        if siguiente is None:
            raise ValueError("El pedido ya está en su estado final.")
        self.estado = siguiente
        self.save(update_fields=["estado", "actualizado"])

    def cancelar(self):
        if not self.puede_cancelarse:
            raise ValueError("Solo se puede cancelar un pedido pendiente.")
        self.estado = Estado.CANCELADO
        self.save(update_fields=["estado", "actualizado"])

    def pasos(self):
        """Línea de tiempo del pedido para mostrarla en pantalla."""
        if self.estado == Estado.CANCELADO:
            return [{"etiqueta": "Cancelado", "completado": True, "actual": True}]
        posicion = FLUJO.index(self.estado)
        return [
            {"etiqueta": paso.label, "completado": i <= posicion, "actual": i == posicion}
            for i, paso in enumerate(FLUJO)
        ]


class ItemPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="items")
    plato = models.ForeignKey(Plato, verbose_name="plato", on_delete=models.PROTECT, related_name="items_pedido")
    cantidad = models.PositiveSmallIntegerField(
        "cantidad", validators=[MinValueValidator(1), MaxValueValidator(MAX_CANTIDAD)]
    )
    precio_unitario = models.DecimalField("precio unitario", max_digits=9, decimal_places=2)

    class Meta:
        verbose_name = "ítem de pedido"
        verbose_name_plural = "ítems de pedido"
        ordering = ["plato__nombre"]
        constraints = [
            models.UniqueConstraint(fields=["pedido", "plato"], name="item_unico_por_plato_y_pedido"),
            models.CheckConstraint(
                condition=models.Q(cantidad__gte=1, cantidad__lte=MAX_CANTIDAD), name="item_cantidad_en_rango"
            ),
        ]

    def __str__(self):
        return f"{self.cantidad} × {self.plato}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

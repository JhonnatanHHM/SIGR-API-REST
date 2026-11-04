from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.comun.validators import validar_texto_libre
from apps.pedidos.models import Pedido


class Factura(models.Model):
    """Comprobante de venta: se emite al cerrar un pedido y congela su total."""

    pedido = models.OneToOneField(Pedido, verbose_name="pedido", on_delete=models.PROTECT, related_name="factura")
    total = models.DecimalField("total", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    emitida = models.DateTimeField("emitida", auto_now_add=True, db_index=True)
    emitida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="emitida por", on_delete=models.PROTECT, related_name="facturas_emitidas"
    )

    class Meta:
        verbose_name = "factura"
        verbose_name_plural = "facturas"
        ordering = ["-emitida"]

    def __str__(self):
        return self.numero

    @property
    def numero(self):
        return f"F-{self.pk:06d}"


class CierreCaja(models.Model):
    """Cierre de la caja de un día. Una vez creado no se modifica ni se elimina."""

    fecha = models.DateField(
        "fecha", unique=True, error_messages={"unique": "La caja de esta fecha ya fue cerrada."}
    )
    total_ventas = models.DecimalField("total de ventas", max_digits=14, decimal_places=2)
    numero_facturas = models.PositiveIntegerField("facturas emitidas")
    efectivo_contado = models.DecimalField(
        "efectivo contado", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    diferencia = models.DecimalField("diferencia", max_digits=14, decimal_places=2)
    observaciones = models.CharField("observaciones", max_length=200, blank=True, validators=[validar_texto_libre])
    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="cerrado por", on_delete=models.PROTECT, related_name="cierres_caja"
    )
    cerrado = models.DateTimeField("cerrado el", auto_now_add=True)

    class Meta:
        verbose_name = "cierre de caja"
        verbose_name_plural = "cierres de caja"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Cierre {self.fecha:%d/%m/%Y}"

    @property
    def resultado(self):
        if self.diferencia == 0:
            return "Cuadrado"
        return "Sobrante" if self.diferencia > 0 else "Faltante"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Un cierre de caja no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Un cierre de caja no se puede eliminar.")

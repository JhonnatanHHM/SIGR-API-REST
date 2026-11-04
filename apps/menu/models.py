import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.comun.validators import validar_imagen, validar_nombre_comercial, validar_texto_libre


def ruta_imagen_plato(instancia, nombre_original):
    """Guarda cada foto con un nombre aleatorio: nunca se usa el nombre que envía el navegador."""
    extension = nombre_original.rsplit(".", 1)[-1].lower()
    return f"platos/{uuid.uuid4().hex}.{extension}"


class Categoria(models.Model):
    nombre = models.CharField("nombre", max_length=60, validators=[validar_nombre_comercial])
    descripcion = models.CharField("descripción", max_length=200, blank=True, validators=[validar_texto_libre])
    orden = models.PositiveSmallIntegerField("orden", default=0, validators=[MaxValueValidator(999)])
    activa = models.BooleanField("activa", default=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["orden", "nombre"]
        constraints = [models.UniqueConstraint(Lower("nombre"), name="categoria_nombre_unico_ci")]

    def __str__(self):
        return self.nombre


class Plato(models.Model):
    categoria = models.ForeignKey(Categoria, verbose_name="categoría", on_delete=models.PROTECT, related_name="platos")
    nombre = models.CharField("nombre", max_length=100, validators=[validar_nombre_comercial])
    descripcion = models.CharField("descripción", max_length=500, blank=True, validators=[validar_texto_libre])
    precio = models.DecimalField(
        "precio",
        max_digits=9,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("9999999.99"))],
    )
    disponible = models.BooleanField("disponible", default=True)
    destacado = models.BooleanField("destacado en el inicio", default=False)
    imagen = models.ImageField("foto", upload_to=ruta_imagen_plato, blank=True, validators=[validar_imagen])
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plato"
        verbose_name_plural = "platos"
        ordering = ["categoria__orden", "categoria__nombre", "nombre"]
        constraints = [models.UniqueConstraint(Lower("nombre"), "categoria", name="plato_nombre_unico_por_categoria_ci")]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        anterior = None
        if self.pk:
            anterior = Plato.objects.filter(pk=self.pk).values_list("imagen", flat=True).first()
        super().save(*args, **kwargs)
        if anterior and anterior != self.imagen.name:
            self.imagen.storage.delete(anterior)          # la foto reemplazada o quitada no queda huérfana


@receiver(post_delete, sender=Plato)
def borrar_foto_del_plato(sender, instance, **kwargs):
    if instance.imagen:
        instance.imagen.storage.delete(instance.imagen.name)

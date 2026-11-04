from django.core.validators import RegexValidator
from rest_framework import serializers

from apps.comun.campos import MontoField, TextoField
from apps.comun.validators import limpiar_espacios, validar_imagen, validar_nombre_comercial, validar_texto_libre

from .models import Categoria, Plato

_validar_busqueda = RegexValidator(r"^[\w\s@.+'\-]*$", "La búsqueda contiene caracteres no permitidos.")


class CategoriaSerializer(serializers.ModelSerializer):
    nombre = TextoField(max_length=60, validators=[validar_nombre_comercial])
    descripcion = TextoField(max_length=200, required=False, allow_blank=True, validators=[validar_texto_libre])
    orden = serializers.IntegerField(min_value=0, max_value=999, default=0)
    activa = serializers.BooleanField(default=True)

    class Meta:
        model = Categoria
        fields = ("id", "nombre", "descripcion", "orden", "activa")
        read_only_fields = ("id",)

    def validate_nombre(self, nombre):
        repetidas = Categoria.objects.filter(nombre__iexact=nombre)
        if self.instance is not None:
            repetidas = repetidas.exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise serializers.ValidationError("Ya existe una categoría con este nombre.", code="unique")
        return nombre


class PlatoSerializer(serializers.ModelSerializer):
    categoria = serializers.PrimaryKeyRelatedField(queryset=Categoria.objects.all())
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True)
    nombre = TextoField(max_length=100, validators=[validar_nombre_comercial])
    descripcion = TextoField(max_length=500, required=False, allow_blank=True, validators=[validar_texto_libre])
    precio = MontoField()
    disponible = serializers.BooleanField(default=True)
    destacado = serializers.BooleanField(default=False)
    imagen = serializers.ImageField(required=False, allow_null=True, validators=[validar_imagen])

    class Meta:
        model = Plato
        fields = (
            "id", "categoria", "categoria_nombre", "nombre", "descripcion", "precio", "disponible", "destacado", "imagen",
        )
        read_only_fields = ("id",)

    def validate_categoria(self, categoria):
        actual = self.instance.categoria_id if self.instance is not None else None
        if not categoria.activa and categoria.pk != actual:
            raise serializers.ValidationError("La categoría no existe o está oculta.", code="does_not_exist")
        return categoria

    def validate(self, datos):
        categoria = datos.get("categoria", self.instance.categoria if self.instance else None)
        nombre = datos.get("nombre", self.instance.nombre if self.instance else None)
        if categoria is not None and nombre:
            repetidos = Plato.objects.filter(categoria=categoria, nombre__iexact=nombre)
            if self.instance is not None:
                repetidos = repetidos.exclude(pk=self.instance.pk)
            if repetidos.exists():
                raise serializers.ValidationError({"nombre": "Ya existe un plato con este nombre en la categoría."})
        return datos


class FiltroPlatoSerializer(serializers.Serializer):
    """Filtros del listado de platos; `disponible` solo lo aplica el personal (el público ve únicamente los disponibles)."""

    q = serializers.CharField(required=False, allow_blank=True, max_length=100, validators=[_validar_busqueda])
    categoria = serializers.PrimaryKeyRelatedField(required=False, queryset=Categoria.objects.all())
    disponible = serializers.ChoiceField(required=False, choices=["true", "false"])

    def validate_q(self, valor):
        return limpiar_espacios(valor)

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.comun.campos import TextoField
from apps.comun.validators import MESA_MAX, MESA_MIN, validar_texto_libre
from apps.menu.models import Plato

from .models import MAX_CANTIDAD, SIGUIENTE, ItemPedido, Pedido, Estado


def _dinero(valor):
    return f"{valor:.2f}"


class ItemPedidoSerializer(serializers.ModelSerializer):
    plato_nombre = serializers.CharField(source="plato.nombre", read_only=True)
    precio_unitario = serializers.DecimalField(max_digits=9, decimal_places=2, read_only=True)
    subtotal = serializers.SerializerMethodField()

    class Meta:
        model = ItemPedido
        fields = ("id", "plato", "plato_nombre", "cantidad", "precio_unitario", "subtotal")
        read_only_fields = fields

    def get_subtotal(self, item) -> str:
        return _dinero(item.subtotal)


class PedidoSerializer(serializers.ModelSerializer):
    """Pedido completo (solo lectura): ítems con el precio congelado al pedir, total y estado."""

    items = ItemPedidoSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    siguiente_estado = serializers.SerializerMethodField()
    puede_cancelarse = serializers.BooleanField(read_only=True)
    cliente_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()
    factura = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = (
            "id", "mesa", "estado", "estado_etiqueta", "siguiente_estado", "puede_cancelarse", "notas", "cliente",
            "cliente_nombre", "creado_por", "registrado_por_nombre", "items", "total", "factura", "creado", "actualizado",
        )
        read_only_fields = fields

    @extend_schema_field({
        "type": "object", "nullable": True,
        "properties": {"id": {"type": "integer"}, "numero": {"type": "string"}, "total": {"type": "string"}},
    })
    def get_factura(self, pedido):
        factura = getattr(pedido, "factura", None)      # None mientras el pedido no se haya cerrado
        if factura is None:
            return None
        return {"id": factura.pk, "numero": factura.numero, "total": _dinero(factura.total)}

    def get_total(self, pedido) -> str:
        return _dinero(pedido.total)

    def get_siguiente_estado(self, pedido) -> str | None:
        return pedido.siguiente_estado

    def get_cliente_nombre(self, pedido) -> str | None:
        return pedido.cliente.nombre_completo if pedido.cliente_id else None

    def get_registrado_por_nombre(self, pedido) -> str:
        return pedido.creado_por.nombre_completo


class ItemEntradaSerializer(serializers.Serializer):
    plato = serializers.PrimaryKeyRelatedField(queryset=Plato.objects.all())
    cantidad = serializers.IntegerField(min_value=1, max_value=MAX_CANTIDAD)

    def validate_plato(self, plato):
        if not plato.disponible or not plato.categoria.activa:
            raise serializers.ValidationError("El plato no está disponible.", code="no_disponible")
        return plato


class PedidoCrearSerializer(serializers.Serializer):
    """Entrada de un pedido. El precio se toma SIEMPRE de la base de datos; cualquier otro dato enviado se ignora."""

    mesa = serializers.IntegerField(min_value=MESA_MIN, max_value=MESA_MAX)
    notas = TextoField(max_length=200, required=False, allow_blank=True, validators=[validar_texto_libre])
    items = ItemEntradaSerializer(many=True, allow_empty=False, max_length=50, error_messages={"empty": "Agrega al menos un plato al pedido."})

    def validate_items(self, items):
        platos = [item["plato"].pk for item in items]
        if len(platos) != len(set(platos)):
            raise serializers.ValidationError("Cada plato solo puede aparecer una vez en el pedido.")
        return items


class CambioEstadoSerializer(serializers.Serializer):
    """Estado que la persona veía al actuar (opcional): si ya cambió, la API responde 409 en vez de saltarse pasos."""

    desde = serializers.ChoiceField(required=False, choices=Estado.choices)


ESTADOS_FILTRO = [("activos", "Activos")] + list(Estado.choices)


class FiltroPedidoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(required=False, choices=ESTADOS_FILTRO)
    mesa = serializers.IntegerField(required=False, min_value=MESA_MIN, max_value=MESA_MAX)


ESTADOS_ACTIVOS = list(SIGUIENTE)

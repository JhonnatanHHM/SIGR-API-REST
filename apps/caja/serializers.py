from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.comun.campos import MontoField, TextoField
from apps.comun.excepciones import Conflicto
from apps.comun.validators import validar_texto_libre
from apps.pedidos.serializers import PedidoSerializer

from .models import CierreCaja, Factura
from .services import pedidos_activos_del_dia

FORMATO_FECHA = "%Y-%m-%d"
DIAS_MAX_REPORTE = 366


class FacturaSerializer(serializers.ModelSerializer):
    """Factura para listados (solo lectura)."""

    numero = serializers.CharField(read_only=True)
    mesa = serializers.IntegerField(source="pedido.mesa", read_only=True)
    emitida_por_nombre = serializers.CharField(source="emitida_por.nombre_completo", read_only=True)

    class Meta:
        model = Factura
        fields = ("id", "numero", "pedido", "mesa", "total", "emitida", "emitida_por", "emitida_por_nombre")
        read_only_fields = fields


class FacturaDetalleSerializer(FacturaSerializer):
    """Factura con el detalle completo del pedido (el documento que se imprime)."""

    pedido_detalle = PedidoSerializer(source="pedido", read_only=True)

    class Meta(FacturaSerializer.Meta):
        fields = FacturaSerializer.Meta.fields + ("pedido_detalle",)
        read_only_fields = fields


class CierreCajaSerializer(serializers.ModelSerializer):
    resultado = serializers.CharField(read_only=True)
    cerrado_por_nombre = serializers.CharField(source="cerrado_por.nombre_completo", read_only=True)

    class Meta:
        model = CierreCaja
        fields = (
            "id", "fecha", "total_ventas", "numero_facturas", "efectivo_contado", "diferencia", "resultado",
            "observaciones", "cerrado_por", "cerrado_por_nombre", "cerrado",
        )
        read_only_fields = fields


class CierreCajaCrearSerializer(serializers.Serializer):
    """Entrada del cierre de caja. El total de ventas, la diferencia y quién cierra se calculan en el servidor."""

    fecha = serializers.DateField(input_formats=[FORMATO_FECHA])
    efectivo_contado = MontoField(max_digits=12, min_value=Decimal("0"))
    observaciones = TextoField(max_length=200, required=False, allow_blank=True, validators=[validar_texto_libre])

    def validate_fecha(self, fecha):
        if fecha > timezone.localdate():
            raise serializers.ValidationError("No se puede cerrar la caja de una fecha futura.")
        if CierreCaja.objects.filter(fecha=fecha).exists():
            raise Conflicto("La caja de esta fecha ya fue cerrada.")
        activos = pedidos_activos_del_dia(fecha)
        if activos:
            raise serializers.ValidationError(
                f"Aún hay {activos} pedido(s) de ese día sin cerrar o cancelar. Ciérralos antes de cerrar la caja."
            )
        return fecha


class RangoFechasSerializer(serializers.Serializer):
    """Rango del reporte de ventas: formato ISO, desde <= hasta <= hoy y máximo un año."""

    desde = serializers.DateField(input_formats=[FORMATO_FECHA])
    hasta = serializers.DateField(input_formats=[FORMATO_FECHA])

    def validate(self, datos):
        desde, hasta = datos["desde"], datos["hasta"]
        if desde > hasta:
            raise serializers.ValidationError({"desde": "La fecha inicial no puede ser posterior a la final."})
        if hasta > timezone.localdate():
            raise serializers.ValidationError({"hasta": "La fecha final no puede ser futura."})
        if hasta - desde > timedelta(days=DIAS_MAX_REPORTE):
            raise serializers.ValidationError({"desde": f"El rango no puede superar {DIAS_MAX_REPORTE} días."})
        return datos


# ---- Respuestas de solo documentación (OpenAPI) ----
class ResumenCajaSerializer(serializers.Serializer):
    fecha = serializers.DateField()
    ventas_del_dia = serializers.CharField()
    facturas = serializers.IntegerField(required=False, help_text="Solo administrador.")
    pedidos_sin_cerrar = serializers.IntegerField(required=False, help_text="Solo administrador.")
    cierre = CierreCajaSerializer(required=False, allow_null=True, help_text="Solo administrador.")


class VentaDiaSerializer(serializers.Serializer):
    dia = serializers.DateField()
    facturas = serializers.IntegerField()
    total = serializers.CharField()


class PlatoVendidoSerializer(serializers.Serializer):
    plato = serializers.CharField()
    unidades = serializers.IntegerField()
    ingresos = serializers.CharField()


class ReporteVentasSerializer(serializers.Serializer):
    desde = serializers.DateField()
    hasta = serializers.DateField()
    total_ventas = serializers.CharField()
    facturas = serializers.IntegerField()
    ticket_promedio = serializers.CharField()
    ventas_por_dia = VentaDiaSerializer(many=True)
    platos_mas_vendidos = PlatoVendidoSerializer(many=True)

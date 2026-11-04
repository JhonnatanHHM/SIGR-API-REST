from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.comun.campos import TextoField
from apps.comun.excepciones import Conflicto
from apps.comun.validators import MESA_MAX, MESA_MIN, validar_texto_libre

from .models import EstadoReserva, Reserva
from .reglas import ANTICIPACION_MINIMA, DIAS_MAX_ANTICIPACION, PERSONAS_MAX, franjas
from .services import conflictos

FORMATO_FECHA = "%Y-%m-%d"
FRANJAS = [(f"{t:%H:%M}", f"{t:%H:%M}") for t in franjas()]
ESTADOS_FILTRO = [("vigentes", "Vigentes")] + list(EstadoReserva.choices)


class ReservaSerializer(serializers.ModelSerializer):
    """Reserva completa (solo lectura)."""

    hora = serializers.TimeField(format="%H:%M", read_only=True)
    fin = serializers.SerializerMethodField()
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre_completo", read_only=True)
    puede_confirmarse = serializers.BooleanField(read_only=True)
    puede_completarse = serializers.BooleanField(read_only=True)
    puede_cancelarse = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reserva
        fields = (
            "id", "fecha", "hora", "fin", "personas", "mesa", "estado", "estado_etiqueta", "notas", "cliente",
            "cliente_nombre", "puede_confirmarse", "puede_completarse", "puede_cancelarse", "creado",
        )
        read_only_fields = fields

    def get_fin(self, reserva) -> str:
        return timezone.localtime(reserva.fin).strftime("%H:%M")


class ReservaCrearSerializer(serializers.Serializer):
    """Entrada de una reserva. El cliente y el estado nunca se reciben: son el usuario autenticado y «pendiente»."""

    fecha = serializers.DateField(input_formats=[FORMATO_FECHA])
    hora = serializers.ChoiceField(choices=FRANJAS)
    personas = serializers.IntegerField(min_value=1, max_value=PERSONAS_MAX)
    mesa = serializers.IntegerField(min_value=MESA_MIN, max_value=MESA_MAX)
    notas = TextoField(max_length=200, required=False, allow_blank=True, validators=[validar_texto_libre])

    def validate(self, datos):
        fecha = datos["fecha"]
        hora = datetime.strptime(datos["hora"], "%H:%M").time()
        datos["hora"] = hora
        inicio = timezone.make_aware(datetime.combine(fecha, hora))
        if inicio < timezone.now() + ANTICIPACION_MINIMA:
            raise serializers.ValidationError({"fecha": "La reserva debe hacerse con al menos 1 hora de anticipación."})
        if fecha > timezone.localdate() + timedelta(days=DIAS_MAX_ANTICIPACION):
            raise serializers.ValidationError({"fecha": f"Solo se reserva con hasta {DIAS_MAX_ANTICIPACION} días de anticipación."})
        cliente = self.context.get("cliente")
        mesa_ocupada, cliente_ocupado = conflictos(datos["mesa"], fecha, hora, cliente)
        if mesa_ocupada:
            raise Conflicto(f"La mesa {datos['mesa']} ya está reservada cerca de las {hora:%H:%M}. Elige otra mesa u otro horario.")
        if cliente_ocupado:
            raise Conflicto("Ya tienes una reserva vigente que se cruza con este horario.")
        return datos


class FiltroReservaSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(required=False, choices=ESTADOS_FILTRO)
    fecha = serializers.DateField(required=False, input_formats=[FORMATO_FECHA])
    mesa = serializers.IntegerField(required=False, min_value=MESA_MIN, max_value=MESA_MAX)


class CambioEstadoReservaSerializer(serializers.Serializer):
    """Estado que la persona veía al actuar (opcional): si ya cambió, la API responde 409."""

    desde = serializers.ChoiceField(required=False, choices=EstadoReserva.choices)

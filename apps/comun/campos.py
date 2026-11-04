"""Campos de serializador que normalizan y validan la entrada de forma estricta (igual que los formularios del SIGR original)."""
import re
from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .validators import limpiar_espacios


class TextoField(serializers.CharField):
    """Texto de una sola línea: quita espacios al inicio y al final y colapsa los repetidos antes de validar."""

    def to_internal_value(self, data):
        return limpiar_espacios(super().to_internal_value(data))


@extend_schema_field({"type": "string", "pattern": r"^\d{1,7}([.,]\d{1,2})?$", "example": "28000.50"})
class MontoField(serializers.Field):
    """Dinero: solo dígitos, con hasta `decimal_places` decimales (punto o coma), positivo y de `max_digits` como máximo.

    Rechaza notación científica, signos, símbolos, NaN, booleanos y cualquier tipo que no sea número o texto.
    Se entrega como texto con los decimales fijos (p. ej. "28000.50"), igual que el resto de la API.
    """

    default_error_messages = {
        "invalid": "Ingresa un valor numérico sin signos ni símbolos, con hasta {decimales} decimales (ej. 12500 o 12500.50).",
        "min_value": "El valor debe ser como mínimo {minimo}.",
    }

    def __init__(self, max_digits=9, decimal_places=2, min_value=Decimal("0.01"), **kwargs):
        super().__init__(**kwargs)
        self.max_digits, self.decimal_places, self.min_value = max_digits, decimal_places, min_value
        enteros = max_digits - decimal_places
        self.patron = re.compile(rf"^\d{{1,{enteros}}}([.,]\d{{1,{decimal_places}}})?$")

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float, Decimal, str)):
            self.fail("invalid", decimales=self.decimal_places)
        texto = str(data).strip()
        if not self.patron.match(texto):
            self.fail("invalid", decimales=self.decimal_places)
        valor = Decimal(texto.replace(",", "."))
        if valor < self.min_value:
            self.fail("min_value", minimo=self.min_value)
        return valor

    def to_representation(self, value):
        return f"{Decimal(value):.{self.decimal_places}f}"

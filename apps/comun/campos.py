"""Campos de serializador que normalizan la entrada ANTES de validarla (igual que los formularios del SIGR original)."""
from rest_framework import serializers

from .validators import limpiar_espacios


class TextoField(serializers.CharField):
    """Texto de una sola línea: quita espacios al inicio y al final y colapsa los repetidos antes de validar."""

    def to_internal_value(self, data):
        return limpiar_espacios(super().to_internal_value(data))

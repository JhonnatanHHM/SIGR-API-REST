from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.version import __version__


class SaludView(APIView):
    """Comprobación de que el servicio está arriba. No requiere credenciales."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        tags=["Salud"],
        summary="Estado del servicio",
        responses=inline_serializer(
            "Salud",
            {
                "estado": serializers.CharField(),
                "servicio": serializers.CharField(),
                "version": serializers.CharField(),
            },
        ),
    )
    def get(self, request):
        return Response({"estado": "ok", "servicio": "SIGR API REST", "version": __version__})

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.comun.excepciones import Conflicto
from apps.usuarios.permisos import EsCliente, EsPersonal

from .models import VIGENTES, EstadoReserva, Reserva
from .serializers import (
    CambioEstadoReservaSerializer, FiltroReservaSerializer, ReservaCrearSerializer, ReservaSerializer,
)
from .services import ReservaNoDisponible, crear_reserva


@extend_schema(tags=["Reservas"])
@extend_schema_view(
    list=extend_schema(
        summary="Listar reservas (el cliente ve solo las suyas; el personal, todas)",
        parameters=[
            OpenApiParameter("estado", str, enum=["vigentes"] + [e.value for e in EstadoReserva], description="Filtra por estado."),
            OpenApiParameter("fecha", str, description="Fecha en formato AAAA-MM-DD."),
            OpenApiParameter("mesa", int, description="Número de mesa (1 a 99)."),
        ],
    ),
    retrieve=extend_schema(summary="Ver una reserva (una reserva ajena responde 404)"),
    create=extend_schema(
        summary="Reservar una mesa (solo clientes)",
        description=(
            "Franjas de media hora entre 11:00 y 20:00, duración de 2 horas, anticipación de 1 hora a 30 días y hasta "
            "12 personas. Un cruce de horario responde 409."
        ),
        request=ReservaCrearSerializer,
        responses={201: ReservaSerializer},
    ),
)
class ReservaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = ReservaSerializer

    def get_permissions(self):
        if self.action == "create":
            return [EsCliente()]
        if self.action in ("confirmar", "completar"):
            return [EsPersonal()]
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):      # generación del esquema OpenAPI: no hay usuario
            return Reserva.objects.none()
        consulta = Reserva.objects.select_related("cliente")
        usuario = self.request.user
        if not usuario.es_personal:
            consulta = consulta.filter(cliente=usuario)
        if self.action != "list":
            return consulta
        filtros = FiltroReservaSerializer(data=self.request.query_params)
        filtros.is_valid(raise_exception=True)      # filtro inválido: 400 con el detalle
        datos = filtros.validated_data
        if datos.get("estado") == "vigentes":
            consulta = consulta.filter(estado__in=VIGENTES)
        elif datos.get("estado"):
            consulta = consulta.filter(estado=datos["estado"])
        if datos.get("fecha"):
            consulta = consulta.filter(fecha=datos["fecha"])
        if datos.get("mesa"):
            consulta = consulta.filter(mesa=datos["mesa"])
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = ReservaCrearSerializer(data=request.data, context={"cliente": request.user})
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        reserva = Reserva(
            cliente=request.user, fecha=datos["fecha"], hora=datos["hora"], personas=datos["personas"],
            mesa=datos["mesa"], notas=datos.get("notas", ""),
        )
        try:
            crear_reserva(reserva)      # revalida dentro de la transacción para evitar carreras
        except ReservaNoDisponible as error:
            raise Conflicto(str(error))
        return Response(
            ReservaSerializer(reserva, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": f"/api/v1/reservas/{reserva.pk}/"},
        )

    def _cambiar_estado(self, request, pk, accion):
        entrada = CambioEstadoReservaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        with transaction.atomic():
            reserva = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            desde = entrada.validated_data.get("desde")
            if desde and desde != reserva.estado:
                raise Conflicto("La reserva cambió mientras la veías. Revísala e inténtalo de nuevo.")
            try:
                getattr(reserva, accion)()
            except ValueError as error:
                raise Conflicto(str(error))
        return Response(ReservaSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data)

    @extend_schema(summary="Confirmar una reserva pendiente (personal)", request=CambioEstadoReservaSerializer, responses=ReservaSerializer)
    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        return self._cambiar_estado(request, pk, "confirmar")

    @extend_schema(summary="Marcar como completada una reserva confirmada (personal)", request=CambioEstadoReservaSerializer, responses=ReservaSerializer)
    @action(detail=True, methods=["post"])
    def completar(self, request, pk=None):
        return self._cambiar_estado(request, pk, "completar")

    @extend_schema(summary="Cancelar una reserva vigente", request=CambioEstadoReservaSerializer, responses=ReservaSerializer)
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        return self._cambiar_estado(request, pk, "cancelar")

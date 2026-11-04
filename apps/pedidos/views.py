from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.caja.services import CajaCerrada, caja_cerrada, emitir_factura
from apps.comun.excepciones import Conflicto
from apps.usuarios.permisos import EsPersonal

from .models import Estado, Pedido
from .serializers import (
    ESTADOS_ACTIVOS, CambioEstadoSerializer, FiltroPedidoSerializer, PedidoCrearSerializer, PedidoSerializer,
)
from .services import crear_pedido


@extend_schema(tags=["Pedidos"])
@extend_schema_view(
    list=extend_schema(
        summary="Listar pedidos (el cliente ve solo los suyos; el personal, todos)",
        parameters=[
            OpenApiParameter("estado", str, enum=["activos"] + [e.value for e in Estado], description="Filtra por estado."),
            OpenApiParameter("mesa", int, description="Número de mesa (1 a 99)."),
        ],
    ),
    retrieve=extend_schema(summary="Ver un pedido (un pedido ajeno responde 404)"),
    create=extend_schema(summary="Crear un pedido", request=PedidoCrearSerializer, responses={201: PedidoSerializer}),
)
class PedidoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """El cliente crea y sigue sus pedidos; el personal registra pedidos de mesa y los avanza de estado."""

    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [EsPersonal()] if self.action == "avanzar" else [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):      # generación del esquema OpenAPI: no hay usuario
            return Pedido.objects.none()
        consulta = Pedido.objects.select_related("cliente", "creado_por", "factura").prefetch_related("items__plato")
        usuario = self.request.user
        if not usuario.es_personal:
            consulta = consulta.filter(cliente=usuario)
        if self.action != "list":
            return consulta
        filtros = FiltroPedidoSerializer(data=self.request.query_params)
        filtros.is_valid(raise_exception=True)      # filtro inválido: 400 con el detalle
        estado, mesa = filtros.validated_data.get("estado"), filtros.validated_data.get("mesa")
        if estado == "activos":
            consulta = consulta.filter(estado__in=ESTADOS_ACTIVOS)
        elif estado:
            consulta = consulta.filter(estado=estado)
        if mesa:
            consulta = consulta.filter(mesa=mesa)
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = PedidoCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        pedido = crear_pedido(
            request.user, datos["mesa"], datos.get("notas", ""), [(i["plato"], i["cantidad"]) for i in datos["items"]]
        )
        pedido = self.get_queryset().get(pk=pedido.pk)
        return Response(
            PedidoSerializer(pedido, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": f"/api/v1/pedidos/{pedido.pk}/"},
        )

    def _verificar_desde(self, request, pedido):
        entrada = CambioEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        desde = entrada.validated_data.get("desde")
        if desde and desde != pedido.estado:
            raise Conflicto("El estado del pedido cambió mientras lo veías. Revísalo e inténtalo de nuevo.")

    @extend_schema(
        summary="Avanzar el pedido al siguiente estado (personal)",
        description="Si se envía `desde` y el pedido ya no está en ese estado, responde 409.",
        request=CambioEstadoSerializer,
        responses=PedidoSerializer,
    )
    @action(detail=True, methods=["post"])
    def avanzar(self, request, pk=None):
        with transaction.atomic():
            pedido = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            self._verificar_desde(request, pedido)
            if pedido.siguiente_estado is None:
                raise Conflicto("El pedido ya está en su estado final.")
            if pedido.siguiente_estado == Estado.CERRADO and caja_cerrada(timezone.localdate()):
                raise Conflicto("La caja de hoy ya está cerrada: no se pueden cerrar más pedidos hoy.")
            pedido.avanzar()
            if pedido.estado == Estado.CERRADO:      # al cerrar el pedido se emite su factura
                try:
                    emitir_factura(pedido, request.user)
                except CajaCerrada:
                    raise Conflicto("La caja de hoy ya está cerrada: no se pueden cerrar más pedidos hoy.")
        return Response(PedidoSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data)

    @extend_schema(summary="Cancelar un pedido pendiente", request=None, responses=PedidoSerializer)
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        with transaction.atomic():
            pedido = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=pk)
            if not pedido.puede_cancelarse:
                raise Conflicto("Solo se puede cancelar un pedido que sigue pendiente.")
            pedido.cancelar()
        return Response(PedidoSerializer(self.get_queryset().get(pk=pk), context=self.get_serializer_context()).data)

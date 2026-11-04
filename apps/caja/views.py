from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from apps.comun.excepciones import Conflicto
from apps.usuarios.permisos import EsAdministrador, EsPersonal

from .models import CierreCaja, Factura
from .serializers import (
    CierreCajaCrearSerializer, CierreCajaSerializer, FORMATO_FECHA, FacturaDetalleSerializer, FacturaSerializer,
    RangoFechasSerializer, ReporteVentasSerializer, ResumenCajaSerializer,
)
from .services import (
    cerrar_caja, pedidos_activos_del_dia, platos_mas_vendidos, totales_del_rango, ventas_del_dia, ventas_por_dia,
)


def _dinero(valor):
    return f"{Decimal(valor):.2f}"


@extend_schema(tags=["Caja"], summary="Resumen de caja del día", responses=ResumenCajaSerializer,
               description="El mesero solo ve el total de ventas del día; el administrador ve además facturas, pedidos sin cerrar y el cierre.")
class ResumenCajaView(APIView):
    permission_classes = [EsPersonal]

    def get(self, request):
        hoy = timezone.localdate()
        total, cantidad = ventas_del_dia(hoy)
        cuerpo = {"fecha": hoy.isoformat(), "ventas_del_dia": _dinero(total)}
        if request.user.es_administrador:      # el mesero solo recibe el total del día
            cierre = CierreCaja.objects.filter(fecha=hoy).select_related("cerrado_por").first()
            cuerpo.update(
                facturas=cantidad,
                pedidos_sin_cerrar=pedidos_activos_del_dia(hoy),
                cierre=CierreCajaSerializer(cierre).data if cierre else None,
            )
        return Response(cuerpo)


@extend_schema(tags=["Caja"])
@extend_schema_view(
    list=extend_schema(summary="Listar facturas (administrador)"),
    retrieve=extend_schema(summary="Ver una factura con el detalle del pedido (una factura ajena responde 404 al cliente)"),
)
class FacturaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    def get_permissions(self):
        return [EsAdministrador()] if self.action == "list" else [IsAuthenticated()]

    def get_serializer_class(self):
        return FacturaSerializer if self.action == "list" else FacturaDetalleSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Factura.objects.none()
        consulta = Factura.objects.select_related("pedido", "pedido__cliente", "pedido__creado_por", "emitida_por").prefetch_related(
            "pedido__items__plato"
        )
        usuario = self.request.user
        return consulta if usuario.es_personal else consulta.filter(pedido__cliente=usuario)


@extend_schema(tags=["Caja"])
@extend_schema_view(
    list=extend_schema(summary="Listar cierres de caja (administrador)"),
    retrieve=extend_schema(summary="Ver un cierre de caja (administrador)"),
    create=extend_schema(
        summary="Cerrar la caja de un día (administrador)",
        description=(
            "Compara el efectivo contado con las ventas facturadas del día y guarda la diferencia. Un cierre no se "
            "puede modificar, eliminar ni repetir (409). No se permite con pedidos del día sin cerrar."
        ),
        request=CierreCajaCrearSerializer,
        responses={201: CierreCajaSerializer},
    ),
)
class CierreCajaViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = CierreCajaSerializer
    permission_classes = [EsAdministrador]
    queryset = CierreCaja.objects.select_related("cerrado_por")

    def create(self, request, *args, **kwargs):
        entrada = CierreCajaCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        try:
            cierre = cerrar_caja(datos["fecha"], datos["efectivo_contado"], datos.get("observaciones", ""), request.user)
        except IntegrityError:
            raise Conflicto("La caja de esta fecha ya fue cerrada.")
        return Response(
            CierreCajaSerializer(cierre).data,
            status=status.HTTP_201_CREATED,
            headers={"Location": f"/api/v1/caja/cierres/{cierre.pk}/"},
        )


@extend_schema(
    tags=["Caja"],
    summary="Reporte de ventas por rango de fechas (administrador)",
    parameters=[
        OpenApiParameter("desde", str, description="AAAA-MM-DD; por defecto, hace 6 días."),
        OpenApiParameter("hasta", str, description="AAAA-MM-DD; por defecto, hoy. No puede ser futura ni superar un año de rango."),
    ],
    responses=ReporteVentasSerializer,
)
class ReporteVentasView(APIView):
    permission_classes = [EsAdministrador]

    def get(self, request):
        hoy = timezone.localdate()
        entrada = RangoFechasSerializer(data={
            "desde": request.query_params.get("desde") or (hoy - timedelta(days=6)).strftime(FORMATO_FECHA),
            "hasta": request.query_params.get("hasta") or hoy.strftime(FORMATO_FECHA),
        })
        entrada.is_valid(raise_exception=True)
        desde, hasta = entrada.validated_data["desde"], entrada.validated_data["hasta"]
        total, facturas = totales_del_rango(desde, hasta)
        promedio = (total / facturas).quantize(Decimal("0.01")) if facturas else Decimal("0")
        cuerpo = {
            "desde": desde,
            "hasta": hasta,
            "total_ventas": _dinero(total),
            "facturas": facturas,
            "ticket_promedio": _dinero(promedio),
            "ventas_por_dia": [
                {"dia": d["dia"], "facturas": d["facturas"], "total": _dinero(d["total"])} for d in ventas_por_dia(desde, hasta)
            ],
            "platos_mas_vendidos": [
                {"plato": p["plato__nombre"], "unidades": p["unidades"], "ingresos": _dinero(p["ingresos"])}
                for p in platos_mas_vendidos(desde, hasta)
            ],
        }
        return Response(ReporteVentasSerializer(cuerpo).data)

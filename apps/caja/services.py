from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.pedidos.models import SIGUIENTE, ItemPedido, Pedido

from .models import CierreCaja, Factura


class CajaCerrada(Exception):
    """La caja del día ya fue cerrada y no admite más ventas."""


def caja_cerrada(fecha):
    return CierreCaja.objects.filter(fecha=fecha).exists()


@transaction.atomic
def emitir_factura(pedido, usuario):
    """Emite (una sola vez) la factura de un pedido cerrado, con su total congelado."""
    if caja_cerrada(timezone.localdate()):
        raise CajaCerrada("La caja de hoy ya está cerrada.")
    factura, _ = Factura.objects.get_or_create(
        pedido=pedido, defaults={"total": pedido.total, "emitida_por": usuario}
    )
    return factura


def ventas_del_dia(fecha):
    """Devuelve (total, cantidad de facturas) emitidas en `fecha`."""
    datos = Factura.objects.filter(emitida__date=fecha).aggregate(total=Sum("total"), cantidad=Count("id"))
    return datos["total"] or Decimal("0"), datos["cantidad"]


def pedidos_activos_del_dia(fecha):
    """Pedidos creados en `fecha` que todavía no se cierran ni se cancelan."""
    return Pedido.objects.filter(creado__date=fecha, estado__in=list(SIGUIENTE)).count()


@transaction.atomic
def cerrar_caja(fecha, efectivo_contado, observaciones, usuario):
    total, cantidad = ventas_del_dia(fecha)
    return CierreCaja.objects.create(
        fecha=fecha,
        total_ventas=total,
        numero_facturas=cantidad,
        efectivo_contado=efectivo_contado,
        diferencia=efectivo_contado - total,
        observaciones=observaciones,
        cerrado_por=usuario,
    )


# ---------- Reportes ----------
def ventas_por_dia(desde, hasta):
    return list(
        Factura.objects.filter(emitida__date__gte=desde, emitida__date__lte=hasta)
        .annotate(dia=TruncDate("emitida"))
        .values("dia")
        .annotate(total=Sum("total"), facturas=Count("id"))
        .order_by("dia")
    )


def totales_del_rango(desde, hasta):
    datos = Factura.objects.filter(emitida__date__gte=desde, emitida__date__lte=hasta).aggregate(
        total=Sum("total"), facturas=Count("id")
    )
    return datos["total"] or Decimal("0"), datos["facturas"]


def platos_mas_vendidos(desde, hasta, limite=10):
    ingresos = ExpressionWrapper(F("cantidad") * F("precio_unitario"), output_field=DecimalField(max_digits=16, decimal_places=2))
    return list(
        ItemPedido.objects.filter(pedido__factura__emitida__date__gte=desde, pedido__factura__emitida__date__lte=hasta)
        .values("plato__nombre")
        .annotate(unidades=Sum("cantidad"), ingresos=Sum(ingresos))
        .order_by("-unidades", "plato__nombre")[:limite]
    )

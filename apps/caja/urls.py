from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("caja/facturas", views.FacturaViewSet, basename="factura")
router.register("caja/cierres", views.CierreCajaViewSet, basename="cierre")

urlpatterns = [
    path("caja/resumen/", views.ResumenCajaView.as_view(), name="caja-resumen"),
    path("caja/reportes/ventas/", views.ReporteVentasView.as_view(), name="caja-reporte-ventas"),
] + router.urls

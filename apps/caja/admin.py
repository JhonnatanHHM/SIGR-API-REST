from django.contrib import admin

from .models import CierreCaja, Factura


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ("numero", "pedido", "total", "emitida", "emitida_por")
    readonly_fields = ("pedido", "total", "emitida", "emitida_por")


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "total_ventas", "efectivo_contado", "diferencia", "cerrado_por")
    readonly_fields = [f.name for f in CierreCaja._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

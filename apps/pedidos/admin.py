from django.contrib import admin

from .models import ItemPedido, Pedido


class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "mesa", "estado", "cliente", "creado_por", "creado")
    list_filter = ("estado",)
    inlines = [ItemPedidoInline]

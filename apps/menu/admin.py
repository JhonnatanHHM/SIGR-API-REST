from django.contrib import admin

from .models import Categoria, Plato


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "orden", "activa")
    list_editable = ("orden", "activa")
    search_fields = ("nombre",)


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio", "disponible")
    list_filter = ("categoria", "disponible")
    search_fields = ("nombre", "descripcion")

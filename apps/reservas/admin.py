from django.contrib import admin

from .models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "hora", "mesa", "personas", "estado", "cliente")
    list_filter = ("estado", "fecha")
    search_fields = ("cliente__email", "cliente__first_name", "cliente__last_name")

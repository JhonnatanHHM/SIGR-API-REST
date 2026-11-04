from django.urls import path

from .views import SaludView

urlpatterns = [
    path("salud/", SaludView.as_view(), name="salud"),
]

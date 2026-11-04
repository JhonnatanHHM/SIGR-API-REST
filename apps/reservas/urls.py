from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("reservas", views.ReservaViewSet, basename="reserva")

urlpatterns = router.urls

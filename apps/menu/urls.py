from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("platos", views.PlatoViewSet, basename="plato")

urlpatterns = router.urls

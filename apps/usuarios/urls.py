from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("usuarios", views.UsuarioViewSet, basename="usuario")

urlpatterns = [
    path("auth/registro/", views.RegistroView.as_view(), name="auth-registro"),
    path("auth/login/", views.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/yo/", views.YoView.as_view(), name="auth-yo"),
    path("", include(router.urls)),
]

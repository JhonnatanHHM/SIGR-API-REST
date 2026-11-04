from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.comun.urls")),
    # Documentación OpenAPI: el esquema se puede importar en Postman
    path("api/schema/", SpectacularAPIView.as_view(), name="esquema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="esquema"), name="swagger"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="esquema"), name="redoc"),
]

if settings.DEBUG:
    # En desarrollo Django sirve las fotos subidas; en producción las sirve nginx.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from config.version import __version__


class SaludTests(TestCase):
    def test_salud_responde_json_sin_credenciales(self):
        respuesta = APIClient().get(reverse("salud"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        self.assertEqual(respuesta.json(), {"estado": "ok", "servicio": "SIGR API REST", "version": __version__})

    def test_la_ruta_vive_bajo_el_prefijo_versionado(self):
        self.assertEqual(reverse("salud"), "/api/v1/salud/")

    def test_solo_acepta_get(self):
        for metodo in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(APIClient(), metodo)(reverse("salud")).status_code, 405, metodo)


class DocumentacionTests(TestCase):
    def test_el_esquema_openapi_es_valido_y_describe_la_api(self):
        respuesta = APIClient().get(reverse("esquema"), {"format": "json"})
        self.assertEqual(respuesta.status_code, 200)
        esquema = respuesta.json()
        self.assertTrue(esquema["openapi"].startswith("3."))
        self.assertEqual(esquema["info"]["title"], "SIGR API REST")
        self.assertIn("/api/v1/salud/", esquema["paths"])

    def test_swagger_y_redoc_cargan(self):
        for nombre in ("swagger", "redoc"):
            self.assertEqual(APIClient().get(reverse(nombre)).status_code, 200, nombre)

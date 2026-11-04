import os
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class IntegridadDelProyectoTests(TestCase):
    def test_no_faltan_migraciones(self):
        # makemigrations --check termina con error (SystemExit) si un modelo cambió sin su migración.
        call_command("makemigrations", check=True, dry_run=True, verbosity=0, stdout=StringIO())

    def test_la_verificacion_de_django_no_reporta_problemas(self):
        call_command("check", verbosity=0)

    def test_el_esquema_openapi_es_valido_y_no_tiene_avisos(self):
        # El esquema es la fuente de la documentación y de la colección de Postman: debe estar limpio.
        call_command("spectacular", validate=True, fail_on_warn=True, file=os.devnull, stdout=StringIO(), stderr=StringIO())

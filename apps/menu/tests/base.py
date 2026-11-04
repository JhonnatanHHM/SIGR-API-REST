import os
import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.menu.models import Categoria, Plato
from apps.usuarios.models import Rol
from apps.usuarios.tests.base import cliente_api, crear_usuario  # noqa: F401  (se reexportan para las pruebas del módulo)


class DatosMenuMixin:
    """Un usuario de cada rol, categorías (una oculta) y platos (uno agotado y otro en la categoría oculta)."""

    def setUp(self):
        super().setUp()
        self.cliente = crear_usuario("cli@ejemplo.com", Rol.CLIENTE)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)
        self.fuertes = Categoria.objects.create(nombre="Fuertes", orden=1)
        self.postres = Categoria.objects.create(nombre="Postres", orden=2)
        self.oculta = Categoria.objects.create(nombre="Oculta", orden=3, activa=False)
        self.pasta = Plato.objects.create(categoria=self.fuertes, nombre="Pasta alfredo", precio="28000")
        self.agotado = Plato.objects.create(categoria=self.fuertes, nombre="Salmón", precio="42500", disponible=False)
        self.brownie = Plato.objects.create(categoria=self.postres, nombre="Brownie", precio="14500")
        self.secreto = Plato.objects.create(categoria=self.oculta, nombre="Plato secreto", precio="1000")

    def datos_plato(self, **cambios):
        base = {"categoria": self.postres.pk, "nombre": "Flan", "descripcion": "De caramelo", "precio": "8000"}
        base.update(cambios)
        return base


def imagen_bytes(formato="PNG", tamano=(40, 30)):
    buffer = BytesIO()
    Image.new("RGB", tamano, (200, 120, 50)).save(buffer, format=formato)
    return buffer.getvalue()


def subida(nombre="plato.png", contenido=None, tipo="image/png"):
    return SimpleUploadedFile(nombre, imagen_bytes() if contenido is None else contenido, content_type=tipo)


class MediaTemporalMixin:
    """Las fotos de las pruebas se guardan en una carpeta temporal que se borra al terminar."""

    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp(prefix="media_prueba_")
        configuracion = override_settings(MEDIA_ROOT=self.media)
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

    def archivos_guardados(self):
        carpeta = os.path.join(self.media, "platos")
        return sorted(os.listdir(carpeta)) if os.path.isdir(carpeta) else []

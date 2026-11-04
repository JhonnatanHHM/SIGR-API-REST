from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.comun.validators import validar_imagen
from apps.menu.models import Plato

from .base import DatosMenuMixin, MediaTemporalMixin, cliente_api, imagen_bytes, subida


class ValidarImagenTests(TestCase):
    def test_acepta_jpg_png_y_webp_reales(self):
        for formato, nombre in (("PNG", "a.png"), ("JPEG", "a.jpg"), ("JPEG", "a.jpeg"), ("WEBP", "a.webp")):
            with self.subTest(formato=formato, nombre=nombre):
                validar_imagen(subida(nombre, imagen_bytes(formato)))

    def test_rechaza_extensiones_no_permitidas(self):
        for nombre in ("a.svg", "a.gif", "a.bmp", "a.php", "a.html", "a.exe", "sin_extension", "a.png.exe", "a.PNG.svg"):
            with self.subTest(nombre=nombre):
                with self.assertRaises(ValidationError):
                    validar_imagen(subida(nombre, imagen_bytes()))

    def test_rechaza_archivos_que_no_son_imagenes_aunque_tengan_extension_de_imagen(self):
        falsos = {
            "texto.png": b"esto no es una imagen",
            "script.jpg": b"<script>alert(1)</script>",
            "svg.png": b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "php.png": b"<?php system($_GET['c']); ?>",
            "vacio.png": b"",
            "truncada.png": imagen_bytes()[:30],
        }
        for nombre, contenido in falsos.items():
            with self.subTest(nombre=nombre):
                with self.assertRaises(ValidationError):
                    validar_imagen(subida(nombre, contenido))

    def test_el_contenido_debe_coincidir_con_la_extension(self):
        for nombre, formato in (("a.jpg", "PNG"), ("a.png", "JPEG"), ("a.png", "GIF"), ("a.webp", "PNG")):
            with self.subTest(nombre=nombre, formato=formato):
                with self.assertRaises(ValidationError):
                    validar_imagen(subida(nombre, imagen_bytes(formato)))

    def test_limite_de_peso_y_de_dimensiones(self):
        with self.assertRaises(ValidationError):
            validar_imagen(subida("a.png", b"x" * (2 * 1024 * 1024 + 1)))
        validar_imagen(subida("a.png", imagen_bytes(tamano=(4000, 10))))
        for tamano in ((4001, 10), (10, 4001)):
            with self.assertRaises(ValidationError):
                validar_imagen(subida("a.png", imagen_bytes(tamano=tamano)))


class FotoDelPlatoModeloTests(MediaTemporalMixin, DatosMenuMixin, TestCase):
    def test_se_guarda_con_nombre_aleatorio_y_no_con_el_del_navegador(self):
        self.pasta.imagen = subida("../../etc/foto original.png")
        self.pasta.save()
        self.assertRegex(self.pasta.imagen.name, r"^platos/[0-9a-f]{32}\.png$")
        self.assertNotIn("etc", self.pasta.imagen.name)

    def test_al_reemplazar_quitar_o_eliminar_se_borra_el_archivo(self):
        self.pasta.imagen = subida()
        self.pasta.save()
        self.pasta.imagen = subida("otra.png")
        self.pasta.save()
        self.assertEqual(len(self.archivos_guardados()), 1)
        self.pasta.imagen = ""
        self.pasta.save()
        self.assertEqual(self.archivos_guardados(), [])
        self.pasta.imagen = subida()
        self.pasta.save()
        self.pasta.delete()
        self.assertEqual(self.archivos_guardados(), [])

    def test_guardar_sin_cambiar_la_foto_no_la_borra(self):
        self.pasta.imagen = subida()
        self.pasta.save()
        self.pasta.refresh_from_db()
        self.pasta.precio = 30000
        self.pasta.save()
        self.assertEqual(len(self.archivos_guardados()), 1)


class FotoDelPlatoApiTests(MediaTemporalMixin, DatosMenuMixin, TestCase):
    def test_el_administrador_crea_un_plato_con_foto_por_multipart(self):
        r = cliente_api(self.admin).post(
            reverse("plato-list"), self.datos_plato(destacado="true", imagen=subida()), format="multipart"
        )
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertTrue(cuerpo["destacado"] and cuerpo["disponible"])      # «disponible» queda en true por defecto
        self.assertRegex(cuerpo["imagen"], r"^http://testserver/media/platos/[0-9a-f]{32}\.png$")
        self.assertEqual(len(self.archivos_guardados()), 1)

    def test_archivos_falsos_no_crean_el_plato_ni_dejan_archivos(self):
        for nombre, contenido in (("x.png", b"no soy imagen"), ("x.svg", b"<svg></svg>"), ("x.php", b"<?php ?>"),
                                  ("x.png", imagen_bytes("GIF")), ("x.jpg", imagen_bytes(tamano=(4001, 5), formato="JPEG"))):
            r = cliente_api(self.admin).post(reverse("plato-list"), self.datos_plato(imagen=subida(nombre, contenido)), format="multipart")
            self.assertEqual(r.status_code, 400, nombre)
            self.assertIn("imagen", r.json())
        self.assertFalse(Plato.objects.filter(nombre="Flan").exists())
        self.assertEqual(self.archivos_guardados(), [])

    def test_foto_demasiado_pesada_se_rechaza(self):
        r = cliente_api(self.admin).post(
            reverse("plato-list"), self.datos_plato(imagen=subida("x.png", b"x" * (2 * 1024 * 1024 + 1))), format="multipart"
        )
        self.assertEqual(r.status_code, 400)

    def test_solo_el_administrador_sube_fotos(self):
        url = reverse("plato-detail", args=[self.pasta.pk])
        for usuario, esperado in ((None, 401), (self.cliente, 403), (self.mesero, 403)):
            r = cliente_api(usuario).patch(url, {"imagen": subida()}, format="multipart")
            self.assertEqual(r.status_code, esperado, usuario)
        self.assertEqual(self.archivos_guardados(), [])

    def test_reemplazar_y_quitar_la_foto(self):
        c, url = cliente_api(self.admin), reverse("plato-detail", args=[self.pasta.pk])
        c.patch(url, {"imagen": subida()}, format="multipart")
        primera = Plato.objects.get(pk=self.pasta.pk).imagen.name
        c.patch(url, {"imagen": subida("otra.png")}, format="multipart")
        self.assertNotEqual(Plato.objects.get(pk=self.pasta.pk).imagen.name, primera)
        self.assertEqual(len(self.archivos_guardados()), 1)
        r = c.patch(url, {"imagen": None}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.json()["imagen"])
        self.assertEqual(self.archivos_guardados(), [])

    def test_editar_otros_campos_conserva_la_foto(self):
        c, url = cliente_api(self.admin), reverse("plato-detail", args=[self.pasta.pk])
        c.patch(url, {"imagen": subida()}, format="multipart")
        c.patch(url, {"precio": "29000"}, format="json")
        self.assertEqual(len(self.archivos_guardados()), 1)
        self.assertIsNotNone(c.get(url).json()["imagen"])

    def test_el_publico_ve_la_url_de_la_foto_solo_en_los_platos_que_la_tienen(self):
        self.pasta.imagen = subida()
        self.pasta.save()
        platos = {p["nombre"]: p["imagen"] for p in cliente_api().get(reverse("plato-list")).json()["results"]}
        self.assertTrue(platos["Pasta alfredo"].startswith("http://testserver/media/platos/"))
        self.assertIsNone(platos["Brownie"])

    def test_eliminar_el_plato_borra_su_foto(self):
        self.pasta.imagen = subida()
        self.pasta.save()
        self.assertEqual(cliente_api(self.admin).delete(reverse("plato-detail", args=[self.pasta.pk])).status_code, 204)
        self.assertEqual(self.archivos_guardados(), [])

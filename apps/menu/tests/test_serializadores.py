from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework import serializers

from apps.comun.campos import MontoField
from apps.menu.models import Categoria, Plato
from apps.menu.serializers import CategoriaSerializer, FiltroPlatoSerializer, PlatoSerializer


def errores(serializador):
    serializador.is_valid()
    return serializador.errors


class MontoFieldTests(SimpleTestCase):
    def test_valores_validos_se_normalizan(self):
        campo = MontoField()
        self.assertEqual(campo.run_validation("12500"), Decimal("12500"))
        self.assertEqual(campo.run_validation("12500,5"), Decimal("12500.5"))
        self.assertEqual(campo.run_validation(" 9.99 "), Decimal("9.99"))
        self.assertEqual(campo.run_validation(28000), Decimal("28000"))
        self.assertEqual(campo.run_validation(28000.5), Decimal("28000.5"))

    def test_valores_invalidos(self):
        campo = MontoField()
        malos = ["abc", "-5", "0", "0.00", "1e3", "10.999", "99999999", "1,000.50", "12 500", "' OR 1=1 --", "NaN", "Infinity",
                 "$100", "", True, False, [], {}, [1], {"a": 1}, 28000.555, 1e16]
        for malo in malos:
            with self.subTest(valor=malo):
                with self.assertRaises(serializers.ValidationError):
                    campo.run_validation(malo)

    def test_representacion_con_decimales_fijos(self):
        self.assertEqual(MontoField().to_representation(Decimal("28000")), "28000.00")

    def test_digitos_configurables(self):
        campo = MontoField(max_digits=12, min_value=Decimal("0"))
        self.assertEqual(campo.run_validation("9999999999.99"), Decimal("9999999999.99"))
        self.assertEqual(campo.run_validation("0"), Decimal("0"))
        with self.assertRaises(serializers.ValidationError):
            campo.run_validation("12345678901")


class CategoriaSerializerTests(TestCase):
    def test_valida_y_normaliza(self):
        s = CategoriaSerializer(data={"nombre": "  Platos   fuertes ", "descripcion": " Lo mejor ", "orden": 2, "activa": True})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["nombre"], "Platos fuertes")
        self.assertEqual(s.validated_data["descripcion"], "Lo mejor")

    def test_valores_por_defecto(self):
        s = CategoriaSerializer(data={"nombre": "Bebidas"})
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual((s.validated_data["orden"], s.validated_data["activa"]), (0, True))

    def test_nombres_y_textos_peligrosos(self):
        for nombre in ["<script>alert(1)</script>", "x'; DROP TABLE menu_categoria;--", "a;b", "=cmd", "@", "-1", "../x"]:
            with self.subTest(nombre=nombre):
                self.assertIn("nombre", errores(CategoriaSerializer(data={"nombre": nombre})))
        self.assertIn("descripcion", errores(CategoriaSerializer(data={"nombre": "Ok", "descripcion": "<b>hola</b>"})))

    def test_orden_numerico_en_rango(self):
        for malo in ["abc", -1, 1000, 1.5, "1.5", None, [], True]:
            with self.subTest(orden=malo):
                self.assertIn("orden", errores(CategoriaSerializer(data={"nombre": "Ok", "orden": malo})))

    def test_nombre_unico_sin_importar_mayusculas(self):
        Categoria.objects.create(nombre="Postres")
        self.assertIn("nombre", errores(CategoriaSerializer(data={"nombre": "POSTRES"})))

    def test_editar_la_misma_categoria_no_choca_consigo_misma(self):
        c = Categoria.objects.create(nombre="Postres")
        self.assertTrue(CategoriaSerializer(c, data={"nombre": "Postres"}, partial=True).is_valid())


class PlatoSerializerTests(TestCase):
    def setUp(self):
        self.cat = Categoria.objects.create(nombre="Fuertes")

    def datos(self, **cambios):
        base = {"categoria": self.cat.pk, "nombre": "Bandeja paisa", "descripcion": "Con arepa", "precio": "34000"}
        base.update(cambios)
        return base

    def test_plato_valido(self):
        s = PlatoSerializer(data=self.datos(nombre="  Bandeja   paisa ", precio="34000,50"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["nombre"], "Bandeja paisa")
        self.assertEqual(s.validated_data["precio"], Decimal("34000.50"))

    def test_precio_invalido(self):
        for malo in ["abc", "-1", "0", "1e3", "10.999", "99999999", "", "'; DROP TABLE x;--", None, True, [], {}]:
            with self.subTest(precio=malo):
                self.assertIn("precio", errores(PlatoSerializer(data=self.datos(precio=malo))))

    def test_categoria_inexistente_inactiva_o_manipulada(self):
        inactiva = Categoria.objects.create(nombre="Oculta", activa=False)
        for malo in [9999, "abc", "' OR 1=1", inactiva.pk, "", None, [1], {"a": 1}]:
            with self.subTest(categoria=malo):
                self.assertIn("categoria", errores(PlatoSerializer(data=self.datos(categoria=malo))))

    def test_nombre_y_descripcion_peligrosos(self):
        self.assertIn("nombre", errores(PlatoSerializer(data=self.datos(nombre="<img src=x onerror=alert(1)>"))))
        self.assertIn("descripcion", errores(PlatoSerializer(data=self.datos(descripcion="<script>x</script>"))))
        self.assertIn("nombre", errores(PlatoSerializer(data=self.datos(nombre="x" * 101))))
        self.assertIn("descripcion", errores(PlatoSerializer(data=self.datos(descripcion="x" * 501))))

    def test_nombre_repetido_en_la_misma_categoria(self):
        Plato.objects.create(categoria=self.cat, nombre="Bandeja paisa", precio="1000")
        self.assertIn("nombre", errores(PlatoSerializer(data=self.datos(nombre="BANDEJA PAISA"))))

    def test_un_plato_conserva_su_categoria_aunque_luego_se_oculte(self):
        plato = Plato.objects.create(categoria=self.cat, nombre="Sopa", precio="1000")
        self.cat.activa = False
        self.cat.save()
        s = PlatoSerializer(plato, data={"categoria": self.cat.pk, "precio": "2000"}, partial=True)
        self.assertTrue(s.is_valid(), s.errors)

    def test_campos_de_solo_lectura_se_ignoran(self):
        s = PlatoSerializer(data=self.datos(id=999, categoria_nombre="Hackeada"))
        self.assertTrue(s.is_valid(), s.errors)
        self.assertNotIn("id", s.validated_data)
        self.assertNotIn("categoria_nombre", s.validated_data)


class FiltroPlatoSerializerTests(TestCase):
    def test_busquedas_peligrosas_se_rechazan(self):
        for q in ["' OR 1=1 --", "a; DROP TABLE x", "<script>", "a%b", "x" * 101]:
            with self.subTest(q=q):
                self.assertIn("q", errores(FiltroPlatoSerializer(data={"q": q})))

    def test_categoria_y_disponibilidad_validadas(self):
        self.assertIn("categoria", errores(FiltroPlatoSerializer(data={"categoria": 99999})))
        self.assertIn("categoria", errores(FiltroPlatoSerializer(data={"categoria": "1 OR 1=1"})))
        self.assertIn("disponible", errores(FiltroPlatoSerializer(data={"disponible": "talvez"})))
        self.assertTrue(FiltroPlatoSerializer(data={"q": "pasta", "disponible": "true"}).is_valid())

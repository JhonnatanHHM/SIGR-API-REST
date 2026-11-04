from django.test import TestCase
from django.urls import reverse

from apps.menu.models import Categoria, Plato
from apps.usuarios.models import Rol

from .base import DatosMenuMixin, cliente_api


def nombres(respuesta):
    cuerpo = respuesta.json()
    return [x["nombre"] for x in (cuerpo["results"] if isinstance(cuerpo, dict) else cuerpo)]


class CartaPublicaTests(DatosMenuMixin, TestCase):
    def test_visitante_ve_solo_platos_disponibles_de_categorias_activas(self):
        r = cliente_api().get(reverse("plato-list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(nombres(r), ["Pasta alfredo", "Brownie"])
        self.assertEqual(set(r.json()), {"count", "next", "previous", "results"})

    def test_el_cliente_ve_lo_mismo_que_el_visitante(self):
        self.assertEqual(nombres(cliente_api(self.cliente).get(reverse("plato-list"))), ["Pasta alfredo", "Brownie"])

    def test_el_personal_ve_todos_los_platos(self):
        for usuario in (self.mesero, self.admin):
            self.assertEqual(len(nombres(cliente_api(usuario).get(reverse("plato-list")))), 4)

    def test_platos_no_visibles_responden_404_al_publico(self):
        for plato in (self.agotado, self.secreto):
            self.assertEqual(cliente_api().get(reverse("plato-detail", args=[plato.pk])).status_code, 404)
            self.assertEqual(cliente_api(self.mesero).get(reverse("plato-detail", args=[plato.pk])).status_code, 200)

    def test_categorias_publicas_solo_activas_y_el_admin_ve_todas(self):
        self.assertEqual(nombres(cliente_api().get(reverse("categoria-list"))), ["Fuertes", "Postres"])
        self.assertEqual(nombres(cliente_api(self.admin).get(reverse("categoria-list"))), ["Fuertes", "Postres", "Oculta"])
        self.assertEqual(cliente_api().get(reverse("categoria-detail", args=[self.oculta.pk])).status_code, 404)

    def test_busqueda_y_filtro_por_categoria(self):
        c = cliente_api()
        self.assertEqual(nombres(c.get(reverse("plato-list"), {"q": "brown"})), ["Brownie"])
        self.assertEqual(nombres(c.get(reverse("plato-list"), {"categoria": self.fuertes.pk})), ["Pasta alfredo"])

    def test_filtro_de_disponibilidad_solo_aplica_al_personal(self):
        self.assertEqual(nombres(cliente_api(self.mesero).get(reverse("plato-list"), {"disponible": "false"})), ["Salmón"])
        # el personal ve también los platos de categorías ocultas
        self.assertEqual(nombres(cliente_api(self.mesero).get(reverse("plato-list"), {"disponible": "true"})), ["Pasta alfredo", "Brownie", "Plato secreto"])
        self.assertEqual(nombres(cliente_api().get(reverse("plato-list"), {"disponible": "false"})), ["Pasta alfredo", "Brownie"])

    def test_filtros_hostiles_responden_400_y_no_tocan_la_base(self):
        for usuario in (None, self.admin):
            c = cliente_api(usuario)
            for params in [{"q": "' OR 1=1 --"}, {"q": "x'; DROP TABLE menu_plato; --"}, {"q": "<script>alert(1)</script>"},
                           {"categoria": "1 OR 1=1"}, {"categoria": 99999}, {"categoria": "abc"}, {"disponible": "talvez"}, {"q": "x" * 101}]:
                r = c.get(reverse("plato-list"), params)
                self.assertEqual(r.status_code, 400, (usuario, params))
        self.assertEqual(Plato.objects.count(), 4)

    def test_paginacion(self):
        c = cliente_api(self.admin)
        r = c.get(reverse("plato-list"), {"page_size": 2})
        self.assertEqual((len(r.json()["results"]), r.json()["count"]), (2, 4))
        self.assertIsNotNone(r.json()["next"])
        self.assertEqual(c.get(reverse("plato-list"), {"page": 99}).status_code, 404)

    def test_destacados_publicos_con_maximo_de_seis(self):
        for numero in range(8):
            Plato.objects.create(categoria=self.fuertes, nombre=f"Estrella {numero}", precio="1000", destacado=True)
        r = cliente_api().get(reverse("plato-destacados"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 6)
        self.assertTrue(all(p["destacado"] for p in r.json()))

    def test_sin_destacados_se_muestran_los_primeros_disponibles(self):
        self.assertEqual(nombres(cliente_api().get(reverse("plato-destacados"))), ["Pasta alfredo", "Brownie"])

    def test_los_destacados_no_incluyen_agotados_ni_categorias_ocultas(self):
        Plato.objects.filter(pk__in=[self.agotado.pk, self.secreto.pk]).update(destacado=True)
        Plato.objects.filter(pk=self.pasta.pk).update(destacado=True)
        self.assertEqual(nombres(cliente_api().get(reverse("plato-destacados"))), ["Pasta alfredo"])

    def test_la_respuesta_incluye_el_nombre_de_la_categoria_y_el_precio_con_dos_decimales(self):
        plato = cliente_api().get(reverse("plato-detail", args=[self.pasta.pk])).json()
        self.assertEqual((plato["categoria_nombre"], plato["precio"]), ("Fuertes", "28000.00"))


class PermisosDeEscrituraTests(DatosMenuMixin, TestCase):
    def esperados(self):
        return ((None, 401), (self.cliente, 403), (self.mesero, 403), (self.admin, 201))

    def test_crear_plato_solo_el_administrador(self):
        for usuario, codigo in self.esperados():
            r = cliente_api(usuario).post(reverse("plato-list"), self.datos_plato(nombre=f"Flan {codigo}"), format="json")
            self.assertEqual(r.status_code, codigo, usuario)
        self.assertEqual(Plato.objects.filter(nombre__startswith="Flan").count(), 1)

    def test_crear_categoria_solo_el_administrador(self):
        for usuario, codigo in self.esperados():
            r = cliente_api(usuario).post(reverse("categoria-list"), {"nombre": f"Bebidas {codigo}"}, format="json")
            self.assertEqual(r.status_code, codigo, usuario)

    def test_editar_y_eliminar_solo_el_administrador(self):
        url = reverse("plato-detail", args=[self.pasta.pk])
        for usuario in (None, self.cliente, self.mesero):
            c = cliente_api(usuario)
            esperado = 401 if usuario is None else 403
            self.assertEqual(c.patch(url, {"precio": "1"}, format="json").status_code, esperado)
            self.assertEqual(c.put(url, self.datos_plato(), format="json").status_code, esperado)
            self.assertEqual(c.delete(url).status_code, esperado)
        self.pasta.refresh_from_db()
        self.assertEqual(str(self.pasta.precio), "28000.00")

    def test_el_mesero_marca_disponibilidad_el_cliente_y_el_visitante_no(self):
        url = reverse("plato-disponibilidad", args=[self.pasta.pk])
        self.assertEqual(cliente_api().post(url).status_code, 401)
        self.assertEqual(cliente_api(self.cliente).post(url).status_code, 403)
        r = cliente_api(self.mesero).post(url)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["disponible"])
        self.assertFalse(Plato.objects.get(pk=self.pasta.pk).disponible)
        self.assertTrue(cliente_api(self.admin).post(url).json()["disponible"])

    def test_disponibilidad_no_acepta_get_ni_ids_inexistentes(self):
        url = reverse("plato-disponibilidad", args=[self.pasta.pk])
        self.assertEqual(cliente_api(self.admin).get(url).status_code, 405)
        # sin el rol adecuado se responde 403 antes de revelar qué métodos existen
        self.assertEqual(cliente_api(self.mesero).get(url).status_code, 403)
        self.assertEqual(cliente_api(self.mesero).post(reverse("plato-disponibilidad", args=[999999])).status_code, 404)


class CrudDelAdministradorTests(DatosMenuMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.c = cliente_api(self.admin)

    def test_crear_plato(self):
        r = self.c.post(reverse("plato-list"), self.datos_plato(precio="12500,50", destacado=True), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertEqual((cuerpo["nombre"], cuerpo["precio"], cuerpo["destacado"], cuerpo["disponible"]), ("Flan", "12500.50", True, True))
        self.assertIsNone(cuerpo["imagen"])

    def test_crear_plato_y_categoria_informan_su_ubicacion(self):
        r = self.c.post(reverse("plato-list"), self.datos_plato(nombre="Natilla"), format="json")
        self.assertEqual(r["Location"], f"/api/v1/platos/{r.json()['id']}/")
        r = self.c.post(reverse("categoria-list"), {"nombre": "Postres frios", "orden": 4}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r["Location"], f"/api/v1/categorias/{r.json()['id']}/")

    def test_precio_como_numero_json(self):
        self.assertEqual(self.c.post(reverse("plato-list"), self.datos_plato(precio=8000.5), format="json").json()["precio"], "8000.50")

    def test_crear_plato_invalido_no_guarda(self):
        malos = [{"precio": "gratis"}, {"precio": -5}, {"precio": 0}, {"precio": "1e3"}, {"precio": None}, {"precio": True},
                 {"categoria": 99999}, {"categoria": self.oculta.pk}, {"nombre": "<script>"}, {"descripcion": "<b>x</b>"},
                 {"nombre": "x" * 101}, {"nombre": ""}, {"nombre": None}]
        for cambios in malos:
            r = self.c.post(reverse("plato-list"), self.datos_plato(**cambios), format="json")
            self.assertEqual(r.status_code, 400, cambios)
        self.assertFalse(Plato.objects.filter(nombre="Flan").exists())

    def test_campos_obligatorios(self):
        r = self.c.post(reverse("plato-list"), {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.json()), {"categoria", "nombre", "precio"})

    def test_editar_con_put_y_patch(self):
        url = reverse("plato-detail", args=[self.pasta.pk])
        r = self.c.put(url, self.datos_plato(categoria=self.fuertes.pk, nombre="Pasta boloñesa", precio="30000"), format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual((r.json()["nombre"], r.json()["precio"]), ("Pasta boloñesa", "30000.00"))
        r = self.c.patch(url, {"precio": "31000"}, format="json")
        self.assertEqual(r.json()["precio"], "31000.00")
        self.assertEqual(r.json()["nombre"], "Pasta boloñesa")

    def test_put_sin_campos_obligatorios_responde_400(self):
        self.assertEqual(self.c.put(reverse("plato-detail", args=[self.pasta.pk]), {"precio": "1000"}, format="json").status_code, 400)

    def test_nombre_repetido_en_la_categoria_responde_400(self):
        r = self.c.post(reverse("plato-list"), self.datos_plato(categoria=self.fuertes.pk, nombre="PASTA ALFREDO"), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("nombre", r.json())

    def test_eliminar_plato(self):
        self.assertEqual(self.c.delete(reverse("plato-detail", args=[self.brownie.pk])).status_code, 204)
        self.assertFalse(Plato.objects.filter(pk=self.brownie.pk).exists())
        self.assertEqual(self.c.delete(reverse("plato-detail", args=[self.brownie.pk])).status_code, 404)

    def test_crud_de_categoria(self):
        r = self.c.post(reverse("categoria-list"), {"nombre": "Bebidas", "orden": 5}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        pk = r.json()["id"]
        self.assertEqual(self.c.patch(reverse("categoria-detail", args=[pk]), {"nombre": "Bebidas frías"}, format="json").json()["nombre"], "Bebidas frías")
        self.assertEqual(self.c.delete(reverse("categoria-detail", args=[pk])).status_code, 204)

    def test_categoria_repetida_u_orden_invalido_responde_400(self):
        for datos in [{"nombre": "FUERTES"}, {"nombre": "Ok", "orden": 1000}, {"nombre": "Ok", "orden": "x"}, {"nombre": "<b>"}]:
            self.assertEqual(self.c.post(reverse("categoria-list"), datos, format="json").status_code, 400, datos)
        self.assertEqual(Categoria.objects.count(), 3)

    def test_no_se_elimina_una_categoria_con_platos(self):
        r = self.c.delete(reverse("categoria-detail", args=[self.fuertes.pk]))
        self.assertEqual(r.status_code, 409)
        self.assertIn("tiene platos", r.json()["detail"])
        self.assertTrue(Categoria.objects.filter(pk=self.fuertes.pk).exists())

    def test_ids_inexistentes_o_mal_formados(self):
        self.assertEqual(self.c.get(reverse("plato-detail", args=[999999])).status_code, 404)
        self.assertEqual(self.c.get("/api/v1/platos/abc/").status_code, 404)
        self.assertEqual(self.c.get("/api/v1/categorias/1%20OR%201=1/").status_code, 404)

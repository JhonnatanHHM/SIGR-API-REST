from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.caja.models import CierreCaja, Factura
from apps.pedidos.models import Estado, Pedido
from apps.pedidos.services import crear_pedido
from apps.usuarios.tests.base import cliente_api

from .base import HOY, DatosCajaMixin


class PermisosTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.factura = self.pedido_cerrado()
        self.urls_admin = [reverse("cierre-list"), reverse("factura-list"), reverse("caja-reporte-ventas")]

    def test_sin_credenciales_responde_401(self):
        for url in [reverse("caja-resumen")] + self.urls_admin + [reverse("factura-detail", args=[self.factura.pk])]:
            self.assertEqual(cliente_api().get(url).status_code, 401, url)
        self.assertEqual(cliente_api().post(reverse("cierre-list"), {}, format="json").status_code, 401)

    def test_el_cliente_no_entra_a_caja(self):
        c = cliente_api(self.cliente)
        for url in [reverse("caja-resumen")] + self.urls_admin:
            self.assertEqual(c.get(url).status_code, 403, url)
        self.assertEqual(c.post(reverse("cierre-list"), {"fecha": "2026-11-10", "efectivo_contado": "1"}, format="json").status_code, 403)

    def test_el_mesero_solo_ve_el_resumen(self):
        c = cliente_api(self.mesero)
        self.assertEqual(c.get(reverse("caja-resumen")).status_code, 200)
        for url in self.urls_admin:
            self.assertEqual(c.get(url).status_code, 403, url)
        self.assertEqual(c.post(reverse("cierre-list"), {"fecha": "2026-11-10", "efectivo_contado": "1"}, format="json").status_code, 403)
        self.assertEqual(CierreCaja.objects.count(), 0)

    def test_el_administrador_accede_a_todo(self):
        c = cliente_api(self.admin)
        for url in [reverse("caja-resumen")] + self.urls_admin:
            self.assertEqual(c.get(url).status_code, 200, url)


class ResumenTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pedido_cerrado()

    def test_el_mesero_solo_ve_el_total_del_dia(self):
        cuerpo = cliente_api(self.mesero).get(reverse("caja-resumen")).json()
        self.assertEqual(cuerpo, {"fecha": "2026-11-10", "ventas_del_dia": "65500.50"})

    def test_el_administrador_ve_el_detalle(self):
        cuerpo = cliente_api(self.admin).get(reverse("caja-resumen")).json()
        self.assertEqual((cuerpo["ventas_del_dia"], cuerpo["facturas"], cuerpo["pedidos_sin_cerrar"], cuerpo["cierre"]), ("65500.50", 1, 0, None))

    def test_el_resumen_refleja_el_cierre(self):
        cliente_api(self.admin).post(reverse("cierre-list"), {"fecha": "2026-11-10", "efectivo_contado": "65500.50"}, format="json")
        cierre = cliente_api(self.admin).get(reverse("caja-resumen")).json()["cierre"]
        self.assertEqual((cierre["resultado"], cierre["diferencia"]), ("Cuadrado", "0.00"))


class FacturacionAlCerrarPedidoTests(DatosCajaMixin, TestCase):
    def avanzar(self, pedido, usuario=None, **cuerpo):
        return cliente_api(usuario or self.mesero).post(reverse("pedido-avanzar", args=[pedido.pk]), cuerpo, format="json")

    def test_al_cerrar_el_pedido_se_emite_la_factura_una_sola_vez(self):
        pedido = crear_pedido(self.cliente, 1, "", [(self.pasta, 2)])
        for _ in range(3):
            r = self.avanzar(pedido)
            self.assertIsNone(r.json()["factura"])
        self.assertFalse(Factura.objects.exists())
        r = self.avanzar(pedido)                                   # servido -> cerrado
        self.assertEqual(r.status_code, 200, r.content)
        factura = Factura.objects.get()
        self.assertEqual((factura.pedido, factura.total, factura.emitida_por), (pedido, Decimal("56000"), self.mesero))
        self.assertEqual(r.json()["factura"], {"id": factura.pk, "numero": factura.numero, "total": "56000.00"})
        self.assertEqual(self.avanzar(pedido).status_code, 409)    # ya cerrado: no duplica
        self.assertEqual(Factura.objects.count(), 1)

    def test_el_cliente_ve_la_factura_de_su_pedido(self):
        factura = self.pedido_cerrado(cliente=self.cliente)
        r = cliente_api(self.cliente).get(reverse("pedido-detail", args=[factura.pedido_id]))
        self.assertEqual(r.json()["factura"]["numero"], factura.numero)

    def test_con_la_caja_cerrada_no_se_pueden_cerrar_pedidos(self):
        pedido = crear_pedido(self.cliente, 1, "", [(self.pasta, 1)])
        for _ in range(3):
            pedido.avanzar()                                      # queda servido
        CierreCaja.objects.create(fecha=HOY, total_ventas=0, numero_facturas=0, efectivo_contado=0, diferencia=0, cerrado_por=self.admin)
        r = self.avanzar(pedido)
        self.assertEqual(r.status_code, 409)
        self.assertIn("caja de hoy ya está cerrada", r.json()["detail"])
        pedido.refresh_from_db()
        self.assertEqual(pedido.estado, Estado.SERVIDO)
        self.assertFalse(Factura.objects.exists())


class FacturasTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.mia = self.pedido_cerrado(cliente=self.cliente)
        self.ajena = self.pedido_cerrado(cliente=self.otro_cliente)

    def test_el_cliente_ve_solo_su_factura(self):
        c = cliente_api(self.cliente)
        r = c.get(reverse("factura-detail", args=[self.mia.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["numero"], self.mia.numero)
        self.assertEqual(c.get(reverse("factura-detail", args=[self.ajena.pk])).status_code, 404)

    def test_el_personal_ve_cualquiera_con_el_detalle_del_pedido(self):
        for usuario in (self.mesero, self.admin):
            cuerpo = cliente_api(usuario).get(reverse("factura-detail", args=[self.ajena.pk])).json()
            self.assertEqual(cuerpo["total"], "65500.50")
            self.assertEqual(len(cuerpo["pedido_detalle"]["items"]), 2)

    def test_listado_solo_para_el_administrador(self):
        r = cliente_api(self.admin).get(reverse("factura-list"))
        self.assertEqual((r.json()["count"], {f["numero"] for f in r.json()["results"]}), (2, {self.mia.numero, self.ajena.numero}))

    def test_ids_inexistentes_o_mal_formados(self):
        c = cliente_api(self.admin)
        self.assertEqual(c.get(reverse("factura-detail", args=[999999])).status_code, 404)
        self.assertEqual(c.get("/api/v1/caja/facturas/abc/").status_code, 404)

    def test_las_facturas_no_se_crean_ni_modifican_por_la_api(self):
        c = cliente_api(self.admin)
        self.assertEqual(c.post(reverse("factura-list"), {}, format="json").status_code, 405)
        for metodo in ("put", "patch", "delete"):
            self.assertEqual(getattr(c, metodo)(reverse("factura-detail", args=[self.mia.pk])).status_code, 405, metodo)


class CierresTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pedido_cerrado()                                     # 65.500,50 hoy
        self.c = cliente_api(self.admin)

    def cerrar(self, **cambios):
        datos = {"fecha": "2026-11-10", "efectivo_contado": "65000", "observaciones": "Faltaron 500"}
        datos.update(cambios)
        return self.c.post(reverse("cierre-list"), datos, format="json")

    def test_cerrar_la_caja(self):
        r = self.cerrar()
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertEqual(r["Location"], f"/api/v1/caja/cierres/{cuerpo['id']}/")
        self.assertEqual((cuerpo["total_ventas"], cuerpo["diferencia"], cuerpo["resultado"], cuerpo["numero_facturas"]),
                         ("65500.50", "-500.50", "Faltante", 1))
        self.assertEqual(cuerpo["cerrado_por"], self.admin.pk)

    def test_cuadrado_sobrante_y_dia_sin_ventas(self):
        self.assertEqual(self.cerrar(efectivo_contado="65500.50", fecha="2026-11-10").json()["resultado"], "Cuadrado")
        r = self.cerrar(efectivo_contado="5000", fecha="2026-11-09").json()
        self.assertEqual((r["total_ventas"], r["resultado"], r["diferencia"]), ("0.00", "Sobrante", "5000.00"))

    def test_no_se_cierra_dos_veces_el_mismo_dia(self):
        self.cerrar()
        r = self.cerrar()
        self.assertEqual(r.status_code, 409)
        self.assertIn("ya fue cerrada", r.json()["detail"])
        self.assertEqual(CierreCaja.objects.count(), 1)

    def test_datos_invalidos_no_cierran(self):
        malos = [{"efectivo_contado": "-1"}, {"efectivo_contado": "abc"}, {"efectivo_contado": None}, {"fecha": "mañana"}, {"fecha": "2026-11-11"},
                 {"observaciones": "<script>"}, {"efectivo_contado": "1e3"}]
        for cambios in malos:
            self.assertEqual(self.cerrar(**cambios).status_code, 400, cambios)
        self.assertEqual(CierreCaja.objects.count(), 0)

    def test_no_cierra_con_pedidos_del_dia_sin_cerrar(self):
        crear_pedido(self.cliente, 2, "", [(self.pasta, 1)])
        r = self.cerrar()
        self.assertEqual(r.status_code, 400)
        self.assertIn("sin cerrar", str(r.json()))

    def test_total_diferencia_y_responsable_no_se_aceptan_de_la_peticion(self):
        r = self.cerrar(efectivo_contado="65500.50", total_ventas="1", diferencia="999", cerrado_por=self.mesero.pk)
        self.assertEqual((r.json()["total_ventas"], r.json()["diferencia"], r.json()["cerrado_por"]), ("65500.50", "0.00", self.admin.pk))

    def test_un_cierre_es_inmutable(self):
        pk = self.cerrar().json()["id"]
        for metodo in ("put", "patch", "delete"):
            self.assertEqual(getattr(self.c, metodo)(reverse("cierre-detail", args=[pk])).status_code, 405, metodo)
        self.assertEqual(self.c.get(reverse("cierre-detail", args=[pk])).json()["id"], pk)
        self.assertEqual(self.c.get(reverse("cierre-list")).json()["count"], 1)


class ReportesTests(DatosCajaMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.pedido_cerrado(dia=9)
        self.pedido_cerrado()
        self.c = cliente_api(self.admin)

    def test_por_defecto_cubre_los_ultimos_siete_dias(self):
        cuerpo = self.c.get(reverse("caja-reporte-ventas")).json()
        self.assertEqual((cuerpo["desde"], cuerpo["hasta"]), ("2026-11-04", "2026-11-10"))
        self.assertEqual((cuerpo["total_ventas"], cuerpo["facturas"], cuerpo["ticket_promedio"]), ("131001.00", 2, "65500.50"))
        self.assertEqual([(d["dia"], d["facturas"], d["total"]) for d in cuerpo["ventas_por_dia"]],
                         [("2026-11-09", 1, "65500.50"), ("2026-11-10", 1, "65500.50")])

    def test_con_rango_y_platos_mas_vendidos(self):
        cuerpo = self.c.get(reverse("caja-reporte-ventas"), {"desde": "2026-11-10", "hasta": "2026-11-10"}).json()
        self.assertEqual((cuerpo["total_ventas"], cuerpo["facturas"]), ("65500.50", 1))
        self.assertEqual(cuerpo["platos_mas_vendidos"], [
            {"plato": "Pasta", "unidades": 2, "ingresos": "56000.00"}, {"plato": "Sopa", "unidades": 1, "ingresos": "9500.50"},
        ])

    def test_rango_sin_ventas(self):
        cuerpo = self.c.get(reverse("caja-reporte-ventas"), {"desde": "2026-10-01", "hasta": "2026-10-02"}).json()
        self.assertEqual((cuerpo["total_ventas"], cuerpo["facturas"], cuerpo["ticket_promedio"], cuerpo["ventas_por_dia"]), ("0.00", 0, "0.00", []))

    def test_parametros_invalidos_o_hostiles_responden_400_y_no_tocan_la_base(self):
        casos = [{"desde": "' OR 1=1 --", "hasta": "2026-11-10"}, {"desde": "2026-11-10", "hasta": "2026-11-01"},
                 {"desde": "2020-01-01", "hasta": "2026-11-10"}, {"desde": "x; DROP TABLE caja_factura", "hasta": "y"},
                 {"hasta": "2026-12-31"}, {"desde": "01/11/2026"}]
        for params in casos:
            r = self.c.get(reverse("caja-reporte-ventas"), params)
            self.assertEqual(r.status_code, 400, params)
        self.assertEqual(Factura.objects.count(), 2)
        self.assertEqual(Pedido.objects.count(), 2)

from datetime import time

from django.test import TestCase
from django.urls import reverse

from apps.reservas.models import EstadoReserva, Reserva
from apps.usuarios.tests.base import cliente_api

from .base import DatosReservasMixin


def payload(**cambios):
    base = {"fecha": "2026-11-11", "hora": "13:00", "personas": 4, "mesa": 7, "notas": "Cumpleaños"}
    base.update(cambios)
    return base


class CrearReservaTests(DatosReservasMixin, TestCase):
    def crear(self, usuario, **cambios):
        return cliente_api(usuario).post(reverse("reserva-list"), payload(**cambios), format="json")

    def test_sin_credenciales_401_y_el_personal_no_crea_reservas(self):
        self.assertEqual(self.crear(None).status_code, 401)
        for usuario in (self.mesero, self.admin):
            self.assertEqual(self.crear(usuario).status_code, 403)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_cliente_crea_reserva_pendiente_con_location(self):
        r = self.crear(self.cliente)
        self.assertEqual(r.status_code, 201, r.content)
        cuerpo = r.json()
        self.assertEqual(r["Location"], f"/api/v1/reservas/{cuerpo['id']}/")
        self.assertEqual((cuerpo["estado"], cuerpo["fecha"], cuerpo["hora"], cuerpo["fin"]), ("pendiente", "2026-11-11", "13:00", "15:00"))
        self.assertEqual((cuerpo["mesa"], cuerpo["personas"], cuerpo["cliente"]), (7, 4, self.cliente.pk))
        self.assertTrue(cuerpo["puede_confirmarse"] and cuerpo["puede_cancelarse"] and not cuerpo["puede_completarse"])

    def test_el_cliente_y_el_estado_no_se_aceptan_de_la_peticion(self):
        r = self.crear(self.cliente, cliente=self.otro_cliente.pk, estado="confirmada")
        reserva = Reserva.objects.get()
        self.assertEqual((reserva.cliente, reserva.estado, r.status_code), (self.cliente, EstadoReserva.PENDIENTE, 201))

    def test_datos_invalidos_no_guardan(self):
        malos = [{"hora": "10:00"}, {"fecha": "ayer"}, {"personas": 99}, {"mesa": 0}, {"notas": "<b>x</b>"}, {"fecha": "2026-01-01"},
                 {"fecha": "11/11/2026"}, {"hora": None}, {"mesa": "abc"}, {"personas": [4]}]
        for cambios in malos:
            self.assertEqual(self.crear(self.cliente, **cambios).status_code, 400, cambios)
        self.assertEqual(Reserva.objects.count(), 0)

    def test_cuerpo_vacio_o_con_tipos_incorrectos_responde_400(self):
        c = cliente_api(self.cliente)
        for cuerpo in ({}, {"fecha": None, "hora": None, "personas": None, "mesa": None}, {"fecha": [], "hora": {}, "personas": "x", "mesa": "y"}):
            self.assertEqual(c.post(reverse("reserva-list"), cuerpo, format="json").status_code, 400, cuerpo)

    def test_una_mesa_ocupada_responde_409(self):
        self.reservar(cliente=self.otro_cliente, dia=11, hora=time(13, 0), mesa=7)
        r = self.crear(self.cliente, hora="14:00")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ya está reservada", r.json()["detail"])
        self.assertEqual(Reserva.objects.count(), 1)
        self.assertEqual(self.crear(self.cliente, hora="15:00").status_code, 201)         # el borde exacto es válido

    def test_un_cliente_no_puede_tener_dos_reservas_cruzadas(self):
        self.assertEqual(self.crear(self.cliente, mesa=1).status_code, 201)
        r = self.crear(self.cliente, hora="14:00", mesa=9)
        self.assertEqual(r.status_code, 409)
        self.assertIn("se cruza", r.json()["detail"])

    def test_cancelar_libera_la_mesa(self):
        reserva = self.reservar(cliente=self.cliente, dia=11, hora=time(13, 0), mesa=7)
        self.assertEqual(self.crear(self.otro_cliente, hora="14:00").status_code, 409)
        self.assertEqual(cliente_api(self.cliente).post(reverse("reserva-cancelar", args=[reserva.pk])).status_code, 200)
        self.assertEqual(self.crear(self.otro_cliente, hora="14:00").status_code, 201)


class VisibilidadTests(DatosReservasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.mia = self.reservar(cliente=self.cliente, dia=11, mesa=1)
        self.ajena = self.reservar(cliente=self.otro_cliente, dia=12, mesa=2)

    def ids(self, usuario, **params):
        r = cliente_api(usuario).get(reverse("reserva-list"), params)
        self.assertEqual(r.status_code, 200, r.content)
        return [x["id"] for x in r.json()["results"]]

    def test_sin_credenciales_responde_401(self):
        self.assertEqual(cliente_api().get(reverse("reserva-list")).status_code, 401)

    def test_cliente_solo_ve_las_suyas_y_las_ajenas_responden_404(self):
        self.assertEqual(self.ids(self.cliente), [self.mia.pk])
        c = cliente_api(self.cliente)
        self.assertEqual(c.get(reverse("reserva-detail", args=[self.mia.pk])).status_code, 200)
        self.assertEqual(c.get(reverse("reserva-detail", args=[self.ajena.pk])).status_code, 404)

    def test_el_personal_ve_todas(self):
        for usuario in (self.mesero, self.admin):
            self.assertEqual(set(self.ids(usuario)), {self.mia.pk, self.ajena.pk})

    def test_filtros(self):
        self.assertEqual(self.ids(self.mesero, mesa=2), [self.ajena.pk])
        self.assertEqual(self.ids(self.mesero, fecha="2026-11-11"), [self.mia.pk])
        self.ajena.cancelar()
        self.assertEqual(self.ids(self.mesero, estado="vigentes"), [self.mia.pk])
        self.assertEqual(self.ids(self.mesero, estado="cancelada"), [self.ajena.pk])

    def test_filtros_hostiles_responden_400_y_no_tocan_la_base(self):
        c = cliente_api(self.mesero)
        for params in [{"estado": "' OR 1=1 --"}, {"fecha": "2026-11-11' OR '1'='1"}, {"fecha": "11/11/2026"}, {"mesa": "1; DROP TABLE reservas_reserva"}, {"mesa": -1}]:
            self.assertEqual(c.get(reverse("reserva-list"), params).status_code, 400, params)
        self.assertEqual(Reserva.objects.count(), 2)

    def test_paginacion_e_ids_inexistentes(self):
        r = cliente_api(self.mesero).get(reverse("reserva-list"), {"page_size": 1}).json()
        self.assertEqual((r["count"], len(r["results"])), (2, 1))
        self.assertEqual(cliente_api(self.mesero).get(reverse("reserva-detail", args=[999999])).status_code, 404)
        self.assertEqual(cliente_api(self.mesero).get("/api/v1/reservas/abc/").status_code, 404)


class CambioDeEstadoTests(DatosReservasMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.reserva = self.reservar(cliente=self.cliente)

    def url(self, accion, pk=None):
        return reverse(f"reserva-{accion}", args=[pk or self.reserva.pk])

    def refrescar(self):
        self.reserva.refresh_from_db()
        return self.reserva.estado

    def test_visitante_401_y_cliente_403_en_confirmar_y_completar(self):
        for accion in ("confirmar", "completar"):
            self.assertEqual(cliente_api().post(self.url(accion)).status_code, 401)
            self.assertEqual(cliente_api(self.cliente).post(self.url(accion)).status_code, 403)
        self.assertEqual(self.refrescar(), EstadoReserva.PENDIENTE)

    def test_el_personal_confirma_y_completa(self):
        r = cliente_api(self.mesero).post(self.url("confirmar"))
        self.assertEqual((r.status_code, r.json()["estado"]), (200, "confirmada"))
        r = cliente_api(self.admin).post(self.url("completar"))
        self.assertEqual((r.status_code, r.json()["estado"]), (200, "completada"))

    def test_no_se_completa_una_pendiente_ni_se_confirma_una_cancelada(self):
        self.assertEqual(cliente_api(self.mesero).post(self.url("completar")).status_code, 409)
        cliente_api(self.mesero).post(self.url("cancelar"))
        self.assertEqual(cliente_api(self.mesero).post(self.url("confirmar")).status_code, 409)
        self.assertEqual(self.refrescar(), EstadoReserva.CANCELADA)

    def test_pantalla_desactualizada_o_estado_invalido(self):
        cliente_api(self.mesero).post(self.url("confirmar"))
        self.assertEqual(cliente_api(self.admin).post(self.url("cancelar"), {"desde": "pendiente"}, format="json").status_code, 409)
        self.assertEqual(cliente_api(self.admin).post(self.url("completar"), {"desde": "volando"}, format="json").status_code, 400)
        self.assertEqual(self.refrescar(), EstadoReserva.CONFIRMADA)

    def test_desde_correcto_aplica_el_cambio(self):
        r = cliente_api(self.mesero).post(self.url("confirmar"), {"desde": "pendiente"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_el_cliente_cancela_la_suya_pero_no_la_ajena(self):
        ajena = self.reservar(cliente=self.otro_cliente, dia=12, mesa=9)
        self.assertEqual(cliente_api(self.cliente).post(self.url("cancelar", ajena.pk)).status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, EstadoReserva.PENDIENTE)
        self.assertEqual(cliente_api(self.cliente).post(self.url("cancelar")).json()["estado"], "cancelada")

    def test_el_personal_cancela_cualquiera_y_una_cancelada_queda_firme(self):
        cliente_api(self.mesero).post(self.url("cancelar"))
        self.assertEqual(cliente_api(self.mesero).post(self.url("cancelar")).status_code, 409)
        self.assertEqual(self.refrescar(), EstadoReserva.CANCELADA)

    def test_las_acciones_no_aceptan_get_y_los_ids_inexistentes_responden_404(self):
        for accion in ("confirmar", "completar", "cancelar"):
            self.assertEqual(cliente_api(self.admin).get(self.url(accion)).status_code, 405)
            self.assertEqual(cliente_api(self.admin).post(self.url(accion, 999999)).status_code, 404)

"""Recorre la API de punta a punta, como lo haría un cliente HTTP real (Postman)."""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.caja.models import CierreCaja, Factura
from apps.menu.models import Plato
from apps.pedidos.models import Estado, Pedido
from apps.reservas.models import EstadoReserva, Reserva
from apps.usuarios.models import Rol, Usuario

from .base import CLAVE, EntornoMixin, cliente_con_token


class FlujoCompletoTests(EntornoMixin, TestCase):
    def test_de_la_cuenta_nueva_hasta_el_reporte_de_ventas(self):
        # 1. Una persona nueva se registra y recibe su token como cliente.
        r = APIClient().post("/api/v1/auth/registro/", {
            "first_name": "Laura", "last_name": "Gómez", "email": "laura@ejemplo.com", "telefono": "300 123 4567",
            "password": CLAVE, "password_confirmacion": CLAVE,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        laura = Usuario.objects.get(email="laura@ejemplo.com")
        self.assertEqual((laura.rol, laura.telefono), (Rol.CLIENTE, "3001234567"))
        cliente = cliente_con_token(r.json()["token"])

        # 2. Cualquiera ve la carta, sin credenciales.
        carta = APIClient().get("/api/v1/platos/").json()
        self.assertIn("Bandeja paisa", [p["nombre"] for p in carta["results"]])

        # 3. Reserva una mesa: queda pendiente.
        r = cliente.post("/api/v1/reservas/", {"fecha": "2026-11-12", "hora": "13:00", "personas": 4, "mesa": 6, "notas": "Cumpleaños"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        reserva = Reserva.objects.get()
        self.assertEqual((reserva.cliente, reserva.estado), (laura, EstadoReserva.PENDIENTE))

        # 4. Hace un pedido: 2 bandejas y 1 limonada.
        bandeja, limonada = Plato.objects.get(nombre="Bandeja paisa"), Plato.objects.get(nombre="Limonada de coco")
        r = cliente.post("/api/v1/pedidos/", {"mesa": 6, "notas": "Sin cebolla", "items": [
            {"plato": bandeja.pk, "cantidad": 2}, {"plato": limonada.pk, "cantidad": 1}]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        pedido = Pedido.objects.get()
        self.assertEqual((pedido.cliente, pedido.estado, str(pedido.total)), (laura, Estado.PENDIENTE, "77000.00"))
        self.assertEqual(r.json()["total"], "77000.00")

        # 5. El mesero inicia sesión, confirma la reserva y lleva el pedido hasta cerrarlo.
        mesero = self.ingresar("mes@ejemplo.com")
        self.assertEqual(mesero.post(f"/api/v1/reservas/{reserva.pk}/confirmar/", {"desde": "pendiente"}, format="json").json()["estado"], "confirmada")
        for esperado in ("en_preparacion", "listo", "servido", "cerrado"):
            r = mesero.post(f"/api/v1/pedidos/{pedido.pk}/avanzar/", {}, format="json")
            self.assertEqual((r.status_code, r.json()["estado"]), (200, esperado), r.content)

        # 6. Al cerrarse el pedido se emitió su factura, y la clienta puede verla.
        factura = Factura.objects.get()
        self.assertEqual((factura.pedido, str(factura.total), factura.emitida_por), (pedido, "77000.00", self.mesero))
        self.assertEqual(r.json()["factura"]["numero"], factura.numero)
        detalle = cliente.get(f"/api/v1/caja/facturas/{factura.pk}/").json()
        self.assertEqual((detalle["numero"], detalle["total"], len(detalle["pedido_detalle"]["items"])), (factura.numero, "77000.00", 2))

        # 7. El mesero ve el total del día, pero no puede ver reportes ni cerrar la caja.
        self.assertEqual(mesero.get("/api/v1/caja/resumen/").json(), {"fecha": "2026-11-10", "ventas_del_dia": "77000.00"})
        self.assertEqual(mesero.get("/api/v1/caja/reportes/ventas/").status_code, 403)
        self.assertEqual(mesero.post("/api/v1/caja/cierres/", {"fecha": "2026-11-10", "efectivo_contado": "1"}, format="json").status_code, 403)

        # 8. El administrador cierra la caja: el efectivo contado cuadra con las ventas.
        admin = self.ingresar("adm@ejemplo.com")
        r = admin.post("/api/v1/caja/cierres/", {"fecha": "2026-11-10", "efectivo_contado": "77000", "observaciones": ""}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual((r.json()["total_ventas"], r.json()["diferencia"], r.json()["resultado"]), ("77000.00", "0.00", "Cuadrado"))
        self.assertEqual(CierreCaja.objects.count(), 1)

        # 9. El reporte muestra la venta y el plato más vendido.
        reporte = admin.get("/api/v1/caja/reportes/ventas/").json()
        self.assertEqual((reporte["total_ventas"], reporte["facturas"]), ("77000.00", 1))
        self.assertEqual(reporte["platos_mas_vendidos"][0], {"plato": "Bandeja paisa", "unidades": 2, "ingresos": "68000.00"})

        # 10. Con la caja cerrada ya no se pueden cerrar más pedidos ese día.
        r = cliente.post("/api/v1/pedidos/", {"mesa": 2, "items": [{"plato": limonada.pk, "cantidad": 1}]}, format="json")
        segundo = Pedido.objects.get(pk=r.json()["id"])
        for _ in range(3):
            segundo.avanzar()
        r = mesero.post(f"/api/v1/pedidos/{segundo.pk}/avanzar/", {}, format="json")
        self.assertEqual(r.status_code, 409)
        segundo.refresh_from_db()
        self.assertEqual(segundo.estado, Estado.SERVIDO)
        self.assertEqual(Factura.objects.count(), 1)

    def test_el_cliente_cancela_su_pedido_y_no_se_factura(self):
        cliente = self.ingresar("cli@ejemplo.com")
        bandeja = Plato.objects.get(nombre="Bandeja paisa")
        r = cliente.post("/api/v1/pedidos/", {"mesa": 3, "items": [{"plato": bandeja.pk, "cantidad": 1}]}, format="json")
        self.assertEqual(cliente.post(f"/api/v1/pedidos/{r.json()['id']}/cancelar/").json()["estado"], "cancelado")
        self.assertFalse(Factura.objects.exists())

    def test_un_administrador_da_de_alta_a_un_mesero_que_ya_puede_trabajar(self):
        admin = self.ingresar("adm@ejemplo.com")
        r = admin.post("/api/v1/usuarios/", {
            "first_name": "Mario", "last_name": "Mesa", "email": "mario@ejemplo.com", "rol": "mesero",
            "password": CLAVE, "password_confirmacion": CLAVE,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        mario = self.ingresar("mario@ejemplo.com")
        self.assertEqual(mario.get("/api/v1/caja/resumen/").status_code, 200)
        self.assertEqual(mario.get("/api/v1/usuarios/").status_code, 403)

    def test_un_plato_agotado_sale_de_la_carta_y_no_se_puede_pedir(self):
        mesero = self.ingresar("mes@ejemplo.com")
        brownie = Plato.objects.get(nombre="Brownie con helado")
        self.assertFalse(mesero.post(f"/api/v1/platos/{brownie.pk}/disponibilidad/").json()["disponible"])
        nombres = [p["nombre"] for p in APIClient().get("/api/v1/platos/").json()["results"]]
        self.assertNotIn("Brownie con helado", nombres)
        cliente = self.ingresar("cli@ejemplo.com")
        r = cliente.post("/api/v1/pedidos/", {"mesa": 1, "items": [{"plato": brownie.pk, "cantidad": 2}]}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Pedido.objects.exists())

    def test_cerrar_sesion_invalida_el_token(self):
        cliente = self.ingresar("cli@ejemplo.com")
        self.assertEqual(cliente.get("/api/v1/auth/yo/").status_code, 200)
        self.assertEqual(cliente.post("/api/v1/auth/logout/").status_code, 204)
        self.assertEqual(cliente.get("/api/v1/auth/yo/").status_code, 401)

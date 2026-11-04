from datetime import date, datetime
from unittest.mock import patch

from django.utils import timezone

from apps.caja.models import Factura
from apps.caja.services import emitir_factura
from apps.menu.models import Categoria, Plato
from apps.pedidos.services import crear_pedido
from apps.usuarios.models import Rol, Usuario

CLAVE = "Contr4seña-Muy-Segura!"
HOY = date(2026, 11, 10)
AHORA = timezone.make_aware(datetime(2026, 11, 10, 18, 0))      # el reloj de las pruebas queda fijo


def crear_usuario(email, rol):
    return Usuario.objects.create_user(email, CLAVE, first_name="Nombre", last_name="Apellido", rol=rol)


class DatosCajaMixin:
    def setUp(self):
        parche = patch("django.utils.timezone.now", return_value=AHORA)
        parche.start()
        self.addCleanup(parche.stop)
        self.cliente = crear_usuario("cli@ejemplo.com", Rol.CLIENTE)
        self.otro_cliente = crear_usuario("otro@ejemplo.com", Rol.CLIENTE)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)
        categoria = Categoria.objects.create(nombre="Fuertes")
        self.pasta = Plato.objects.create(categoria=categoria, nombre="Pasta", precio="28000")
        self.sopa = Plato.objects.create(categoria=categoria, nombre="Sopa", precio="9500.50")

    def pedido_cerrado(self, cliente=None, items=None, dia=None):
        """Crea un pedido ya cerrado y facturado; `dia` mueve la fecha de la factura (sin tocar el reloj)."""
        pedido = crear_pedido(cliente or self.cliente, 3, "", items or [(self.pasta, 2), (self.sopa, 1)])
        for _ in range(4):
            pedido.avanzar()
        factura = emitir_factura(pedido, self.mesero)
        if dia:
            Factura.objects.filter(pk=factura.pk).update(emitida=timezone.make_aware(datetime(2026, 11, dia, 12, 0)))
            factura.refresh_from_db()
        return factura

from apps.menu.models import Categoria, Plato
from apps.usuarios.models import Rol
from apps.usuarios.tests.base import cliente_api, crear_usuario  # noqa: F401  (se reexportan para las pruebas del módulo)


class DatosPedidosMixin:
    """Usuarios de cada rol y un menú con un plato agotado y otro en una categoría oculta."""

    def setUp(self):
        super().setUp()
        self.cliente = crear_usuario("cli@ejemplo.com", Rol.CLIENTE)
        self.otro_cliente = crear_usuario("otro@ejemplo.com", Rol.CLIENTE)
        self.mesero = crear_usuario("mes@ejemplo.com", Rol.MESERO)
        self.admin = crear_usuario("adm@ejemplo.com", Rol.ADMINISTRADOR)
        self.fuertes = Categoria.objects.create(nombre="Fuertes", orden=1)
        self.oculta = Categoria.objects.create(nombre="Oculta", orden=2, activa=False)
        self.pasta = Plato.objects.create(categoria=self.fuertes, nombre="Pasta alfredo", precio="28000")
        self.sopa = Plato.objects.create(categoria=self.fuertes, nombre="Sopa", precio="9500.50")
        self.agotado = Plato.objects.create(categoria=self.fuertes, nombre="Salmón", precio="42500", disponible=False)
        self.secreto = Plato.objects.create(categoria=self.oculta, nombre="Secreto", precio="1000")

    def datos(self, **cambios):
        base = {"mesa": 5, "notas": "Sin cebolla", "items": [{"plato": self.pasta.pk, "cantidad": 2}, {"plato": self.sopa.pk, "cantidad": 1}]}
        base.update(cambios)
        return base

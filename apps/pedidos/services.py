from django.db import transaction

from .models import ItemPedido, Pedido


@transaction.atomic
def crear_pedido(usuario, mesa, notas, items):
    """Crea un pedido con sus ítems. El precio siempre se toma de la base de datos, nunca del cliente.

    `items` es una lista de (plato, cantidad). Si el pedido lo hace un cliente queda asociado a su cuenta;
    si lo registra el personal para una mesa, queda sin cliente.
    """
    pedido = Pedido.objects.create(
        cliente=usuario if usuario.es_cliente else None,
        creado_por=usuario,
        mesa=mesa,
        notas=notas,
    )
    ItemPedido.objects.bulk_create(
        ItemPedido(pedido=pedido, plato=plato, cantidad=cantidad, precio_unitario=plato.precio)
        for plato, cantidad in items
    )
    return pedido

"""Carga categorías y platos de ejemplo (idempotente). Uso: python manage.py cargar_menu_demo"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.menu.models import Categoria, Plato

DEMO = {
    ("Entradas", 1): [
        ("Empanadas de carne", "Tres empanadas crocantes con ají de la casa.", "9500"),
        ("Crema de tomate", "Con albahaca fresca y crotones.", "12000"),
    ],
    ("Platos fuertes", 2): [
        ("Bandeja paisa", "Frijoles, arroz, chicharrón, carne molida, huevo, plátano y arepa.", "34000"),
        ("Salmón a la plancha", "Con puré de papa y vegetales salteados.", "42500"),
        ("Pasta alfredo", "Fetuccini en salsa cremosa de queso parmesano.", "28000"),
    ],
    ("Postres", 3): [
        ("Brownie con helado", "Chocolate caliente y helado de vainilla.", "14500"),
        ("Tres leches", "Bizcocho húmedo con crema chantilly.", "12500"),
    ],
    ("Bebidas", 4): [
        ("Limonada de coco", "Cremosa y bien fría.", "9000"),
        ("Jugo natural", "Mora, lulo o maracuyá, en agua o en leche.", "7500"),
    ],
}


class Command(BaseCommand):
    help = "Crea categorías y platos de demostración"

    def handle(self, *args, **opciones):
        creados = 0
        for (nombre, orden), platos in DEMO.items():
            categoria, _ = Categoria.objects.get_or_create(nombre=nombre, defaults={"orden": orden})
            for plato, descripcion, precio in platos:
                _, nuevo = Plato.objects.get_or_create(
                    categoria=categoria, nombre=plato, defaults={"descripcion": descripcion, "precio": Decimal(precio)}
                )
                creados += nuevo
        self.stdout.write(self.style.SUCCESS(f"Menú de demostración listo ({creados} platos nuevos)."))

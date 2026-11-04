"""Permisos por rol. Toda vista protegida de la API debe usar uno de ellos (o IsAuthenticated).

- Sin credenciales válidas: 401.
- Con credenciales pero sin el rol requerido: 403.
"""
from rest_framework.permissions import BasePermission

from .models import Rol


class RolRequerido(BasePermission):
    roles = ()
    message = "Tu rol no tiene permiso para esta acción."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and usuario.is_active and usuario.rol in self.roles)


class EsCliente(RolRequerido):
    roles = (Rol.CLIENTE,)


class EsPersonal(RolRequerido):
    """Personal del restaurante: meseros y administradores."""

    roles = (Rol.MESERO, Rol.ADMINISTRADOR)


class EsAdministrador(RolRequerido):
    roles = (Rol.ADMINISTRADOR,)

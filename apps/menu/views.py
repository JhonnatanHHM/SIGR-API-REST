from django.db.models import ProtectedError, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.comun.excepciones import Conflicto
from apps.comun.ubicacion import UbicacionAlCrearMixin
from apps.usuarios.permisos import EsAdministrador, EsPersonal

from .models import Categoria, Plato
from .serializers import CategoriaSerializer, FiltroPlatoSerializer, PlatoSerializer

MAX_DESTACADOS = 6


def _es_personal(usuario):
    return bool(usuario.is_authenticated and usuario.es_personal)


@extend_schema_view(
    list=extend_schema(summary="Listar categorías (el público ve solo las activas)"),
    retrieve=extend_schema(summary="Ver una categoría"),
    create=extend_schema(summary="Crear una categoría (administrador)"),
    update=extend_schema(summary="Reemplazar una categoría (administrador)"),
    partial_update=extend_schema(summary="Editar una categoría (administrador)"),
    destroy=extend_schema(summary="Eliminar una categoría (administrador); 409 si tiene platos"),
)
@extend_schema(tags=["Menú: categorías"])
class CategoriaViewSet(UbicacionAlCrearMixin, viewsets.ModelViewSet):
    serializer_class = CategoriaSerializer

    def get_permissions(self):
        return [AllowAny()] if self.action in ("list", "retrieve") else [EsAdministrador()]

    def get_queryset(self):
        consulta = Categoria.objects.all()
        usuario = self.request.user
        if usuario.is_authenticated and usuario.es_administrador:
            return consulta
        return consulta.filter(activa=True)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise Conflicto("No se puede eliminar: la categoría tiene platos. Muévelos o elimínalos primero.")


@extend_schema_view(
    list=extend_schema(
        summary="Listar platos (carta)",
        description="El público y los clientes ven solo platos disponibles de categorías activas; el personal ve todos.",
        parameters=[
            OpenApiParameter("q", str, description="Texto a buscar en nombre o descripción (máx. 100)."),
            OpenApiParameter("categoria", int, description="Id de la categoría."),
            OpenApiParameter("disponible", str, enum=["true", "false"], description="Solo el personal."),
        ],
    ),
    retrieve=extend_schema(summary="Ver un plato"),
    create=extend_schema(summary="Crear un plato, con foto opcional (administrador)"),
    update=extend_schema(summary="Reemplazar un plato (administrador)"),
    partial_update=extend_schema(summary="Editar un plato (administrador)"),
    destroy=extend_schema(summary="Eliminar un plato (administrador); 409 si tiene pedidos"),
)
@extend_schema(tags=["Menú: platos"])
class PlatoViewSet(UbicacionAlCrearMixin, viewsets.ModelViewSet):
    serializer_class = PlatoSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "destacados"):
            return [AllowAny()]
        if self.action == "disponibilidad":
            return [EsPersonal()]
        return [EsAdministrador()]

    def _publicos(self):
        return Plato.objects.filter(disponible=True, categoria__activa=True).select_related("categoria")

    def get_queryset(self):
        consulta = Plato.objects.select_related("categoria")
        if not _es_personal(self.request.user):
            return self._publicos()
        if self.action != "list":
            return consulta
        filtros = FiltroPlatoSerializer(data=self.request.query_params)
        filtros.is_valid(raise_exception=True)
        return self._filtrar(consulta, filtros.validated_data, con_disponibilidad=True)

    def list(self, request, *args, **kwargs):
        if not _es_personal(request.user):
            filtros = FiltroPlatoSerializer(data=request.query_params)
            filtros.is_valid(raise_exception=True)
            pagina = self.paginate_queryset(self._filtrar(self._publicos(), filtros.validated_data, con_disponibilidad=False))
            return self.get_paginated_response(self.get_serializer(pagina, many=True).data)
        return super().list(request, *args, **kwargs)

    @staticmethod
    def _filtrar(consulta, datos, con_disponibilidad):
        if datos.get("q"):
            consulta = consulta.filter(Q(nombre__icontains=datos["q"]) | Q(descripcion__icontains=datos["q"]))
        if datos.get("categoria"):
            consulta = consulta.filter(categoria=datos["categoria"])
        if con_disponibilidad and datos.get("disponible"):
            consulta = consulta.filter(disponible=datos["disponible"] == "true")
        return consulta

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise Conflicto("No se puede eliminar: el plato tiene pedidos asociados. Márcalo como agotado.")

    @extend_schema(
        summary="Platos destacados del inicio (máximo 6)",
        responses=PlatoSerializer(many=True),
    )
    @action(detail=False, methods=["get"])
    def destacados(self, request):
        disponibles = self._publicos()
        platos = list(disponibles.filter(destacado=True)[:MAX_DESTACADOS])
        if not platos:    # sin destacados marcados: se muestran los primeros, con foto primero
            platos = sorted(disponibles[:30], key=lambda plato: not plato.imagen)[:MAX_DESTACADOS]
        return Response(self.get_serializer(platos, many=True).data)

    @extend_schema(
        summary="Alternar la disponibilidad de un plato (personal)",
        request=None,
        responses=PlatoSerializer,
    )
    @action(detail=True, methods=["post"])
    def disponibilidad(self, request, pk=None):
        plato = self.get_object()
        plato.disponible = not plato.disponible
        plato.save(update_fields=["disponible", "actualizado"])
        return Response(self.get_serializer(plato).data, status=status.HTTP_200_OK)

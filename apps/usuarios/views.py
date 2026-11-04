from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Rol, Usuario
from .permisos import EsAdministrador
from .serializers import (
    FiltroUsuarioSerializer, LoginSerializer, PerfilSerializer, PersonalSerializer, RegistroSerializer,
    SesionSerializer, UsuarioSerializer,
)


def _sesion(usuario):
    token, _ = Token.objects.get_or_create(user=usuario)
    return {"token": token.key, "usuario": UsuarioSerializer(usuario).data}


class RegistroView(APIView):
    """Crea una cuenta de cliente y devuelve su token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Autenticación"], summary="Registrar un cliente", request=RegistroSerializer,
                   responses={201: SesionSerializer})
    def post(self, request):
        serializador = RegistroSerializer(data=request.data)
        serializador.is_valid(raise_exception=True)
        usuario = serializador.crear_usuario()
        return Response(_sesion(usuario), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Inicia sesión con correo y contraseña y devuelve el token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Autenticación"], summary="Iniciar sesión", request=LoginSerializer,
                   responses={200: SesionSerializer})
    def post(self, request):
        serializador = LoginSerializer(data=request.data, context={"request": request})
        serializador.is_valid(raise_exception=True)
        return Response(_sesion(serializador.validated_data["usuario"]))


class LogoutView(APIView):
    """Cierra la sesión: el token deja de ser válido."""

    @extend_schema(tags=["Autenticación"], summary="Cerrar sesión", request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class YoView(RetrieveUpdateAPIView):
    """Datos de la cuenta autenticada; se pueden editar el nombre, el apellido y el teléfono."""

    serializer_class = PerfilSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    @extend_schema(tags=["Autenticación"], summary="Ver mi cuenta")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=["Autenticación"], summary="Editar mi cuenta")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


@extend_schema(tags=["Usuarios"])
class UsuarioViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Administración de usuarios (solo administrador): listar con búsqueda, ver y dar de alta personal."""

    queryset = Usuario.objects.all()
    permission_classes = [EsAdministrador]

    def get_serializer_class(self):
        return PersonalSerializer if self.action == "create" else UsuarioSerializer

    def get_queryset(self):
        consulta = Usuario.objects.all().order_by("first_name", "last_name", "email")
        if self.action != "list":
            return consulta
        filtros = FiltroUsuarioSerializer(data=self.request.query_params)
        filtros.is_valid(raise_exception=True)          # filtro inválido: 400 con el detalle, nunca una consulta
        texto, rol = filtros.validated_data.get("q"), filtros.validated_data.get("rol")
        if texto:
            consulta = consulta.filter(
                Q(first_name__icontains=texto) | Q(last_name__icontains=texto) | Q(email__icontains=texto)
            )
        if rol:
            consulta = consulta.filter(rol=rol)
        return consulta

    @extend_schema(
        summary="Listar usuarios",
        parameters=[
            OpenApiParameter("q", str, description="Texto a buscar en nombre, apellido o correo (máx. 100)."),
            OpenApiParameter("rol", str, enum=[r.value for r in Rol], description="Filtra por rol."),
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Ver un usuario")
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(summary="Dar de alta personal (mesero o administrador)", request=PersonalSerializer,
                   responses={201: UsuarioSerializer})
    def create(self, request, *args, **kwargs):
        serializador = PersonalSerializer(data=request.data)
        serializador.is_valid(raise_exception=True)
        usuario = serializador.crear_usuario()
        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)

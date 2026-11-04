"""Serializadores de cuentas. Cada campo se normaliza y valida antes de llegar a la base de datos."""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import RegexValidator
from rest_framework import serializers
from rest_framework import status
from rest_framework.exceptions import APIException

from apps.comun.campos import TextoField
from apps.comun.validators import limpiar_espacios

from .models import Rol, Usuario
from .validators import normalizar_telefono, validar_nombre, validar_telefono

ROLES_PERSONAL = [(Rol.MESERO, "Mesero"), (Rol.ADMINISTRADOR, "Administrador")]


class CredencialesInvalidas(APIException):
    """Ingreso fallido: siempre 401, aunque el endpoint de ingreso no tenga autenticación previa."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Credenciales inválidas."
    default_code = "credenciales_invalidas"


class UsuarioSerializer(serializers.ModelSerializer):
    """Datos públicos de una cuenta (solo lectura)."""

    class Meta:
        model = Usuario
        fields = ("id", "email", "first_name", "last_name", "telefono", "rol", "is_active", "date_joined")
        read_only_fields = fields


class TelefonoField(serializers.CharField):
    """Teléfono opcional: se quitan espacios, guiones y paréntesis antes de validar (7 a 15 dígitos, + opcional)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        kwargs.setdefault("max_length", 40)
        super().__init__(**kwargs)
        self.validators.append(validar_telefono)

    def to_internal_value(self, data):
        return normalizar_telefono(super().to_internal_value(data))

    def run_validators(self, value):
        if value == "":              # el teléfono es opcional
            return
        super().run_validators(value)


class RegistroSerializer(serializers.Serializer):
    """Registro público: SIEMPRE crea un cliente; el rol nunca se acepta desde la petición."""

    first_name = TextoField(max_length=60, validators=[validar_nombre])
    last_name = TextoField(max_length=60, validators=[validar_nombre])
    email = serializers.EmailField(max_length=254)
    telefono = TelefonoField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)
    password_confirmacion = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate_email(self, valor):
        correo = valor.strip().lower()
        if Usuario.objects.filter(email__iexact=correo).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo electrónico.", code="unique")
        return correo

    def validate(self, datos):
        if datos["password"] != datos["password_confirmacion"]:
            raise serializers.ValidationError({"password_confirmacion": "Las contraseñas no coinciden."})
        candidato = Usuario(email=datos["email"], first_name=datos["first_name"], last_name=datos["last_name"])
        try:
            validate_password(datos["password"], candidato)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": list(error.messages)})
        return datos

    def crear_usuario(self, rol=Rol.CLIENTE):
        datos = self.validated_data
        return Usuario.objects.create_user(
            email=datos["email"], password=datos["password"], first_name=datos["first_name"],
            last_name=datos["last_name"], telefono=datos.get("telefono", ""), rol=rol,
        )


class PersonalSerializer(RegistroSerializer):
    """Alta de personal (mesero o administrador) hecha por un administrador."""

    rol = serializers.ChoiceField(choices=ROLES_PERSONAL)

    def crear_usuario(self, rol=None):
        return super().crear_usuario(rol=self.validated_data["rol"])


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=128)

    def validate(self, datos):
        usuario = authenticate(
            request=self.context.get("request"), username=datos["email"].strip().lower(), password=datos["password"]
        )
        if usuario is None:
            raise CredencialesInvalidas()
        datos["usuario"] = usuario
        return datos


class SesionSerializer(serializers.Serializer):
    """Respuesta de registro e ingreso: el token que se envía en `Authorization: Token <token>` y la cuenta."""

    token = serializers.CharField()
    usuario = UsuarioSerializer()


class PerfilSerializer(serializers.ModelSerializer):
    """El usuario solo edita su nombre, apellido y teléfono; el correo y el rol son de solo lectura."""

    first_name = TextoField(max_length=60, validators=[validar_nombre])
    last_name = TextoField(max_length=60, validators=[validar_nombre])
    telefono = TelefonoField()

    class Meta:
        model = Usuario
        fields = ("id", "email", "first_name", "last_name", "telefono", "rol")
        read_only_fields = ("id", "email", "rol")


class FiltroUsuarioSerializer(serializers.Serializer):
    """Filtros del listado de usuarios: solo caracteres de texto razonables, nunca se arma SQL con ellos."""

    q = serializers.CharField(
        required=False, allow_blank=True, max_length=100,
        validators=[RegexValidator(r"^[\w\s@.+'\-]*$", "La búsqueda contiene caracteres no permitidos.")],
    )
    rol = serializers.ChoiceField(required=False, choices=Rol.choices)

    def validate_q(self, valor):
        return limpiar_espacios(valor)

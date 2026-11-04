from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

from .validators import validar_nombre, validar_telefono


class Rol(models.TextChoices):
    CLIENTE = "cliente", "Cliente"
    MESERO = "mesero", "Mesero"
    ADMINISTRADOR = "administrador", "Administrador"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("rol", Rol.CLIENTE)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra["rol"] = Rol.ADMINISTRADOR
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Un superusuario debe tener is_staff e is_superuser en True.")
        return self._crear(email, password, **extra)


class Usuario(AbstractUser):
    """Usuario del sistema: se identifica con su correo y tiene un rol."""

    username = None
    first_name = models.CharField("nombre", max_length=60, validators=[validar_nombre])
    last_name = models.CharField("apellido", max_length=60, validators=[validar_nombre])
    email = models.EmailField(
        "correo electrónico",
        max_length=254,
        unique=True,
        error_messages={"unique": "Ya existe una cuenta con este correo electrónico."},
    )
    telefono = models.CharField("teléfono", max_length=16, blank=True, validators=[validar_telefono])
    rol = models.CharField("rol", max_length=15, choices=Rol.choices, default=Rol.CLIENTE)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["first_name", "last_name"]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre_completo} ({self.email})"

    @property
    def nombre_completo(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def es_cliente(self):
        return self.rol == Rol.CLIENTE

    @property
    def es_mesero(self):
        return self.rol == Rol.MESERO

    @property
    def es_personal(self):
        """Personal del restaurante: meseros y administradores."""
        return self.rol in (Rol.MESERO, Rol.ADMINISTRADOR)

    @property
    def es_administrador(self):
        return self.rol == Rol.ADMINISTRADOR

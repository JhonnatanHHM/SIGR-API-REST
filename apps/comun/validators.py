"""Validadores y normalizadores compartidos por todos los módulos."""
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

# Rango de mesas del restaurante (lo comparten pedidos y reservas)
MESA_MIN = 1
MESA_MAX = 99


def limpiar_espacios(valor):
    """Quita espacios al inicio y al final y colapsa los espacios (y saltos de línea) repetidos."""
    return " ".join((valor or "").split())


validar_nombre_comercial = RegexValidator(
    regex=r"^\w[\w ,.'&()/\-]*$",
    message="Usa solo letras, números, espacios y los signos , . ' & ( ) / -",
    code="nombre_invalido",
)

# Formato real de la imagen -> extensiones que le corresponden. SVG queda fuera a propósito: puede llevar scripts.
EXTENSIONES_POR_FORMATO = {"JPEG": {"jpg", "jpeg"}, "PNG": {"png"}, "WEBP": {"webp"}}
EXTENSIONES_IMAGEN = {ext for extensiones in EXTENSIONES_POR_FORMATO.values() for ext in extensiones}
TAMANO_MAX_IMAGEN = 2 * 1024 * 1024                         # 2 MB
LADO_MAX_IMAGEN = 4000                                      # píxeles


def validar_imagen(archivo):
    """Acepta solo fotos JPG, PNG o WebP reales, de hasta 2 MB y 4000 px por lado.

    No se fía del nombre ni del tipo que declara el navegador: abre el contenido con Pillow, comprueba que
    su formato real coincida con la extensión y revisa sus dimensiones. Los archivos ya guardados no se
    vuelven a revisar.
    """
    from PIL import Image

    if getattr(archivo, "_committed", False):
        return
    nombre = (archivo.name or "").lower()
    extension = nombre.rsplit(".", 1)[-1] if "." in nombre else ""
    if extension not in EXTENSIONES_IMAGEN:
        raise ValidationError("Sube una foto en formato JPG, PNG o WebP.", code="imagen_extension")
    if archivo.size > TAMANO_MAX_IMAGEN:
        raise ValidationError("La foto no puede pesar más de 2 MB.", code="imagen_pesada")
    try:
        archivo.seek(0)
        with Image.open(archivo) as imagen:
            formato, (ancho, alto) = imagen.format, imagen.size
            imagen.verify()
    except Exception:
        raise ValidationError("El archivo no es una imagen válida.", code="imagen_invalida")
    finally:
        archivo.seek(0)
    if extension not in EXTENSIONES_POR_FORMATO.get(formato, set()):
        raise ValidationError("El contenido del archivo no corresponde a su extensión (JPG, PNG o WebP).", code="imagen_formato")
    if max(ancho, alto) > LADO_MAX_IMAGEN:
        raise ValidationError(f"La foto no puede superar {LADO_MAX_IMAGEN} píxeles por lado.", code="imagen_grande")


validar_texto_libre = RegexValidator(
    regex=r"^[^<>\x00-\x08\x0b-\x1f\x7f]*$",
    message="El texto contiene caracteres no permitidos (< >, o de control).",
    code="texto_invalido",
)

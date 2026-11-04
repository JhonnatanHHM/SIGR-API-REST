from rest_framework import status
from rest_framework.exceptions import APIException


class Conflicto(APIException):
    """La acción choca con el estado actual del recurso (p. ej. eliminar algo que tiene datos asociados): 409."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "La acción no se puede realizar con el estado actual del recurso."
    default_code = "conflicto"

# Todo POST que crea un recurso responde con la cabecera Location apuntando a su detalle.
# (Comentario y no docstring: drf-spectacular copiaría el docstring a la descripción de cada endpoint.)
class UbicacionAlCrearMixin:

    def get_success_headers(self, data):
        headers = super().get_success_headers(data)
        if "id" in data:
            headers["Location"] = f"{self.request.path.rstrip('/')}/{data['id']}/"
        return headers

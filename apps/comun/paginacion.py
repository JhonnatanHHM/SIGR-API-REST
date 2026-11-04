from rest_framework.pagination import PageNumberPagination


class PaginacionEstandar(PageNumberPagination):
    """Respuesta paginada: {count, next, previous, results}. `page` elige la página y `page_size` el tamaño (máx. 100)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

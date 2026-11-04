# Arquitectura, estructura de carpetas y convenciones

## Arquitectura

API REST con **Django 5.2** y **Django REST Framework** sobre **PostgreSQL**. Es la réplica en JSON del backend del [SIGR monolítico](https://github.com/JhonnatanHHM/Sistema-Integral-de-Gestion-de-Restaurante-SIGR-): mismos modelos y reglas de negocio, pero las respuestas son JSON en lugar de HTML.

```
Cliente HTTP (Postman) ──► Vistas / ViewSets ──► Serializadores (validan y normalizan)
                                 │                          │
                          Permisos por rol                  ▼
                                 │                 Servicios (reglas de negocio)
                                 ▼                          │
                         Respuesta JSON  ◄──────  Modelos / ORM  ──►  PostgreSQL
```

- **Modelos** (`models.py`): datos y restricciones.
- **Serializadores** (`serializers.py`): validan, normalizan y dan forma a la entrada y a la salida.
- **Vistas** (`views.py`): `ViewSet` de DRF; los permisos se declaran con clases de permiso por rol.
- **Servicios** (`services.py`): reglas que cruzan varios modelos (crear un pedido, reservar sin cruces, facturar, cerrar caja).
- **Documentación**: drf-spectacular genera el esquema OpenAPI desde el código.

## Estructura de carpetas

```
.
├── manage.py
├── requirements.txt           dependencias de desarrollo y pruebas
├── requirements-prod.txt      agrega gunicorn para producción
├── .env.example               variables de entorno (el .env real no se versiona)
├── config/                    proyecto Django
│   ├── settings.py            configuración (todo lo variable sale del entorno)
│   ├── settings_test.py       pruebas rápidas sobre SQLite en memoria
│   ├── settings_ci.py         pruebas sobre PostgreSQL (CI)
│   ├── urls.py                rutas /api/v1/, /api/schema/, /api/docs/
│   └── version.py             versión de la API
├── apps/
│   ├── comun/                 validadores, campos de serializador, paginación, excepciones y endpoint de salud
│   ├── usuarios/              cuentas, roles, token y permisos por rol
│   ├── menu/                  categorías, platos y fotos
│   ├── pedidos/               pedidos, ítems y flujo de estados
│   ├── reservas/              reservas y reglas de horario
│   ├── caja/                  facturas, cierres de caja y reportes
│   └── integracion/           pruebas de integración de extremo a extremo
├── docs/                      documentación técnica y esquema openapi.yaml
└── .github/                   plantillas de PR e Issues y flujos de GitHub Actions
```

Cada app sigue la misma forma: `models.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `services.py` (si hay reglas de negocio), `migrations/` y `tests/`.

## Convenciones de código

### Nombres
- Código, rutas e interfaz de la API en **español** (modelos, campos, rutas). Las palabras propias de DRF (`serializers`, `views`, `permissions`) se mantienen.
- Clases en `PascalCase`, funciones y variables en `snake_case`, constantes en `MAYUSCULAS`.
- Rutas versionadas bajo `/api/v1/`, en plural y en minúsculas; las acciones son verbos (`/avanzar/`, `/cancelar/`).

### Seguridad (obligatorio en todo cambio)
1. **Entradas validadas y normalizadas.** Todo dato que entra pasa por un serializador con validadores: correo con formato de correo, dinero solo numérico (`MontoField`), fechas ISO, horas en franjas fijas, textos con longitud máxima y sin `< >` ni caracteres de control, y espacios limpios. Los parámetros de consulta también se validan con un serializador.
2. **Sin SQL armado a mano.** Solo ORM con parámetros. Un filtro inválido responde 400; nunca se arma una consulta con él.
3. **Permisos por rol** declarados con clases de permiso (`EsCliente`, `EsPersonal`, `EsAdministrador`) y `IsAuthenticated` por defecto. Sin credenciales 401; con el rol equivocado 403; los datos ajenos responden 404.
4. **Nunca confiar en el cliente** para precios, estados, roles, dueños de un registro o totales: se calculan en el servidor.
5. **Archivos subidos validados por su contenido** (`validar_imagen`): JPG, PNG o WebP reales, hasta 2 MB y 4000 px por lado; SVG y cualquier otro formato se rechazan; el archivo se guarda con un nombre aleatorio.
6. **Concurrencia.** Los cambios de estado bloquean la fila y aceptan `desde`; si el estado ya cambió responden 409 en lugar de saltarse pasos. Las reservas revalidan los cruces dentro de la transacción, con bloqueo en PostgreSQL.

### Pruebas
- Cada módulo tiene pruebas de modelo, de serializadores (con entradas mal formadas y maliciosas) y de la API (incluidos los permisos por rol).
- Las pruebas que dependen de la hora fijan el reloj con `patch("django.utils.timezone.now")`.
- La matriz de acceso (`apps/integracion/tests/test_matriz_acceso.py`) lee los endpoints del esquema OpenAPI y falla si se agrega uno sin declarar qué roles pueden llamarlo.
- Antes de abrir un Pull Request: `python manage.py test --settings=config.settings_ci`.

### Git
Flujo, ramas, commits y versionado: ver [CONTRIBUTING.md](../CONTRIBUTING.md).

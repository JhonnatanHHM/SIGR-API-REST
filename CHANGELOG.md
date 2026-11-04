# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.3.0] - 2026-11-04

### Añadido
- App `menu` con los modelos `Categoria` y `Plato` (nombre único sin distinguir mayúsculas, precio con rango, disponibilidad, marca de destacado y foto).
- Carta pública: `GET /api/v1/platos/` (búsqueda y filtro por categoría) y `GET /api/v1/categorias/`; sin credenciales solo se ven platos disponibles de categorías activas.
- `GET /api/v1/platos/destacados/` (máximo 6, público).
- Gestión para el administrador: crear, reemplazar, editar y eliminar platos y categorías. El mesero solo alterna la disponibilidad de un plato con `POST /api/v1/platos/{id}/disponibilidad/`.
- Fotos de los platos por `multipart/form-data`: JPG, PNG o WebP reales de hasta 2 MB y 4000 px por lado, verificadas por su contenido, con nombre aleatorio y limpieza del archivo al reemplazar, quitar o eliminar.
- Eliminar una categoría con platos responde 409 (`Conflicto`).
- `MontoField` en `apps/comun`: dinero solo con dígitos, hasta 2 decimales, positivo y de máximo 9 dígitos; rechaza notación científica, signos, símbolos, booleanos y otros tipos.
- Filtros validados: una búsqueda o un filtro inválido responde 400 con el detalle.
- Comando `cargar_menu_demo` para cargar un menú de ejemplo.
- 65 pruebas nuevas (122 en total): precios, textos y categorías manipuladas, entradas hostiles, fotos falsas, permisos por rol y limpieza de archivos.

### Añadido
- App `usuarios` con modelo `Usuario` propio: acceso con correo electrónico y tres roles (cliente, mesero, administrador).
- Autenticación por token: `POST /api/v1/auth/registro/`, `POST /api/v1/auth/login/`, `POST /api/v1/auth/logout/` y `GET/PATCH /api/v1/auth/yo/`. El token se envía en `Authorization: Token <token>`.
- Administración de usuarios (solo administrador): `GET /api/v1/usuarios/` con búsqueda y filtro por rol, `GET /api/v1/usuarios/{id}/` y `POST /api/v1/usuarios/` para dar de alta personal.
- Permisos por rol (`EsCliente`, `EsPersonal`, `EsAdministrador`): sin credenciales 401, con el rol equivocado 403.
- El registro público siempre crea clientes; el rol y los permisos nunca se aceptan desde la petición.
- Validación y normalización de entradas: correo con formato válido y único sin importar mayúsculas, nombres solo con letras, teléfono de 7 a 15 dígitos y filtros con lista de caracteres permitidos (un filtro inválido responde 400).
- Ingreso fallido siempre responde 401 con `{"detail": "Credenciales inválidas."}`.
- Listados paginados (`count`, `next`, `previous`, `results`).
- Administración de Django para el modelo `Usuario`.
- 57 pruebas: modelo, serializadores con entradas mal formadas y maliciosas, flujo de autenticación y permisos por rol.

## [0.1.0] - 2026-11-04

### Añadido
- Flujo de trabajo Git: ramas `main` y `dev`, plantillas de Pull Request e Issues, guardia de ramas en GitHub Actions y guía `CONTRIBUTING.md`.
- Proyecto Django 5.2 con Django REST Framework, configuración por variables de entorno y conexión a PostgreSQL.
- Rutas versionadas bajo `/api/v1/` y endpoint de salud `GET /api/v1/salud/`.
- Documentación OpenAPI con drf-spectacular: esquema (`/api/schema/`), Swagger UI (`/api/docs/`) y ReDoc (`/api/redoc/`), con los recursos incluidos localmente.
- Valores por defecto seguros de DRF: autenticación obligatoria, respuestas solo en JSON y paginación estándar.
- Endurecimiento de la configuración de producción (cookies seguras, HSTS, rechazo de la clave secreta por defecto).
- Flujo de GitHub Actions `pruebas` sobre PostgreSQL 16: verifica la configuración, las migraciones y el esquema OpenAPI, y ejecuta las pruebas.
- Configuraciones de pruebas `settings_test` (SQLite) y `settings_ci` (PostgreSQL).
- `.env.example`, `.gitignore`, `requirements.txt` y `requirements-prod.txt`.

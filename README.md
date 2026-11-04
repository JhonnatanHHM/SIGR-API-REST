# SIGR API REST

API REST del **Sistema Integral de Gestión de Restaurante (SIGR)**, construida con **Django REST Framework** y **PostgreSQL**. Es la réplica en JSON del backend del [SIGR monolítico](https://github.com/JhonnatanHHM/Sistema-Integral-de-Gestion-de-Restaurante-SIGR-): mismos modelos y reglas de negocio, con respuestas JSON. Sirve como objeto de las pruebas automatizadas de la materia *Pruebas y Calidad del Software* (Postman).

## Módulos

| Módulo | Qué ofrece | Quién lo usa |
|---|---|---|
| **Autenticación** | Registro, ingreso con correo y token, cierre de sesión, perfil y roles | Todos |
| **Menú** | Carta pública con búsqueda y fotos; CRUD de platos y categorías; platos destacados y agotados | Público (carta), mesero (disponibilidad), administrador (gestión) |
| **Pedidos** | Pedido por mesa con precios congelados, estados Pendiente → En preparación → Listo → Servido → Cerrado, cancelación y control de concurrencia | Cliente y personal |
| **Reservas** | Reserva por fecha y hora (franjas de 30 min, 2 h de duración), sin cruces de mesa ni de cliente | Cliente reserva; personal confirma y completa |
| **Caja y reportes** | Factura numerada al cerrar un pedido, cierre de caja diario inmutable, reportes de ventas y platos más vendidos | Mesero (total del día), administrador (todo) |

Roles: **cliente** (se registra solo), **mesero** y **administrador** (los crea el administrador). Referencia completa de endpoints en [docs/api.md](docs/api.md).

## Arquitectura
Django 5.2 + DRF con rutas versionadas bajo `/api/v1/`, autenticación por token, permisos por rol y documentación OpenAPI generada automáticamente. Todas las entradas se validan y normalizan en los serializadores (sin SQL armado a mano). Detalle en [docs/arquitectura.md](docs/arquitectura.md).

## Puesta en marcha (Windows, PowerShell)

Requisitos: Python 3.10 a 3.12, PostgreSQL 14+ y Git.

```powershell
git clone https://github.com/JhonnatanHHM/SIGR-API-REST.git
cd SIGR-API-REST
```

1. **Base de datos** (en pgAdmin o `psql`, sobre la base `postgres`):
   ```sql
   CREATE USER sigr_app WITH PASSWORD 'cambia-esta-contrasena' CREATEDB;
   CREATE DATABASE sigr_api OWNER sigr_app ENCODING 'UTF8';
   ```
2. **Variables de entorno:** copia `.env.example` como `.env` y rellénalo.
3. **Entorno de Python:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
4. **Tablas, usuarios y menú de demostración, y servidor:**
   ```powershell
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py cargar_usuarios_demo
   .venv\Scripts\python manage.py cargar_menu_demo
   .venv\Scripts\python manage.py runserver
   ```
5. Comprueba que responde: http://127.0.0.1:8000/api/v1/salud/ y abre la documentación interactiva en http://127.0.0.1:8000/api/docs/

### Usuarios de demostración (solo desarrollo)
Contraseña de los tres: `Prueba-Segura-2026!`

| Rol | Correo |
|---|---|
| Administrador | `admin@sigr.test` |
| Mesero | `mesero@sigr.test` |
| Cliente | `cliente@sigr.test` |

El comando `cargar_usuarios_demo` se niega a ejecutarse con `DJANGO_DEBUG=0`, porque esa contraseña es pública.

## Probar la API
- **Swagger UI:** `/api/docs/` → *Authorize* con `Token <token>` (el token sale de `POST /api/v1/auth/login/`).
- **Postman:** *Import → Link* con `http://127.0.0.1:8000/api/schema/` (o el archivo [docs/openapi.yaml](docs/openapi.yaml)); ver [docs/api.md](docs/api.md#importar-en-postman).

## Pruebas
```powershell
.venv\Scripts\python manage.py test --settings=config.settings_test   # rápidas, SQLite en memoria
.venv\Scripts\python manage.py test --settings=config.settings_ci     # sobre PostgreSQL (lo mismo que el CI)
```
Incluyen pruebas por módulo (modelos, serializadores y API), pruebas de integración de extremo a extremo y una matriz de acceso por rol generada desde el esquema OpenAPI. En GitHub, el flujo `pruebas` las ejecuta en cada Pull Request y su resultado es obligatorio para fusionar.

## Flujo de trabajo y versionado
`rama nueva → dev → main`, siempre por Pull Request, con los checks `origen-permitido` y `pruebas` obligatorios. Commits en formato Conventional Commits y versiones con SemVer (tags `vX.Y.Z`). Ver [CONTRIBUTING.md](CONTRIBUTING.md) y [CHANGELOG.md](CHANGELOG.md).

## Documentación

| Documento | Contenido |
|---|---|
| [docs/api.md](docs/api.md) | Referencia de endpoints, códigos de estado y reglas de validación |
| [docs/openapi.yaml](docs/openapi.yaml) | Esquema OpenAPI 3 para importar en Postman |
| [docs/arquitectura.md](docs/arquitectura.md) | Arquitectura, estructura de carpetas y convenciones |
| [docs/base-de-datos.md](docs/base-de-datos.md) | Diagrama entidad–relación y diccionario de datos |
| [docs/despliegue.md](docs/despliegue.md) | Manual de despliegue en Windows y en Linux |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios por versión |

## Licencia
MIT. Ver [LICENSE](LICENSE).

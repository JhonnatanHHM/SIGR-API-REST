# SIGR API REST

API REST del **Sistema Integral de Gestión de Restaurante (SIGR)**, construida con **Django REST Framework** y **PostgreSQL**. Es la réplica en JSON del backend del [SIGR monolítico](https://github.com/JhonnatanHHM/Sistema-Integral-de-Gestion-de-Restaurante-SIGR-) y sirve como objeto de las pruebas automatizadas de la materia *Pruebas y Calidad del Software* (Postman).

## Arquitectura
- **Django 5.2 + DRF**: una app por módulo en `apps/` y rutas versionadas bajo `/api/v1/`.
- **PostgreSQL** como base de datos.
- **Autenticación por token** y permisos por rol (cliente, mesero, administrador).
- **Documentación OpenAPI** generada automáticamente (`/api/docs/`, `/api/redoc/`, `/api/schema/`); el esquema se puede importar en Postman.
- Todas las entradas se validan y normalizan en los serializadores (sin SQL armado a mano).

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
4. **Tablas y servidor:**
   ```powershell
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py runserver
   ```
5. Comprueba que responde: http://127.0.0.1:8000/api/v1/salud/ y la documentación en http://127.0.0.1:8000/api/docs/

## Pruebas
```powershell
.venv\Scripts\python manage.py test --settings=config.settings_test   # rápidas, SQLite en memoria
.venv\Scripts\python manage.py test --settings=config.settings_ci     # sobre PostgreSQL (lo mismo que el CI)
```

## Flujo de trabajo y versionado
`rama nueva → dev → main`, siempre por Pull Request, con los checks del CI obligatorios. Commits en formato Conventional Commits y versiones con SemVer (tags `vX.Y.Z`). Ver [CONTRIBUTING.md](CONTRIBUTING.md) y [CHANGELOG.md](CHANGELOG.md).

## Licencia
MIT. Ver [LICENSE](LICENSE).

# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

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

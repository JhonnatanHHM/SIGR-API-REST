# Guía de contribución

## Flujo de ramas

```
rama nueva  ──PR──►  dev  ──PR de integración──►  main
```

- `main`: rama estable. Solo recibe Pull Requests desde `dev`. Cada versión se marca con un tag `vX.Y.Z`.
- `dev`: integración. Solo recibe Pull Requests de ramas de trabajo. Se origina desde `main`.
- Cada módulo o cambio vive en una rama creada desde `origin/dev`:
  `feature/<modulo>`, `fix/<descripcion>`, `chore/<descripcion>`, `docs/<descripcion>`, `test/<descripcion>`.
- Nunca se hace push directo a `dev` ni a `main`.
- Estrategia de merge: **squash** en `feature → dev`, **merge commit** en `dev → main`.
- El flujo `guardia-ramas` comprueba en cada Pull Request que el origen sea el permitido para la rama de destino.

> **Protección de ramas.** Las reglas de GitHub (rulesets) que impiden el push directo y exigen los checks solo se pueden
> aplicar si el repositorio es público o la cuenta tiene GitHub Pro. Mientras no estén activas, el flujo se cumple por
> disciplina y los checks se ejecutan igualmente en cada Pull Request.

## Commits (Conventional Commits)

`tipo(alcance): descripción en imperativo`

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`, `ci`.

## Versionado (SemVer)

`MAJOR.MINOR.PATCH`. Los hitos de desarrollo son `0.x.0`; la primera versión estable es `v1.0.0`.
Cada versión se registra en `CHANGELOG.md` (formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)) y se publica como tag anotado y release en GitHub.

## Reglas de calidad del código

1. **Entradas validadas y normalizadas.** Todo dato que entra a la API pasa por un serializador con validadores: correo con formato de correo, dinero solo numérico, fechas en ISO, horas en franjas fijas, textos con longitud máxima y sin `< >` ni caracteres de control. Los filtros de las consultas también se validan.
2. **Sin SQL armado a mano.** Solo ORM con parámetros.
3. **Permisos por rol** declarados con clases de permiso de DRF (`EsCliente`, `EsPersonal`, `EsAdministrador`). Sin credenciales: 401; con el rol equivocado: 403; datos ajenos: 404.
4. **Nunca confiar en el cliente** para precios, estados, roles o dueños de un registro.
5. **Pruebas** por módulo (modelos, serializadores, vistas) con entradas mal formadas y maliciosas, y pruebas de integración. Antes de abrir un Pull Request: `python manage.py test --settings=config.settings_ci`.

## Pull Requests

Usa la plantilla del repositorio. Actualiza el CHANGELOG en la sección `[Sin publicar]`.

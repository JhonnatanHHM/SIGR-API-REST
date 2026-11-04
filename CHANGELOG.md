# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.7.0] - 2026-11-04

### Añadido
- Pruebas de integración de extremo a extremo (`apps/integracion`): de la cuenta nueva a la reserva, el pedido, la factura, el cierre de caja y el reporte, más cancelaciones, alta de personal, platos agotados y cierre de sesión.
- Matriz de acceso por rol generada a partir del esquema OpenAPI: verifica qué rol puede llamar a cada uno de los 42 endpoints (401 sin credenciales, 403 con el rol equivocado) y falla si se agrega un endpoint sin declarar su permiso.
- Barrido de seguridad: entradas hostiles (inyección SQL, scripts, rutas, plantillas, valores gigantes, tipos incorrectos, JSON malformado, tipos de contenido no soportados) en todos los filtros y cuerpos; ninguna produce un error del servidor ni guarda datos en campos estrictos.
- Verificaciones de integridad: sin migraciones pendientes, `check` sin problemas y esquema OpenAPI válido y sin avisos.
- Comando `cargar_usuarios_demo`: crea un administrador, un mesero y un cliente (`@sigr.test`) con una contraseña conocida para probar la API con Postman o Swagger; solo funciona con `DJANGO_DEBUG=1`.
- 29 pruebas nuevas (291 en total).

### Añadido
- App `caja` con los modelos `Factura` y `CierreCaja`.
- Facturación: al cerrar un pedido con `POST /api/v1/pedidos/{id}/avanzar/` se emite automáticamente su factura numerada (`F-000001`), una sola por pedido y con el total congelado. El pedido incluye ahora el campo `factura`.
- `GET /api/v1/caja/facturas/` (administrador) y `GET /api/v1/caja/facturas/{id}/` con el detalle del pedido: el personal ve cualquiera y el cliente solo la de sus pedidos (las ajenas responden 404).
- Cierre de caja (solo administrador): `POST /api/v1/caja/cierres/` registra el efectivo contado, lo compara con las ventas facturadas del día y guarda la diferencia (cuadrado, sobrante o faltante). Un cierre no se puede modificar, eliminar (405) ni repetir para el mismo día (409). `GET /api/v1/caja/cierres/` y `GET /api/v1/caja/cierres/{id}/`.
- Reglas del cierre: no se cierra una fecha futura ni un día con pedidos sin cerrar (400); con la caja de hoy cerrada ya no se pueden cerrar más pedidos (409).
- `GET /api/v1/caja/reportes/ventas/` (administrador): ventas por día, total, número de facturas, ticket promedio y platos más vendidos, con rango de fechas validado (formato ISO, desde ≤ hasta ≤ hoy, máximo un año; 400 si es inválido).
- `GET /api/v1/caja/resumen/`: el mesero solo recibe el total de ventas del día; el administrador recibe además facturas, pedidos sin cerrar y el cierre.
- 48 pruebas nuevas (262 en total): facturación y numeración, diferencias de caja, inmutabilidad de los cierres, totales de reportes, efectivo y fechas mal formados, inyección SQL en parámetros y permisos por rol.

### Añadido
- App `reservas` con el modelo `Reserva` (fecha, hora, personas, mesa, notas y estado).
- Reglas de negocio centralizadas: franjas de 11:00 a 20:00 cada 30 minutos, duración de 2 horas, anticipación mínima de 1 hora y máxima de 30 días, hasta 12 personas.
- `POST /api/v1/reservas/` (solo clientes): fecha en formato ISO `AAAA-MM-DD`, hora entre las franjas permitidas, personas y mesa numéricas dentro de su rango, notas sin `< >`. Responde 201 con la cabecera `Location`.
- Bloqueo de cruces: una mesa no se reserva si ya hay una reserva vigente a menos de 2 horas de diferencia (el borde exacto es válido) y un cliente no puede tener dos reservas cruzadas. Un cruce responde 409; la verificación se repite dentro de la transacción, con bloqueo en PostgreSQL.
- `GET /api/v1/reservas/` (filtros `estado`, incluido `vigentes`, `fecha` y `mesa`, con paginación) y `GET /api/v1/reservas/{id}/`: el cliente solo ve las suyas (las ajenas responden 404) y el personal ve todas.
- Flujo Pendiente → Confirmada → Completada con `POST /api/v1/reservas/{id}/confirmar/` y `/completar/` (solo personal) y cancelación mientras esté vigente con `POST /api/v1/reservas/{id}/cancelar/`; una reserva cancelada libera la mesa.
- Si se envía `desde` y la reserva ya cambió de estado, la API responde 409.
- El cliente y el estado nunca se aceptan de la petición.
- 47 pruebas nuevas (214 en total), con el reloj fijo: formatos de fecha y hora inválidos, límites de anticipación, cruces y bordes, inyección SQL en filtros, permisos y acciones con estado desactualizado.

### Añadido
- App `pedidos` con los modelos `Pedido` e `ItemPedido`; el precio de cada ítem se congela al crear el pedido.
- `POST /api/v1/pedidos/`: el cliente crea el suyo y el personal registra pedidos de mesa. Mesa de 1 a 99, cantidades de 1 a 50, notas validadas y platos disponibles; el precio nunca se recibe del cliente. Responde 201 con la cabecera `Location`.
- `GET /api/v1/pedidos/` (filtros `estado`, incluido `activos`, y `mesa`, con paginación) y `GET /api/v1/pedidos/{id}/`: el cliente solo ve los suyos (los ajenos responden 404) y el personal ve todos.
- Flujo de estados Pendiente → En preparación → Listo → Servido → Cerrado con `POST /api/v1/pedidos/{id}/avanzar/` (solo personal) y cancelación mientras está pendiente con `POST /api/v1/pedidos/{id}/cancelar/`.
- Control de concurrencia: si se envía `desde` y el pedido ya cambió de estado, la API responde 409 en lugar de saltarse pasos; el pedido se bloquea durante el cambio.
- Un plato con pedidos asociados responde 409 al eliminarse.
- Esquema OpenAPI sin avisos (nombres de enumeraciones y tipos de parámetros).
- 45 pruebas nuevas (167 en total): estados, validación de mesa, cantidades, notas e ítems, visibilidad por rol, filtros con inyección SQL y cambios de estado desactualizados.

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

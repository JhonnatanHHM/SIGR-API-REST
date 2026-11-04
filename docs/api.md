# Referencia de la API

Base: `http://127.0.0.1:8000/api/v1` (en desarrollo). Documentación interactiva: `/api/docs/` (Swagger UI) y `/api/redoc/`. Esquema OpenAPI: `/api/schema/` y el archivo [openapi.yaml](openapi.yaml), que se puede importar en Postman.

## Convenciones

| Tema | Regla |
|---|---|
| Formato | JSON (`Content-Type: application/json`). Las fotos de los platos se envían como `multipart/form-data`. Otros tipos responden 415 |
| Autenticación | Token en la cabecera `Authorization: Token <token>`. Se obtiene con `POST /auth/login/` o `POST /auth/registro/` y se invalida con `POST /auth/logout/` |
| Roles | `cliente` (se registra solo), `mesero` y `administrador` (los crea un administrador) |
| Dinero | Texto con dos decimales (`"28000.00"`). Al enviarlo se aceptan dígitos con punto o coma decimal; se rechazan signos, símbolos y notación científica |
| Fechas y horas | Fecha `AAAA-MM-DD`; hora `HH:MM` |
| Listados | Paginados: `{"count", "next", "previous", "results"}`. Parámetros `page` y `page_size` (máximo 100) |
| Filtros | Se validan: un filtro inválido responde **400** con el detalle y nunca devuelve el listado completo |
| Ubicación | Los `POST` que crean recursos responden **201** con la cabecera `Location` |

### Códigos de estado

| Código | Significado |
|---|---|
| 200 / 201 / 204 | Correcto / creado / correcto sin contenido |
| 400 | Datos inválidos. El cuerpo indica el error por campo, por ejemplo `{"precio": ["Ingresa un valor numérico…"]}` |
| 401 | Sin credenciales, token inválido o ingreso fallido. Incluye `WWW-Authenticate: Token` |
| 403 | Credenciales válidas pero el rol no tiene permiso |
| 404 | El recurso no existe **o pertenece a otra persona** (un cliente no puede saber si un pedido ajeno existe) |
| 405 | Método no permitido |
| 409 | Conflicto con el estado del recurso: mesa ya reservada, cierre de caja repetido, pedido con estado cambiado, eliminar algo con datos asociados |
| 415 | Tipo de contenido no soportado |

### Validación de entradas

| Dato | Regla |
|---|---|
| Correo | Formato de correo, hasta 254 caracteres, único sin distinguir mayúsculas; se guarda en minúsculas |
| Nombre y apellido | Solo letras, espacios, guion y apóstrofo; hasta 60 caracteres; los espacios se limpian |
| Teléfono | De 7 a 15 dígitos con `+` opcional; se quitan espacios, guiones y paréntesis |
| Contraseña | Validadores de Django (mínimo 8 caracteres, no común, no solo números) y confirmación |
| Nombres de plato y categoría | Letras, números, espacios y `, . ' & ( ) / -`; únicos sin distinguir mayúsculas (los platos, por categoría) |
| Descripciones, notas y observaciones | Sin `<` ni `>` ni caracteres de control; longitud máxima (200 o 500) |
| Precio | Mayor que 0, hasta 7 enteros y 2 decimales |
| Efectivo contado | Desde 0, hasta 10 enteros y 2 decimales |
| Mesa | Entero de 1 a 99 |
| Cantidad de un plato en un pedido | Entero de 1 a 50; cada plato aparece una sola vez |
| Reserva | Hora entre 11:00 y 20:00 cada 30 minutos; personas de 1 a 12; entre 1 hora y 30 días de anticipación |
| Foto | JPG, PNG o WebP reales, hasta 2 MB y 4000 px por lado; se guarda con un nombre aleatorio |
| Rango de reporte | `desde` ≤ `hasta` ≤ hoy y máximo 366 días |

El precio de un pedido, su estado, el cliente dueño, el rol de una cuenta nueva y los totales de un cierre **nunca se aceptan** del cliente: se calculan en el servidor.

## Endpoints

Acceso: **Público** = sin credenciales · **Sesión** = cualquier usuario autenticado · **Personal** = mesero o administrador.

### Salud
| Método | Ruta | Acceso | Respuesta |
|---|---|---|---|
| GET | `/salud/` | Público | 200 `{"estado": "ok", "servicio", "version"}` |

### Autenticación
| Método | Ruta | Acceso | Cuerpo | Respuestas |
|---|---|---|---|---|
| POST | `/auth/registro/` | Público | `first_name`, `last_name`, `email`, `telefono` (opcional), `password`, `password_confirmacion` | 201 `{"token", "usuario"}` (siempre rol cliente) · 400 |
| POST | `/auth/login/` | Público | `email`, `password` | 200 `{"token", "usuario"}` · 400 · 401 `{"detail": "Credenciales inválidas."}` |
| POST | `/auth/logout/` | Sesión | — | 204 (el token deja de valer) |
| GET | `/auth/yo/` | Sesión | — | 200 con la cuenta |
| PATCH | `/auth/yo/` | Sesión | `first_name`, `last_name`, `telefono` | 200 · 400 (el correo y el rol no se pueden cambiar) |

### Usuarios (administrador)
| Método | Ruta | Cuerpo / parámetros | Respuestas |
|---|---|---|---|
| GET | `/usuarios/` | `?q=` (nombre, apellido o correo), `?rol=`, `?page=`, `?page_size=` | 200 paginado · 400 si el filtro es inválido |
| POST | `/usuarios/` | Datos del registro + `rol` (`mesero` o `administrador`) | 201 (sin token) · 400 |
| GET | `/usuarios/{id}/` | — | 200 · 404 |

### Menú
| Método | Ruta | Acceso | Cuerpo / parámetros | Respuestas |
|---|---|---|---|---|
| GET | `/categorias/` | Público | — | 200 (el público ve solo las activas; el administrador, todas) |
| GET | `/categorias/{id}/` | Público | — | 200 · 404 |
| POST | `/categorias/` | Administrador | `nombre`, `descripcion`, `orden` (0–999), `activa` | 201 · 400 |
| PUT/PATCH | `/categorias/{id}/` | Administrador | igual que crear | 200 · 400 · 404 |
| DELETE | `/categorias/{id}/` | Administrador | — | 204 · 404 · 409 si tiene platos |
| GET | `/platos/` | Público | `?q=`, `?categoria=<id>`, `?disponible=true\|false` (solo personal) | 200 paginado · 400. El público ve solo platos disponibles de categorías activas |
| GET | `/platos/destacados/` | Público | — | 200 con hasta 6 platos |
| GET | `/platos/{id}/` | Público | — | 200 · 404 (un plato agotado u oculto responde 404 al público) |
| POST | `/platos/` | Administrador | `categoria`, `nombre`, `descripcion`, `precio`, `disponible`, `destacado`, `imagen` (archivo) | 201 · 400 |
| PUT/PATCH | `/platos/{id}/` | Administrador | igual que crear; `imagen: null` quita la foto | 200 · 400 · 404 |
| DELETE | `/platos/{id}/` | Administrador | — | 204 · 404 · 409 si tiene pedidos |
| POST | `/platos/{id}/disponibilidad/` | Personal | — | 200 (alterna disponible/agotado) · 404 |

### Pedidos
| Método | Ruta | Acceso | Cuerpo / parámetros | Respuestas |
|---|---|---|---|---|
| GET | `/pedidos/` | Sesión (el cliente ve solo los suyos) | `?estado=` (`activos` o un estado), `?mesa=` | 200 paginado · 400 |
| POST | `/pedidos/` | Sesión | `mesa`, `notas`, `items: [{"plato": id, "cantidad": n}]` | 201 + `Location` · 400 |
| GET | `/pedidos/{id}/` | Sesión (un pedido ajeno responde 404) | — | 200 · 404 |
| POST | `/pedidos/{id}/avanzar/` | Personal | `desde` (opcional: el estado que se veía) | 200 · 409 si el estado cambió, si ya está cerrado o si la caja de hoy está cerrada |
| POST | `/pedidos/{id}/cancelar/` | Sesión | — | 200 · 404 · 409 si ya no está pendiente |

Estados: `pendiente` → `en_preparacion` → `listo` → `servido` → `cerrado` (o `cancelado`, solo desde `pendiente`). Al pasar a `cerrado` se emite la factura, que aparece en el campo `factura` del pedido.

### Reservas
| Método | Ruta | Acceso | Cuerpo / parámetros | Respuestas |
|---|---|---|---|---|
| GET | `/reservas/` | Sesión (el cliente ve solo las suyas) | `?estado=` (`vigentes` o un estado), `?fecha=`, `?mesa=` | 200 paginado · 400 |
| POST | `/reservas/` | Cliente | `fecha`, `hora`, `personas`, `mesa`, `notas` | 201 + `Location` · 400 · **409** si la mesa ya está reservada cerca de esa hora o el cliente ya tiene una reserva que se cruza |
| GET | `/reservas/{id}/` | Sesión (una reserva ajena responde 404) | — | 200 · 404 |
| POST | `/reservas/{id}/confirmar/` | Personal | `desde` (opcional) | 200 · 409 |
| POST | `/reservas/{id}/completar/` | Personal | `desde` (opcional) | 200 · 409 (solo una confirmada) |
| POST | `/reservas/{id}/cancelar/` | Sesión | `desde` (opcional) | 200 · 404 · 409 |

Cada reserva dura 2 horas; terminar justo cuando empieza otra es válido. Estados: `pendiente` → `confirmada` → `completada` (o `cancelada`).

### Caja
| Método | Ruta | Acceso | Cuerpo / parámetros | Respuestas |
|---|---|---|---|---|
| GET | `/caja/resumen/` | Personal | — | 200. El mesero solo recibe `fecha` y `ventas_del_dia`; el administrador, además, `facturas`, `pedidos_sin_cerrar` y `cierre` |
| GET | `/caja/facturas/` | Administrador | — | 200 paginado |
| GET | `/caja/facturas/{id}/` | Sesión (el cliente, solo la de sus pedidos) | — | 200 con el detalle del pedido · 404 |
| GET | `/caja/cierres/` | Administrador | — | 200 paginado |
| POST | `/caja/cierres/` | Administrador | `fecha`, `efectivo_contado`, `observaciones` | 201 + `Location` · 400 (fecha futura o pedidos del día sin cerrar) · 409 si ese día ya se cerró |
| GET | `/caja/cierres/{id}/` | Administrador | — | 200 · 404 |
| GET | `/caja/reportes/ventas/` | Administrador | `?desde=`, `?hasta=` (por defecto, los últimos 7 días) | 200 con ventas por día, total, ticket promedio y platos más vendidos · 400 |

Un cierre de caja **no se puede modificar ni eliminar** (405) y no se puede repetir para el mismo día (409).

## Ejemplos (PowerShell)

```powershell
$base = "http://127.0.0.1:8000/api/v1"

# 1. Iniciar sesión (usuarios de demostración: ver el README)
$sesion = Invoke-RestMethod "$base/auth/login/" -Method Post -ContentType "application/json" `
  -Body (@{ email = "cliente@sigr.test"; password = "Prueba-Segura-2026!" } | ConvertTo-Json)
$h = @{ Authorization = "Token $($sesion.token)" }

# 2. Ver la carta (no necesita token)
(Invoke-RestMethod "$base/platos/").results | Select-Object id, nombre, precio

# 3. Crear un pedido
$pedido = @{ mesa = 5; notas = "Sin cebolla"; items = @(@{ plato = 1; cantidad = 2 }) } | ConvertTo-Json -Depth 5
Invoke-RestMethod "$base/pedidos/" -Method Post -Headers $h -ContentType "application/json" -Body $pedido
```

## Importar en Postman
1. **Import → Link** y pegar `http://127.0.0.1:8000/api/schema/` (o **Import → File** con `docs/openapi.yaml`).
2. Crear la variable `base_url = http://127.0.0.1:8000` y, en la autorización de la colección, usar *API Key* con clave `Authorization` y valor `Token {{token}}` en la cabecera.
3. Ejecutar `POST /auth/login/` y guardar el `token` de la respuesta en la variable `token`.

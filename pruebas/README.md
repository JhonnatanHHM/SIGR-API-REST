# Pruebas automatizadas de servicios REST y formularios web

| Qué se prueba | Herramienta | Carpeta |
|---|---|---|
| API REST (este repositorio) | **Postman** (colección, ambiente y Collection Runner) | [postman/](postman/) |
| Formularios web de registro e ingreso (SIGR monolítico) | **Selenium WebDriver** con Python y pytest | [selenium/](selenium/) |
| Lógica interna de la API | Pruebas de Django (291+) | `apps/*/tests/` |

## Antes de empezar

1. **API REST** (puerto 8001; el 8000 se reserva para el sistema web monolítico):
   ```powershell
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py cargar_usuarios_demo
   .venv\Scripts\python manage.py cargar_menu_demo
   .venv\Scripts\python manage.py runserver 8001
   ```
   Comprobar en http://127.0.0.1:8001/api/v1/salud/ y en la documentación http://127.0.0.1:8001/api/docs/.
2. **Sistema web monolítico** (solo para Selenium): arrancarlo desde su carpeta con `.venv\Scripts\python manage.py runserver` (puerto 8000). Debe abrir http://127.0.0.1:8000/cuentas/registro/.

---

## 1. Postman

### 1.1 Importar
1. Abrir Postman → **Import** → seleccionar los dos archivos de [postman/](postman/):
   - `SIGR-API.postman_collection.json` (la colección)
   - `SIGR-Local.postman_environment.json` (el ambiente)
2. En la esquina superior derecha elegir el ambiente **SIGR Local**. Define `base_url = http://127.0.0.1:8001` y `password`.

### 1.2 Ejecutar todo con el Collection Runner
1. Clic derecho sobre la colección → **Run collection** (o *Runner* → arrastrar la colección).
2. Marcar las carpetas **00 a 06** y **desmarcar la 07**. Dejar *Iterations = 1* y *Delay = 0*.
3. **Run SIGR API REST**. Las carpetas corren en orden: la 00 inicia sesión con los tres roles y guarda los tokens; las demás los reutilizan.
4. Resultado esperado: **166 aserciones aprobadas, 0 fallidas**. Cada solicitud muestra sus pruebas con ✔ o ✘, que sirve para la captura.

### 1.3 Pruebas con datos hostiles (carpeta 07)
Una misma solicitud de ingreso se repite con 12 filas de datos (inyección SQL, scripts, vacíos, mayúsculas...).
1. En el Runner dejar marcada **solo** la carpeta 07.
2. **Select File** (*Data*) → `postman/datos/login_hostil.json`. Debe indicar 12 iteraciones.
3. Ejecutar. Esperado: **12 iteraciones, 0 fallos**.

### 1.4 Ejecutar solicitudes sueltas
Abrir cualquier solicitud y pulsar **Send**; la pestaña **Test Results** muestra sus aserciones. Para una carpeta que depende de los tokens, ejecutar antes `00 Preparación`.

### 1.5 Qué valida cada carpeta

| Carpeta | Qué comprueba |
|---|---|
| 00 Preparación | Salud del servicio, ingreso de los tres roles, plato base de la carta |
| 01 Autenticación | Registro válido y mal formado (correo, contraseña, scripts, SQL), ingreso, perfil, intento de subir de rol |
| 02 Control de acceso | 401 sin token, 403 con el rol equivocado, 200 con el correcto |
| 03 Menú y búsquedas | Búsquedas con inyección SQL y HTML (400), precios inválidos, nombre repetido, platos agotados, borrado con datos asociados (409) |
| 04 Pedidos | Precio calculado en el servidor, validaciones, aislamiento entre clientes (404), flujo completo hasta la factura, 409 por estado desactualizado |
| 05 Reservas | Franjas horarias, aforo, fechas, bloqueo de cruces (409), ciclo de vida |
| 06 Caja | Resumen por rol, rangos de reporte, cierre de caja inmutable (405) y no repetible (409) |
| 07 Datos hostiles | Ingreso con 12 combinaciones de datos (Runner con archivo) |

### 1.6 Ejecutar sin abrir Postman (Newman, opcional)
Requiere Node.js. Con él instalado:
```powershell
npm install -g newman
newman run pruebas\postman\SIGR-API.postman_collection.json -e pruebas\postman\SIGR-Local.postman_environment.json `
  --folder "00 Preparación" --folder "01 Autenticación" --folder "02 Control de acceso por rol" `
  --folder "03 Menú y búsquedas" --folder "04 Pedidos" --folder "05 Reservas" --folder "06 Caja, cierres y reportes"

newman run pruebas\postman\SIGR-API.postman_collection.json -e pruebas\postman\SIGR-Local.postman_environment.json `
  --folder "07 Ingreso con datos hostiles (Runner)" -d pruebas\postman\datos\login_hostil.json
```

### 1.7 Repetir la ejecución
La colección se puede ejecutar varias veces seguidas: usa correos, nombres, fechas y mesas únicos, y el cierre de caja se hace sobre un día pasado aleatorio.

---

## 2. Selenium WebDriver

### 2.1 Preparar el entorno (una sola vez)
```powershell
python -m venv .venv-selenium
.venv-selenium\Scripts\pip install -r pruebas\selenium\requirements.txt
```
Se necesita Chrome o Edge instalado; Selenium descarga el controlador solo (requiere internet la primera vez).

### 2.2 Ejecutar
```powershell
cd pruebas\selenium
..\..\.venv-selenium\Scripts\python -m pytest                    # todo, sin ventana
..\..\.venv-selenium\Scripts\python -m pytest --visible          # viendo el navegador trabajar
..\..\.venv-selenium\Scripts\python -m pytest -m registro        # solo el formulario de registro
..\..\.venv-selenium\Scripts\python -m pytest -m ingreso         # solo el de ingreso
..\..\.venv-selenium\Scripts\python -m pytest --navegador edge   # con Edge
..\..\.venv-selenium\Scripts\python -m pytest --url http://127.0.0.1:8000
```
Resultado esperado: **25 pruebas aprobadas** (15 de registro y 10 de ingreso), unos 2 minutos.

### 2.3 Resultados
- `pruebas/selenium/informe/informe-selenium.html`: informe con cada prueba y su resultado.
- `pruebas/selenium/capturas/`: una captura por prueba como evidencia; si una falla se guarda `FALLO_<prueba>.png`.

### 2.4 Cómo está organizado
```
pruebas/selenium/
├── conftest.py          navegador, opciones (--visible, --navegador, --url), capturas y cuenta de apoyo
├── paginas/             Page Object: un archivo por formulario; los selectores viven solo aquí
├── datos/               casos de prueba en JSON (agregar un caso no exige tocar código)
├── test_registro.py     registro válido e inválido, correo repetido
└── test_ingreso.py      ingreso correcto y credenciales rechazadas
```
Buenas prácticas aplicadas: esperas explícitas (nunca `sleep`), un navegador limpio por prueba, datos únicos por ejecución, pruebas guiadas por datos, aserciones sobre el resultado y sobre la ausencia de errores de servidor, y captura de evidencia en cada caso.

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| Postman: *Could not send request* | La API no está en marcha | Arrancar `runserver 8001` |
| Postman: la carpeta 00 falla con 401 | Faltan los usuarios de demostración | `cargar_usuarios_demo` |
| Postman: 03 o 04 fallan por plato | Falta el menú de demostración | `cargar_menu_demo` |
| Postman: 404 en `/api/...` con puerto 8000 | El 8000 es el monolito | Usar `base_url = http://127.0.0.1:8001` |
| Postman: la 06 devuelve 409 en un cierre | Se repitió la fecha aleatoria (muy raro) | Volver a ejecutar la carpeta |
| Selenium: `ERR_CONNECTION_REFUSED` | El sistema web no está en el puerto 8000 | Arrancarlo o usar `--url` |
| Selenium: no encuentra el navegador | Chrome/Edge no instalado | Instalarlo o usar `--navegador edge` |

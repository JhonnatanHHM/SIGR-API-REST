# Manual de despliegue

Dos escenarios: **A. instalación local (Windows)**, la que se usó durante el desarrollo, y **B. servidor Linux de producción** con gunicorn, nginx y systemd.

> Estado de validación: el escenario A se ejecutó completo en el equipo de desarrollo y en el CI (GitHub Actions con PostgreSQL 16). Los archivos de nginx y systemd del escenario B son una configuración de referencia que no se probó en un servidor real: ajusta dominios y rutas a tu servidor.

## Requisitos

| Componente | Versión |
|---|---|
| Python | 3.10 a 3.12 |
| PostgreSQL | 14 o superior (probado con 16 y 18) |
| Git | cualquiera reciente |
| Producción | nginx y un dominio con certificado HTTPS |

## Variables de entorno

Se leen del archivo `.env` (en la carpeta del proyecto) o del entorno del sistema. Plantilla: `.env.example`.

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | Sí | Conexión a PostgreSQL |
| `DJANGO_SECRET_KEY` | Sí | Cadena larga y aleatoria. Con `DJANGO_DEBUG=0` el sistema **se niega a arrancar** con la clave por defecto |
| `DJANGO_DEBUG` | No | `1` en desarrollo (por defecto); **`0` en producción** |
| `DJANGO_ALLOWED_HOSTS` | Sí en producción | Dominios permitidos, separados por comas |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | En producción | Orígenes con https, p. ej. `https://api.ejemplo.com` (afecta al sitio de administración) |
| `DJANGO_BEHIND_PROXY` | Con nginx | `1` si el proxy termina el HTTPS y envía `X-Forwarded-Proto` |
| `DJANGO_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS` | No | Redirección a https (1 por defecto) y duración de HSTS |

Generar una clave secreta: `python -c "import secrets; print(secrets.token_urlsafe(64))"`

---

## A. Instalación local (Windows, PowerShell)

1. **Clonar:** `git clone https://github.com/JhonnatanHHM/SIGR-API-REST.git` y entrar a la carpeta.
2. **Base de datos** (en pgAdmin o `psql`, sobre la base `postgres`):
   ```sql
   CREATE USER sigr_app WITH PASSWORD 'cambia-esta-contrasena' CREATEDB;
   CREATE DATABASE sigr_api OWNER sigr_app ENCODING 'UTF8';
   ```
   (`CREATEDB` permite que las pruebas creen su base temporal.)
3. **Variables:** `copy .env.example .env` y editar los valores.
4. **Entorno de Python:**
   ```powershell
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
5. **Tablas y datos de demostración:**
   ```powershell
   .venv\Scripts\python manage.py migrate
   .venv\Scripts\python manage.py cargar_usuarios_demo     # administrador, mesero y cliente
   .venv\Scripts\python manage.py cargar_menu_demo         # menú de ejemplo
   ```
6. **Arrancar:** `.venv\Scripts\python manage.py runserver`
7. **Verificar:** abrir http://127.0.0.1:8000/api/v1/salud/ (debe responder `{"estado": "ok", …}`) y http://127.0.0.1:8000/api/docs/, y ejecutar `.venv\Scripts\python manage.py test --settings=config.settings_ci` (debe terminar en `OK`).

---

## B. Producción en Linux (Ubuntu/Debian)

### 1. Paquetes y usuario del sistema
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-dev libpq-dev postgresql nginx git
sudo adduser --system --group --home /opt/sigr sigr
```

### 2. Base de datos
```bash
sudo -u postgres psql <<'SQL'
CREATE USER sigr_app WITH PASSWORD 'CONTRASEÑA-FUERTE';
CREATE DATABASE sigr_api OWNER sigr_app ENCODING 'UTF8';
SQL
```

### 3. Código y entorno
```bash
sudo -u sigr git clone https://github.com/JhonnatanHHM/SIGR-API-REST.git /opt/sigr/app
cd /opt/sigr/app
sudo -u sigr git checkout v1.0.0            # siempre desplegar una versión etiquetada
sudo -u sigr python3 -m venv /opt/sigr/venv
sudo -u sigr /opt/sigr/venv/bin/pip install -r requirements-prod.txt
```

### 4. Configuración
Crear `/opt/sigr/app/.env` (permisos `600`, dueño `sigr`):
```ini
DB_NAME=sigr_api
DB_USER=sigr_app
DB_PASSWORD=CONTRASEÑA-FUERTE
DB_HOST=localhost
DB_PORT=5432
DJANGO_SECRET_KEY=<clave generada>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=api.ejemplo.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.ejemplo.com
DJANGO_BEHIND_PROXY=1
```

### 5. Tablas, estáticos y administrador
```bash
cd /opt/sigr/app
sudo -u sigr mkdir -p media                 # fotos de los platos (debe poder escribir el usuario sigr)
sudo -u sigr /opt/sigr/venv/bin/python manage.py migrate
sudo -u sigr /opt/sigr/venv/bin/python manage.py collectstatic --noinput
sudo -u sigr /opt/sigr/venv/bin/python manage.py createsuperuser
sudo -u sigr /opt/sigr/venv/bin/python manage.py check --deploy
```
Con `DJANGO_DEBUG=0` **no** se debe ejecutar `cargar_usuarios_demo` (se niega a correr: sus contraseñas son públicas). El primer administrador se crea con `createsuperuser`; después, el administrador da de alta al personal por la API.

### 6. Servicio (systemd)
`/etc/systemd/system/sigr-api.service`:
```ini
[Unit]
Description=SIGR API REST (gunicorn)
After=network.target postgresql.service

[Service]
User=sigr
Group=sigr
WorkingDirectory=/opt/sigr/app
ExecStart=/opt/sigr/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=on-failure

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sigr-api
```

### 7. nginx
`/etc/nginx/sites-available/sigr-api`:
```nginx
server {
    listen 80;
    server_name api.ejemplo.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name api.ejemplo.com;
    # ssl_certificate y ssl_certificate_key: por ejemplo con certbot (Let's Encrypt)

    client_max_body_size 3m;          # las fotos de los platos pesan hasta 2 MB

    location /static/ { alias /opt/sigr/app/staticfiles/; }   # recursos de Swagger UI y del administrador
    location /media/  { alias /opt/sigr/app/media/; }         # fotos de los platos

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
```bash
sudo ln -s /etc/nginx/sites-available/sigr-api /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 8. Comprobación
`curl https://api.ejemplo.com/api/v1/salud/` debe responder `{"estado":"ok",…}`; `https://api.ejemplo.com/api/docs/` debe cargar con estilos.

---

## Actualizar a una versión nueva
```bash
cd /opt/sigr/app
sudo -u sigr git fetch --tags
sudo -u sigr git checkout vX.Y.Z
sudo -u sigr /opt/sigr/venv/bin/pip install -r requirements-prod.txt
sudo -u sigr /opt/sigr/venv/bin/python manage.py migrate
sudo -u sigr /opt/sigr/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart sigr-api
```
Antes de actualizar, haz una copia de seguridad de la base de datos y de la carpeta `media/`.

## Volver a una versión anterior
1. `sudo systemctl stop sigr-api`.
2. Restaurar la copia de la base de datos hecha antes de actualizar (las migraciones nuevas pueden no ser reversibles).
3. `git checkout vX.Y.Z` (la versión anterior), reinstalar dependencias y `collectstatic`.
4. `sudo systemctl start sigr-api`.

## Copias de seguridad
```bash
pg_dump -U sigr_app -h localhost -Fc sigr_api > sigr_api_$(date +%F).dump
pg_restore -U sigr_app -h localhost -d sigr_api --clean --if-exists sigr_api_2026-11-04.dump
tar czf media_$(date +%F).tgz /opt/sigr/app/media          # las fotos no están en la base de datos
```
Los cierres de caja y las facturas son datos contables: no se borran.

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `ImproperlyConfigured: Define DJANGO_SECRET_KEY…` | `DJANGO_DEBUG=0` con la clave por defecto | Definir `DJANGO_SECRET_KEY` en `.env` |
| Error 400 «Bad Request» | Dominio fuera de `DJANGO_ALLOWED_HOSTS` | Agregar el dominio |
| Bucle de redirecciones | HTTPS terminado en nginx sin `DJANGO_BEHIND_PROXY=1` | Activarla y enviar `X-Forwarded-Proto` |
| Swagger UI sin estilos | No se ejecutó `collectstatic` o falta `location /static/` | Ejecutarlo y revisar nginx |
| Las fotos no se ven o no se pueden subir | Falta `location /media/`, `media/` no es escribible por `sigr`, o la foto pesa más de 2 MB | Revisar nginx y permisos |
| 401 en todas las rutas protegidas | Falta la cabecera `Authorization: Token <token>` | Iniciar sesión y enviar el token |
| `password authentication failed` | Credenciales de `.env` distintas a las de PostgreSQL | Corregir `DB_USER`/`DB_PASSWORD` |
| Las pruebas no pueden crear la base | El usuario no tiene `CREATEDB` | `ALTER USER sigr_app CREATEDB;` |

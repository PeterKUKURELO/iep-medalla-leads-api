# I.E.P. Medalla Leads API

API FastAPI para los formularios de Admisión y Contacto de I.E.P. Medalla. Cada solicitud se guarda primero en MySQL y luego intenta enviar, en segundo plano, una notificación administrativa y una confirmación al usuario.

Nombre recomendado del repositorio: **`iep-medalla-leads-api`**.

## Características

- FastAPI y validación estricta con Pydantic.
- MySQL mediante SQLAlchemy y PyMySQL.
- Migraciones con Alembic.
- Correos HTML mediante SMTP con STARTTLS.
- CORS restringido al frontend configurado.
- Host header restringido en producción.
- Límite de cinco solicitudes por minuto e IP.
- Honeypot y límite de cuerpo de 16 KiB.
- Nginx como reverse proxy y HTTPS con Let's Encrypt.
- Ejecución como servicio `systemd` sin usuario root.

## Requisitos locales

- Python 3.11 o superior.
- MySQL 8 o una base remota de testing.

## Instalación local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Copia `.env.example` como `.env.development` y completa únicamente recursos de testing:

```bash
cp .env.example .env.development
```

Los archivos `.env.development`, `.env.test` y `.env.production` están excluidos de Git.

## Subir a GitHub

Crea en GitHub un repositorio vacío llamado `iep-medalla-leads-api`. Después, desde esta carpeta:

```bash
git init -b main
git add .
git status
git commit -m "Initial production-ready leads API"
git remote add origin https://github.com/TU_USUARIO/iep-medalla-leads-api.git
git push -u origin main
```

Antes del commit confirma que ningún archivo `.env` aparezca en `git status`. Las dos plantillas terminadas en `.example` sí deben incluirse.

## Pruebas automáticas

La suite utiliza SQLite descartable y SMTP desactivado. No usa MySQL ni correo de producción.

```bash
APP_ENV=test .venv/bin/python -m pytest --cov=app
```

## Inicio local

Aplica la migración solamente cuando la base de testing esté vacía o Alembic ya gestione su esquema:

```bash
APP_ENV=development .venv/bin/alembic upgrade head
APP_ENV=development .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Servicios locales:

- API: `http://127.0.0.1:8000`
- Salud: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

## API para el frontend

### `GET /health`

Respuesta `200`:

```json
{
  "status": "ok",
  "database": "ok"
}
```

Si MySQL no está disponible devuelve `503` sin exponer detalles internos.

### `POST /api/v1/leads`

Admisión:

```json
{
  "formType": "admission",
  "fullName": "María López Torres",
  "phone": "+51 999 999 999",
  "email": "maria@example.com",
  "educationLevel": "Inicial",
  "grade": "4 años",
  "privacyAccepted": true,
  "sourceUrl": "/admision",
  "utmSource": "facebook",
  "utmMedium": "social",
  "utmCampaign": "matricula-2026",
  "companyWebsite": ""
}
```

Valores válidos:

- `Inicial`: `3 años`, `4 años`, `5 años`.
- `Primaria`: `1° grado` hasta `6° grado`.

Contacto:

```json
{
  "formType": "contact",
  "fullName": "Carlos Ramírez",
  "phone": "988 888 888",
  "email": "carlos@example.com",
  "contactReason": "Información académica",
  "message": "Deseo información sobre la matrícula.",
  "privacyAccepted": true,
  "sourceUrl": "/contacto",
  "companyWebsite": ""
}
```

Respuesta `201`:

```json
{
  "success": true,
  "message": "Recibimos tus datos correctamente.",
  "leadId": 123
}
```

Códigos relevantes:

- `201`: lead guardado.
- `413`: cuerpo mayor de 16 KiB.
- `422`: datos inválidos o campos desconocidos.
- `429`: límite de solicitudes alcanzado.
- `500`: no fue posible guardar el lead.

El campo oculto `companyWebsite` es un honeypot y debe permanecer vacío. No existen endpoints públicos para listar, editar o eliminar leads.

## Variables de producción

En el servidor, copia la plantilla y edítala:

```bash
cp .env.production.example .env.production
chmod 640 .env.production
```

Variables importantes:

- `APP_ENV=production`
- `FRONTEND_ORIGINS`: solo URLs HTTPS del sitio público.
- `ALLOWED_HOSTS`: dominio de la API, sin comodines.
- `DB_USE_TLS=true`
- `MAIL_PASSWORD`: contraseña de aplicación de Google, no la contraseña normal.
- `DOCS_ENABLED=false`

No subas `.env.production`, contraseñas, certificados ni respaldos SQL al repositorio.

## Despliegue en CentOS Stream 9

La guía usa:

- Ruta: `/opt/iep-medalla-leads-api`
- Usuario de servicio: `medalla-api`
- API interna: `127.0.0.1:8000`
- Dominio público: `api.iepmedalla.com`

### 1. DNS

Crea un registro DNS tipo `A`:

```text
api.iepmedalla.com -> IP_PUBLICA_DEL_SERVIDOR_CENTOS
```

El dominio debe resolver al servidor y los puertos 80/443 deben estar accesibles antes de solicitar el certificado.

### 2. Paquetes del servidor

```bash
sudo dnf install -y git nginx firewalld policycoreutils-python-utils \
  python3.11 python3.11-pip python3.11-devel gcc
```

Comprueba la versión:

```bash
python3.11 --version
```

### 3. Usuario y código

```bash
sudo useradd --system --home-dir /opt/iep-medalla-leads-api --shell /sbin/nologin medalla-api
sudo git clone https://github.com/TU_USUARIO/iep-medalla-leads-api.git /opt/iep-medalla-leads-api
sudo chown -R medalla-api:medalla-api /opt/iep-medalla-leads-api
cd /opt/iep-medalla-leads-api
```

Instala el proyecto:

```bash
sudo -u medalla-api python3.11 -m venv .venv
sudo -u medalla-api .venv/bin/python -m pip install --upgrade pip
sudo -u medalla-api .venv/bin/python -m pip install .
```

### 4. Secretos de producción

```bash
sudo -u medalla-api cp .env.production.example .env.production
sudo chown root:medalla-api .env.production
sudo chmod 640 .env.production
sudoedit .env.production
```

Reemplaza todas las variables que comienzan con `REEMPLAZAR_`. Las credenciales compartidas por chat deben rotarse antes del despliegue definitivo.

Valida la configuración sin iniciar el servidor:

```bash
sudo -u medalla-api env APP_ENV=production .venv/bin/python -c "from app.config import Settings; Settings(); print('Configuracion valida')"
```

### 5. Migración de base de datos

Primero consulta el estado:

```bash
sudo -u medalla-api env APP_ENV=production .venv/bin/alembic current
```

Si la base está vacía o ya está controlada por Alembic:

```bash
sudo -u medalla-api env APP_ENV=production .venv/bin/alembic upgrade head
```

Si ya existe una tabla `leads` creada por otro sistema, detente y compara su estructura con `app/models/lead.py`. No ejecutes la migración inicial ni uses `alembic stamp` hasta verificar que las columnas coincidan.

### 6. Servicio systemd

```bash
sudo cp deploy/systemd/iep-medalla-leads-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iep-medalla-leads-api
sudo systemctl status iep-medalla-leads-api
```

La aplicación utiliza un solo proceso porque el limitador actual vive en memoria. Antes de usar múltiples workers debe migrarse el rate limit a Redis u otro almacenamiento compartido.

Comprueba el servicio interno:

```bash
curl http://127.0.0.1:8000/health
```

### 7. Nginx y SELinux

```bash
sudo cp deploy/nginx/api.iepmedalla.com.conf /etc/nginx/conf.d/
sudo setsebool -P httpd_can_network_connect 1
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

Abre el firewall:

```bash
sudo systemctl enable --now firewalld
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

Comprueba HTTP antes de solicitar el certificado:

```bash
curl http://api.iepmedalla.com/health
```

### 8. Certificado SSL con Certbot

Instala Certbot en un entorno aislado:

```bash
sudo dnf install -y python3 python3-devel augeas-devel gcc
sudo python3 -m venv /opt/certbot
sudo /opt/certbot/bin/pip install --upgrade pip
sudo /opt/certbot/bin/pip install certbot certbot-nginx
sudo ln -s /opt/certbot/bin/certbot /usr/local/bin/certbot
```

Solicita el certificado y obliga la redirección a HTTPS:

```bash
sudo certbot --nginx \
  --domain api.iepmedalla.com \
  --email info@iepmedalla.com \
  --agree-tos \
  --no-eff-email \
  --redirect
```

Instala la renovación automática incluida en el repositorio:

```bash
sudo cp deploy/cron/certbot-renew /etc/cron.d/certbot-renew
sudo chmod 644 /etc/cron.d/certbot-renew
sudo certbot renew --dry-run
```

Verifica el resultado:

```bash
curl -i https://api.iepmedalla.com/health
```

### 9. Verificación final

```bash
sudo systemctl status iep-medalla-leads-api nginx
sudo journalctl -u iep-medalla-leads-api -n 100 --no-pager
curl -i https://api.iepmedalla.com/health
```

En producción `/docs`, `/redoc` y `/openapi.json` están desactivados.

## Actualizaciones

```bash
cd /opt/iep-medalla-leads-api
sudo -u medalla-api git pull --ff-only
sudo -u medalla-api .venv/bin/python -m pip install .
sudo -u medalla-api env APP_ENV=production .venv/bin/alembic upgrade head
sudo systemctl restart iep-medalla-leads-api
curl -i https://api.iepmedalla.com/health
```

## Logs y reintento de correos

```bash
sudo journalctl -u iep-medalla-leads-api -f
sudo -u medalla-api env APP_ENV=production .venv/bin/python -m app.retry_emails --limit 50
```

Un fallo SMTP no elimina el lead. Los estados de correo quedan como `failed` y pueden reintentarse posteriormente.

## Seguridad

- La API nunca debe exponerse directamente por el puerto 8000.
- MySQL y SMTP solo se configuran en `.env.production`.
- La contraseña de Gmail debe ser una contraseña de aplicación.
- Rota inmediatamente cualquier credencial publicada en chats, tickets o commits.
- Mantén CentOS, Nginx, Python y Certbot actualizados.

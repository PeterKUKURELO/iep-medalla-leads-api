# Despliegue en CentOS

Guía para desplegar `iep-medalla-leads-api` en el servidor `217.196.61.5` utilizando:

- CentOS Stream 9.
- Python 3.11.
- Uvicorn administrado por systemd.
- Nginx como reverse proxy.
- Certificado SSL de Let's Encrypt con Certbot.
- Dominio `api.iepmedalla.com`.

> No copies contraseñas dentro del repositorio. Las credenciales compartidas por chat deben rotarse antes del despliegue.

## Checklist

- [ ] Repositorio creado en GitHub como `iep-medalla-leads-api`.
- [ ] Código enviado a la rama `main`.
- [ ] Registro DNS `api.iepmedalla.com` apuntando a `217.196.61.5`.
- [ ] Nueva contraseña MySQL creada.
- [ ] Acceso remoto MySQL permitido desde `217.196.61.5`.
- [ ] Contraseña de aplicación de Google disponible.
- [ ] Puertos 22, 80 y 443 habilitados.
- [ ] Migración revisada antes de ejecutarse.
- [ ] Certificado SSL instalado y renovación comprobada.

## 1. Conexión SSH

Desde una terminal local:

```bash
ssh root@217.196.61.5
```

Si el proveedor utiliza un puerto SSH diferente:

```bash
ssh -p PUERTO root@217.196.61.5
```

La primera conexión solicitará confirmar la huella del servidor. Escribe `yes` después de verificar que la IP sea correcta. La contraseña o llave SSH debe obtenerse directamente del proveedor y nunca almacenarse en Git.

Comprueba el sistema:

```bash
cat /etc/os-release
whoami
```

Los siguientes comandos asumen que la sesión es `root`. Si se utiliza otro usuario administrativo, anteponer `sudo`.

## 2. DNS

Crear el siguiente registro en el proveedor DNS de `iepmedalla.com`:

```text
Tipo: A
Nombre: api
Valor: 217.196.61.5
TTL: automático
```

Comprobar desde un equipo local:

```bash
dig +short api.iepmedalla.com
```

La respuesta debe incluir:

```text
217.196.61.5
```

El dominio debe resolver correctamente antes de solicitar el certificado SSL.

## 3. Paquetes del servidor

```bash
dnf install -y git nginx firewalld nano \
  policycoreutils-python-utils \
  python3.11 python3.11-pip python3.11-devel gcc
```

Comprobar Python:

```bash
python3.11 --version
```

El proyecto requiere Python 3.11 o superior.

## 4. Usuario y descarga del proyecto

```bash
useradd --system \
  --home-dir /opt/iep-medalla-leads-api \
  --shell /sbin/nologin \
  medalla-api
```

Clonar el repositorio, reemplazando `TU_USUARIO`:

```bash
git clone https://github.com/TU_USUARIO/iep-medalla-leads-api.git \
  /opt/iep-medalla-leads-api
```

Si el repositorio es privado, utilizar un Personal Access Token de GitHub o una deploy key. No utilizar la contraseña normal de GitHub.

```bash
chown -R medalla-api:medalla-api /opt/iep-medalla-leads-api
cd /opt/iep-medalla-leads-api
```

## 5. Dependencias de Python

```bash
sudo -u medalla-api python3.11 -m venv .venv
sudo -u medalla-api .venv/bin/python -m pip install --upgrade pip
sudo -u medalla-api .venv/bin/python -m pip install .
sudo -u medalla-api .venv/bin/python -m pip check
```

## 6. Variables de producción

Crear el archivo secreto desde la plantilla incluida:

```bash
sudo -u medalla-api cp .env.production.example .env.production
chown root:medalla-api .env.production
chmod 640 .env.production
nano .env.production
```

Completar todos los valores que comienzan con `REEMPLAZAR_`. La estructura esperada es:

```env
APP_ENV=production
APP_NAME=Medalla Leads API
FRONTEND_ORIGINS=["https://iepmedalla.com","https://www.iepmedalla.com"]
ALLOWED_HOSTS=["api.iepmedalla.com","127.0.0.1","localhost"]
DOCS_ENABLED=false

DB_HOST=srv775.hstgr.io
DB_PORT=3306
DB_NAME=u411722909_iepmedalla
DB_USER=REEMPLAZAR_USUARIO_MYSQL
DB_PASSWORD=REEMPLAZAR_PASSWORD_MYSQL
DB_USE_TLS=true

MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=info@iepmedalla.com
MAIL_PASSWORD=REEMPLAZAR_PASSWORD_DE_APLICACION_GOOGLE
MAIL_FROM=info@iepmedalla.com
MAIL_FROM_NAME=I.E.P. Medalla
MAIL_ADMIN_TO=info@iepmedalla.com
MAIL_REPLY_TO=info@iepmedalla.com
MAIL_USE_TLS=true
MAIL_ENABLED=true

RATE_LIMIT_REQUESTS=5
RATE_LIMIT_WINDOW_SECONDS=60
MAX_BODY_BYTES=16384
```

La contraseña de aplicación de Google debe colocarse como una cadena continua, sin espacios.

Validar sin iniciar la API:

```bash
sudo -u medalla-api env APP_ENV=production \
  .venv/bin/python -c \
  "from app.config import Settings; Settings(); print('Configuracion valida')"
```

## 7. Verificación de MySQL y migración

Antes de migrar, listar las tablas mediante una consulta de solo lectura:

```bash
sudo -u medalla-api env APP_ENV=production \
  .venv/bin/python -c \
  "from sqlalchemy import inspect; from app.database import engine; print(inspect(engine).get_table_names())"
```

Si devuelve una lista vacía, aplicar la migración:

```bash
sudo -u medalla-api env APP_ENV=production \
  .venv/bin/alembic upgrade head
```

Si ya existe `leads`, detenerse y comparar su estructura con `app/models/lead.py`. No ejecutar la migración inicial ni usar `alembic stamp` sin realizar esa revisión.

Consultar el estado de Alembic:

```bash
sudo -u medalla-api env APP_ENV=production \
  .venv/bin/alembic current
```

## 8. Servicio systemd

Instalar la unidad incluida en el repositorio:

```bash
cp deploy/systemd/iep-medalla-leads-api.service \
  /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now iep-medalla-leads-api
systemctl status iep-medalla-leads-api
```

Comprobar la API interna:

```bash
curl http://127.0.0.1:8000/health
```

Respuesta esperada:

```json
{"status":"ok","database":"ok"}
```

Si falla:

```bash
journalctl -u iep-medalla-leads-api -n 100 --no-pager
```

## 9. Nginx y SELinux

```bash
cp deploy/nginx/api.iepmedalla.com.conf \
  /etc/nginx/conf.d/

setsebool -P httpd_can_network_connect 1
nginx -t
systemctl enable --now nginx
systemctl reload nginx
```

Comprobar HTTP:

```bash
curl -i http://api.iepmedalla.com/health
```

## 10. Firewall

Mantener abierta la sesión SSH actual mientras se configura el firewall:

```bash
systemctl enable --now firewalld
firewall-cmd --permanent --add-service=ssh
firewall-cmd --permanent --add-service=http
firewall-cmd --permanent --add-service=https
firewall-cmd --reload
firewall-cmd --list-services
```

Antes de cerrar la sesión actual, abrir otra terminal y confirmar una nueva conexión:

```bash
ssh root@217.196.61.5
```

## 11. Certbot y certificado SSL

```bash
dnf install -y python3 python3-devel augeas-devel gcc
python3 -m venv /opt/certbot
/opt/certbot/bin/pip install --upgrade pip
/opt/certbot/bin/pip install certbot certbot-nginx
ln -s /opt/certbot/bin/certbot /usr/local/bin/certbot
certbot --version
```

Solicitar el certificado y activar la redirección HTTPS:

```bash
certbot --nginx \
  --domain api.iepmedalla.com \
  --email info@iepmedalla.com \
  --agree-tos \
  --no-eff-email \
  --redirect
```

Instalar y comprobar la renovación automática:

```bash
cp deploy/cron/certbot-renew /etc/cron.d/certbot-renew
chmod 644 /etc/cron.d/certbot-renew
certbot renew --dry-run
```

## 12. Verificación final

```bash
curl -i https://api.iepmedalla.com/health
systemctl status iep-medalla-leads-api
systemctl status nginx
journalctl -u iep-medalla-leads-api -n 100 --no-pager
```

La API pública debe responder desde HTTPS. El puerto 8000 solo debe escuchar en `127.0.0.1`.

## 13. Prueba controlada del formulario

Este comando crea un registro real en producción y envía los correos configurados:

```bash
curl -i https://api.iepmedalla.com/api/v1/leads \
  -H 'Content-Type: application/json' \
  -d '{
    "formType": "contact",
    "fullName": "Prueba Producción",
    "phone": "999999999",
    "email": "info@iepmedalla.com",
    "contactReason": "Prueba técnica",
    "message": "Validación controlada del formulario en producción.",
    "privacyAccepted": true,
    "sourceUrl": "/prueba-produccion"
  }'
```

Debe responder `201 Created`. Revisar inmediatamente:

```bash
journalctl -u iep-medalla-leads-api -f
```

## 14. Actualizaciones posteriores

```bash
cd /opt/iep-medalla-leads-api
sudo -u medalla-api git pull --ff-only
sudo -u medalla-api .venv/bin/python -m pip install .
sudo -u medalla-api env APP_ENV=production .venv/bin/alembic upgrade head
systemctl restart iep-medalla-leads-api
curl -i https://api.iepmedalla.com/health
```

## Diagnóstico rápido

API:

```bash
systemctl status iep-medalla-leads-api
journalctl -u iep-medalla-leads-api -n 200 --no-pager
```

Nginx:

```bash
nginx -t
systemctl status nginx
journalctl -u nginx -n 100 --no-pager
```

Certificado:

```bash
certbot certificates
certbot renew --dry-run
```

Puertos:

```bash
ss -lntp
```

DNS:

```bash
getent hosts api.iepmedalla.com
```

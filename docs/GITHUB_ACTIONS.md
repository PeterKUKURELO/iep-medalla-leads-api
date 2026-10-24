# Pipeline de GitHub Actions

El repositorio contiene dos workflows:

- `CI`: se ejecuta en pushes a `main` y `cambios-Pet`, y en pull requests hacia
  `main`. Instala Python 3.11, valida dependencias, compila la aplicación y exige
  que las pruebas mantengan al menos 80 % de cobertura.
- `Deploy production`: se ejecuta manualmente y solo desde `main`. Repite las
  pruebas, solicita la aprobación del entorno `production`, despliega exactamente
  el commit probado, ejecuta Alembic, reinicia systemd y comprueba `/health`.

Las contraseñas MySQL y SMTP no se copian a GitHub. Permanecen en el archivo
`/opt/iep-medalla-leads-api/.env.production` del servidor.

## 1. Proteger `main`

En GitHub, abrir **Settings → Branches → Add branch protection rule**:

1. Patrón: `main`.
2. Activar pull request antes de merge.
3. Exigir que pase el check `Tests (Python 3.11)`.
4. Bloquear force pushes y eliminación de la rama.

## 2. Crear el entorno productivo

Abrir **Settings → Environments → New environment** y crear `production`.
Agregar un reviewer obligatorio si el plan y la visibilidad del repositorio lo
permiten. El workflow nunca despliega automáticamente al hacer push.

Crear estos secrets dentro del entorno `production`:

| Secret | Contenido |
| --- | --- |
| `PRODUCTION_SSH_HOST` | Host o IP del servidor. |
| `PRODUCTION_SSH_PORT` | Puerto SSH; normalmente `22`. |
| `PRODUCTION_SSH_USER` | Usuario dedicado de despliegue. |
| `PRODUCTION_SSH_PRIVATE_KEY` | Llave privada Ed25519 exclusiva del pipeline. |
| `PRODUCTION_SSH_KNOWN_HOSTS` | Línea `known_hosts` cuya huella fue verificada. |

No guardar `MIEDU_MAIL_PASSWORD`, contraseñas de base de datos ni el contenido de
`.env.production` como secrets del workflow: el despliegue conserva el archivo ya
protegido en el servidor.

## 3. Preparar el acceso SSH

Usar un usuario dedicado, no la cuenta personal. Debe poder actualizar
`/opt/iep-medalla-leads-api`, ejecutar el entorno virtual y conectarse a la base.
Conceder mediante `sudoers` únicamente estos comandos sin contraseña:

```text
medalla-deploy ALL=(root) NOPASSWD: /usr/bin/systemctl restart iep-medalla-leads-api, /usr/bin/systemctl is-active iep-medalla-leads-api
```

Confirmar las rutas reales con `command -v systemctl` antes de crear la regla.
Instalar la llave pública del pipeline en
`/home/medalla-deploy/.ssh/authorized_keys`. La llave privada se copia una sola vez
al secret `PRODUCTION_SSH_PRIVATE_KEY`.

Obtener la línea de host únicamente después de contrastar la huella SSH con la
consola del proveedor:

```bash
ssh-keyscan -H -p 22 217.196.61.5
```

Guardar la línea verificada como `PRODUCTION_SSH_KNOWN_HOSTS`. No aceptar una
huella desconocida automáticamente dentro del workflow.

## 4. Condiciones del checkout productivo

Antes del primer pipeline, el servidor debe cumplir:

- Repositorio en `/opt/iep-medalla-leads-api`, rama `main` y remoto `origin` válido.
- Sin modificaciones locales en archivos versionados.
- `.venv` creado con Python 3.11 y Alembic instalado.
- `.env.production` completo, protegido y excluido de Git.
- El usuario de despliegue puede escribir el checkout y `.venv`.
- El usuario `medalla-api` puede leer el código y `.env.production`.

El script aborta ante una rama distinta, cambios locales, un commit diferente al
actual `origin/main`, configuración inválida, migración fallida, error de systemd o
fallo de `/health`.

## 5. Ejecutar un despliegue

1. Integrar los cambios a `main` mediante pull request con CI aprobado.
2. Abrir **Actions → Deploy production → Run workflow**.
3. Seleccionar la rama `main`.
4. Aprobar el entorno `production`, si tiene reviewer.
5. Confirmar el resultado del paso `Deploy and verify health`.

La activación inicial de MIEDU requiere además completar la contraseña Titan en el
`.env.production` del servidor y ejecutar primero:

```bash
sudo -u medalla-api env APP_ENV=production \
  .venv/bin/python -m app.check_smtp --profile miedu
```

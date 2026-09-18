# Seguridad

## Controles implementados

- Hosts permitidos y CORS configurables; v2 valida además `Origin` contra la marca cuando la cabecera está presente.
- Modelos con `extra=forbid`, consentimiento estricto y honeypot.
- Límite de body tanto por `Content-Length` como por stream, coordinado con Nginx en 16 KiB.
- Rate limit por IP antes de parsear el body y `Retry-After`. Es deliberadamente local al proceso; el despliegue soportado usa un worker web.
- `X-Request-ID` acepta solo 1–64 caracteres seguros o genera UUID.
- Logs JSON con allowlist. No registrar nombre, email, teléfono, mensaje, documento, domicilio, bodies, secretos, tokens ni connection strings.
- ORM parametrizado y SQLAlchemy `hide_parameters=True`.
- MySQL exige TLS en producción y PyMySQL habilita verificación de certificado e identidad. `DB_SSL_CA` permite fijar la CA del proveedor.
- SMTP STARTTLS usa `ssl.create_default_context()`, timeout y bloqueo de destinatarios reales fuera de producción.
- Configuración interna no forma parte de DTOs públicos; templates solo aceptan nombres locales del registry.

## Límites conocidos

- CORS no autentica clientes no navegador. Ausencia de `Origin` se permite para integraciones servidor-servidor; si no se necesitan, puede endurecerse por policy.
- Rate limit se reinicia y no coordina múltiples procesos. Antes de escalar workers debe implementarse un store compartido o un límite equivalente en gateway/Nginx.
- Honeypot y rate limit reducen abuso, no sustituyen CAPTCHA/WAF si aparece spam sostenido.
- Belsitec y miedu se distribuyen con `enabled=false`; sus destinatarios y orígenes placeholder deben reemplazarse y revisarse antes de activarlas.
- Definir retención, acceso y borrado de PII con el responsable de tratamiento. Reclamos requieren política distinta de leads.

## Variables sensibles

Contraseñas DB/SMTP permanecen solo en `.env.<environment>` protegido. El registry versionado contiene metadatos, no passwords. No incluir certificados privados; `DB_SSL_CA` debe apuntar a un archivo administrado en el host.

## Revisión de producción

### Perfiles SMTP por marca

Cada marca puede declarar `"notifications_enabled": false` para guardar leads sin
enviar correos al equipo ni al usuario. Si se omite, su valor es `true`.
No es un campo aceptado en los payloads públicos. `MAIL_ENABLED` continúa siendo
el interruptor global; mantenerlo en `true` para las otras marcas.
Las marcas sin notificaciones no necesitan credenciales SMTP.

Los nuevos jobs se crean directamente en `disabled`. El worker también comprueba
la configuración antes de enviar jobs existentes: pendientes, fallidos elegibles
o leases vencidos pasan a `disabled`, sin envío ni nuevos retries.
Al reclamar un job existente el contador de intentos puede incrementarse, aunque
se deshabilite antes de SMTP. Jobs fallidos futuros o leases activos se evaluarán
cuando sean elegibles. Un SMTP ya iniciado no puede cancelarse.

Reiniciar la API tras cambiar el registry; workers persistentes también.
Volver a `true` habilita nuevos jobs, pero no reactiva los ya `disabled`:
su recuperación requiere una decisión explícita para evitar correos atrasados.

El campo backend `email_profile` selecciona credenciales independientes. `default`
conserva `MAIL_*`; `medalla`, `belsitec` y `miedu` leen respectivamente
`MEDALLA_MAIL_*`, `BELSITEC_MAIL_*` y `MIEDU_MAIL_*` desde el entorno o
`.env.<environment>`. También se admiten nuevos nombres con letras minúsculas,
números y underscores, comenzando por letra.

Cada perfil requiere `MAIL_HOST`, `MAIL_USERNAME`, `MAIL_PASSWORD` y `MAIL_FROM`
con su prefijo. Puerto 587, STARTTLS y timeout 10 segundos son sus defaults
independientes; nunca hereda credenciales de otra marca. `MAIL_FROM_NAME` es opcional.
El entorno del proceso tiene prioridad sobre el archivo.

`MAIL_ENABLED` sigue siendo el interruptor global. Con envío habilitado, la API y
el worker validan los perfiles de marcas habilitadas antes de aceptar tráfico o
reclamar trabajos. Los perfiles se almacenan en memoria: reiniciar la API y cualquier
worker persistente al rotar credenciales. El worker systemd oneshot los relee en su
próxima ejecución. En producción todos los perfiles deben usar STARTTLS.

Para activar cuentas independientes, copiar los bloques de
`.env.production.example` al archivo protegido del servidor, completar los secretos
y cambiar en el registry: Medalla a `"email_profile": "medalla"`, Belsitec a
`"email_profile": "belsitec"`, miedu a `"email_profile": "miedu"`.
Destinatarios y Reply-To se toman del registry. Solo Medalla con `default` conserva
`MAIL_ADMIN_TO` y `MAIL_REPLY_TO` por compatibilidad.

No requiere migración de DB. Para rollback de configuración, restaurar `default`
y las variables `MAIL_*`, luego reiniciar. No registrar objetos de configuración
ni errores completos de validación con secretos.

Validar hostname/CA MySQL, STARTTLS SMTP, SPF/DKIM/DMARC, orígenes exactos, headers de Nginx, logs de acceso sin query strings sensibles, permisos de `.env`, un único proceso web y timer del worker. Probar errores sin exponer detalles y confirmar que OpenAPI está deshabilitado si así lo exige operación.

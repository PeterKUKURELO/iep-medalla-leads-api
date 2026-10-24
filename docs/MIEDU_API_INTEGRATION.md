# Integración de miedu.pe con Leads API

Esta guía describe el contrato que debe usar el frontend de miedu.pe para registrar solicitudes de demo y contactos comerciales.

## URL base

Mientras el certificado de `api.iepmedalla.com` no incluya ese dominio, usar la URL que actualmente tiene TLS válido:

```text
https://srv475849.hstgr.cloud
```

No desactivar la validación TLS en el frontend.

## Endpoint de leads

```http
POST /api/v2/leads
Content-Type: application/json
```

URL completa:

```text
https://srv475849.hstgr.cloud/api/v2/leads
```

No requiere token de autenticación. El navegador envía automáticamente el encabezado `Origin`; solo se aceptan `https://miedu.pe` y `https://www.miedu.pe` para la marca `miedu-pe`.

## Campos comunes

| Campo | Tipo | Obligatorio | Regla |
| --- | --- | --- | --- |
| `brand` | string | Sí | Siempre `miedu-pe`. |
| `formType` | string | Sí | `demo_request` o `sales_contact`. |
| `sourceKey` | string | No | Identificador del CTA, máximo 100 caracteres. |
| `fullName` | string | Sí | Entre 3 y 150 caracteres. |
| `email` | string | Sí | Correo válido; el backend lo normaliza a minúsculas. |
| `phoneCountry` | string | Sí | Código de dos letras, por ejemplo `PE`; se normaliza a mayúsculas. |
| `phone` | string | Sí | Debe contener entre 7 y 15 dígitos. Puede incluir espacios, guiones y prefijo `+`. |
| `organizationName` | string | Sí | Entre 2 y 200 caracteres. |
| `jobTitle` | string | Sí | Entre 2 y 120 caracteres. |
| `privacyAccepted` | boolean | Sí | Debe ser `true`. |
| `message` | string | No | Entre 5 y 2000 caracteres cuando se envía. |
| `sourceUrl` | string | No | URL o ruta de origen, máximo 500 caracteres. |
| `utmSource` | string | No | Máximo 100 caracteres. |
| `utmMedium` | string | No | Máximo 100 caracteres. |
| `utmCampaign` | string | No | Máximo 150 caracteres. |
| `utmContent` | string | No | Máximo 150 caracteres. |
| `utmTerm` | string | No | Máximo 150 caracteres. |
| `data` | object | Sí | Depende de `formType`. |

Los campos desconocidos son rechazados. El campo honeypot `companyWebsite` debe omitirse o permanecer vacío.

## Solicitud de demo

Usar `formType: "demo_request"`. Dentro de `data` son obligatorios:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `studentRange` | string | Entre 1 y 50 caracteres. |
| `primaryNeed` | string | Entre 1 y 100 caracteres. |

Ejemplo:

```json
{
  "brand": "miedu-pe",
  "formType": "demo_request",
  "sourceKey": "hero_demo",
  "fullName": "María García",
  "email": "direccion@colegioejemplo.edu.pe",
  "phoneCountry": "PE",
  "phone": "999 999 999",
  "organizationName": "Colegio Ejemplo",
  "jobTitle": "Directora",
  "privacyAccepted": true,
  "sourceUrl": "/demo",
  "utmSource": "google",
  "utmMedium": "cpc",
  "utmCampaign": "admision-2027",
  "data": {
    "studentRange": "201–500",
    "primaryNeed": "Admisión"
  }
}
```

Prueba con cURL:

```bash
curl -i https://srv475849.hstgr.cloud/api/v2/leads \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://miedu.pe' \
  --data '{"brand":"miedu-pe","formType":"demo_request","sourceKey":"hero_demo","fullName":"María García","email":"direccion@colegioejemplo.edu.pe","phoneCountry":"PE","phone":"999999999","organizationName":"Colegio Ejemplo","jobTitle":"Directora","privacyAccepted":true,"sourceUrl":"/demo","data":{"studentRange":"201–500","primaryNeed":"Admisión"}}'
```

## Contacto comercial

Usar `formType: "sales_contact"`. El objeto `data` es obligatorio, pero sus campos son opcionales:

| Campo | Tipo | Regla |
| --- | --- | --- |
| `city` | string | Entre 1 y 100 caracteres cuando se envía. |
| `schedule` | string | Entre 1 y 100 caracteres cuando se envía. |
| `primaryNeed` | string | Entre 1 y 100 caracteres cuando se envía. |

Ejemplo:

```json
{
  "brand": "miedu-pe",
  "formType": "sales_contact",
  "sourceKey": "pricing",
  "fullName": "Luis Pérez",
  "email": "luis@colegioejemplo.edu.pe",
  "phoneCountry": "PE",
  "phone": "988888888",
  "organizationName": "Colegio Ejemplo",
  "jobTitle": "Administrador",
  "privacyAccepted": true,
  "message": "Deseo conocer los planes disponibles.",
  "sourceUrl": "/precios",
  "data": {
    "city": "Lima",
    "schedule": "Mañana",
    "primaryNeed": "Gestión académica"
  }
}
```

## Ejemplo desde el frontend

El navegador agrega `Origin` automáticamente; no se debe configurar manualmente.

```js
const response = await fetch(
  "https://srv475849.hstgr.cloud/api/v2/leads",
  {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      brand: "miedu-pe",
      formType: "demo_request",
      sourceKey: "footer_demo",
      fullName: form.name,
      email: form.email,
      phoneCountry: "PE",
      phone: form.phone,
      organizationName: form.school,
      jobTitle: form.role,
      privacyAccepted: form.privacy,
      sourceUrl: window.location.pathname,
      data: {
        studentRange: form.students,
        primaryNeed: form.need,
      },
    }),
  },
);

const result = await response.json();

if (!response.ok) {
  throw new Error(result.detail ?? "No se pudo registrar la solicitud.");
}

console.log(result.leadId);
```

## Respuesta exitosa

La API responde `201 Created` después de guardar el lead:

```json
{
  "success": true,
  "message": "Recibimos tus datos correctamente.",
  "leadId": 123
}
```

El envío de correo ocurre fuera de la respuesta HTTP. Un lead guardado conserva su `leadId` aunque posteriormente falle una notificación.

## Nombres compatibles del frontend actual

Aunque se recomienda el contrato canónico anterior, el backend también convierte estos nombres:

| Nombre actual | Nombre canónico |
| --- | --- |
| `name` | `fullName` |
| `school` | `organizationName` |
| `role` | `jobTitle` |
| `privacy` | `privacyAccepted` |
| `students` | `data.studentRange` |
| `need` | `data.primaryNeed` |
| `city` | `data.city` |
| `schedule` | `data.schedule` |

No enviar simultáneamente un alias y su nombre canónico.

## Errores esperados

| Estado | Significado |
| --- | --- |
| `201` | Lead creado correctamente. |
| `403` | Marca deshabilitada u origen no permitido. |
| `413` | Cuerpo mayor al límite configurado. |
| `422` | Campos inválidos, ausentes, desconocidos o combinación de formulario incorrecta. |
| `429` | Límite de solicitudes excedido. |
| `500` | No se pudo guardar el lead. |

No reintentar automáticamente respuestas `403`, `413` o `422`. Para `429`, respetar el encabezado `Retry-After`.

## Estado productivo de miedu.pe

El registro actual contiene:

```json
{
  "key": "miedu-pe",
  "enabled": true,
  "notifications_enabled": false,
  "email_profile": "miedu"
}
```

Por tanto, las solicitudes se guardan en la base de datos, pero los correos de administrador y usuario se crean con estado `disabled` y no se envían.

Para aceptar solicitudes desde el navegador, `.env.production` también debe incluir ambos orígenes en la lista global de CORS:

```env
FRONTEND_ORIGINS=["https://miedu.pe","https://www.miedu.pe"]
```

Si la API también atiende otros sitios, conservar sus orígenes dentro del mismo arreglo; no reemplazarlos.

Para activar los correos se requiere:

1. Confirmar el buzón `contacto@miedu.pe` en Titan Webmail.
2. En Titan Webmail, abrir **Configuración → Configurar aplicaciones de terceros**
   y habilitar el acceso. Si la cuenta tiene 2FA, generar una contraseña de
   aplicación; de lo contrario se usa la contraseña del buzón.
3. Completar todas las variables `MIEDU_MAIL_*` en `.env.production` usando
   `smtp.titan.email`, puerto `587`, STARTTLS y el correo completo como usuario.
4. Validar desde el servidor, sin enviar un mensaje:

   ```bash
   sudo -u medalla-api env APP_ENV=production \
     .venv/bin/python -m app.check_smtp --profile miedu
   ```

5. Cambiar `notifications_enabled` a `true` para `miedu-pe` en `app/config/brands.json`.
6. Reiniciar `iep-medalla-leads-api`. El worker `oneshot` leerá la configuración en
   su siguiente ejecución.
7. Enviar un lead controlado y revisar el estado de sus dos notificaciones y los
   logs del worker. Los jobs creados anteriormente como `disabled` no se reactivan
   automáticamente.

No usar el puerto `465` con `MIEDU_MAIL_USE_TLS=true`: ese puerto inicia TLS desde
la apertura de la conexión, mientras esta aplicación usa STARTTLS explícito sobre
el puerto `587`.

## Comprobación de salud

```http
GET /health
```

```bash
curl -i https://srv475849.hstgr.cloud/health
```

Respuesta esperada:

```json
{"status":"ok","database":"ok"}
```

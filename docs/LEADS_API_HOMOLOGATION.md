# Homologación de Leads API

## Compatibilidad v1

`POST /api/v1/leads` no exige `brand`. El mapper fija `iep-medalla` y mantiene aliases, normalización, `201`, mensajes de error, honeypot y validaciones admission/contact. El lead se confirma antes del procesamiento de email.

## Contrato v2

Las combinaciones aceptadas son:

IEP Medalla está activa en el registry incluido. Belsitec y miedu están implementadas pero parten con `enabled=false` hasta configurar y aprobar sus orígenes/destinatarios reales; la tabla siguiente describe sus contratos al activarlas.

| brand | formType | data específico |
| --- | --- | --- |
| `iep-medalla` | `admission` | `educationLevel`, `grade` |
| `iep-medalla` | `contact` | `contactReason`; `message` es común |
| `belsitec` | `meeting_request` | `contactDescription` opcional |
| `miedu-pe` | `demo_request` | `studentRange`, `primaryNeed` |
| `miedu-pe` | `sales_contact` | `city`, `schedule`, `primaryNeed` opcionales |

Los campos comunes son `sourceKey`, `fullName`, `email`, `phoneCountry`, `phone`, `organizationName`, `jobTitle`, `message`, consentimiento, URL y UTM. Campos desconocidos retornan `422`. Origen no permitido retorna `403`. La marca se declara; nunca se infiere de URL.

Ejemplo Medalla admission:

```json
{"brand":"iep-medalla","formType":"admission","fullName":"María López","email":"maria@example.com","phone":"999999999","privacyAccepted":true,"data":{"educationLevel":"Inicial","grade":"4 años"}}
```

Ejemplo Belsitec meeting:

```json
{"brand":"belsitec","formType":"meeting_request","sourceKey":"contact_section","fullName":"Ana Pérez","jobTitle":"Directora","organizationName":"Colegio Uno","phone":"999999999","email":"ana@example.com","privacyAccepted":true,"data":{"contactDescription":"Deseo coordinar una reunión."}}
```

Ejemplo miedu sales contact:

```json
{"brand":"miedu-pe","formType":"sales_contact","sourceKey":"pricing","fullName":"Luis Pérez","organizationName":"Colegio Dos","phoneCountry":"PE","phone":"988888888","email":"luis@example.com","jobTitle":"Administrador","privacyAccepted":true,"data":{"city":"Lima","schedule":"Mañana"}}
```

## Belsitec

La policy actual clasifica como `prioritario` cuando hay institución, correo no público y cargo decisor; `evaluacion` cuando hay institución o cargo decisor; e `informativo` en otro caso. Está aislada en `app/policies/belsitec.py`. Esta matriz debe confirmarse con negocio antes de activación productiva. No se inventó vendedor ni fecha de seguimiento: permanecen nulos hasta recibir catálogo y SLA reales; el frontend no puede enviarlos.

## miedu.pe

Además del contrato canónico, el mapper admite los nombres actuales `name`, `school`, `students`, `role`, `need`, `privacy`, `city` y `schedule`. No sintetiza datos ausentes. `sourceKey` identifica el CTA.

## Form data

`form_data` contiene solo el modelo `data` validado. Marca, formulario, nombre, email, teléfono, organización, status y fechas permanecen en columnas consultables. Durante convivencia Medalla también proyecta nivel/grado/motivo en columnas legacy.

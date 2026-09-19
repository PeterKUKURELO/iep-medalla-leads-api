# Análisis de arquitectura actual

Fecha del análisis: 2026-09-11  
Repositorio analizado: `iep-medalla-leads-api`  
Alcance: estado observado antes de modificar código funcional.

## 1. Resumen ejecutivo

El servicio actual es un monolito FastAPI pequeño y orientado exclusivamente a IEP Medalla. Expone un único endpoint de escritura, valida dos formularios con un DTO Pydantic, persiste el lead en una tabla MySQL y programa dos correos mediante `BackgroundTasks`. La base está separada en carpetas de router, schema, repository y service, pero las responsabilidades aún no forman una capa de dominio: el repository depende directamente del DTO HTTP y el service existente solo coordina correo.

La implementación es una base razonable para evolucionar incrementalmente; no requiere reescritura. El principal trabajo consiste en introducir un comando interno independiente de HTTP, configuración validada por marca, persistencia expandida, contratos v2 por `brand + formType` y notificaciones durables. El endpoint v1 puede conservarse como adaptador Medalla sobre ese flujo compartido.

Hallazgos de la línea base:

- `POST /api/v1/leads` acepta solo `admission` y `contact` y responde `201` después del commit del lead.
- `form_type` ya es `VARCHAR(20)`, no `ENUM`; no se necesita conversión desde ENUM en la migración versionada actual. Debe ampliarse su longitud para admitir `meeting_request` y mantenerse validado en aplicación.
- La tabla conserva estados de correo dentro de `leads`; no existe `lead_notifications` ni una cola durable.
- El despacho en `BackgroundTasks` puede perderse si el proceso cae después de responder y antes de ejecutar la tarea.
- El reintento selecciona leads por estado, sin reserva, backoff, máximo de intentos ni protección entre workers.
- MySQL activa `ssl={}` cuando `DB_USE_TLS=true`, sin CA explícita ni evidencia de verificación de hostname.
- SMTP usa STARTTLS, pero no configura de forma explícita un contexto SSL verificable.
- El body limit depende de `Content-Length`; un cuerpo chunked o sin cabecera puede evadirlo en la aplicación.
- El rate limit es en memoria, por IP y por proceso. Se ejecuta después de que FastAPI/Pydantic haya parseado el body.
- No existe validación de `Origin` como política de negocio por marca; CORS por sí solo no protege clientes no navegador.
- El logging es texto plano y no existe `X-Request-ID`.
- Los logs de aplicación observados no incluyen el body ni PII, pero SQLAlchemy no está configurado con `hide_parameters=True`.
- No existe dominio ni endpoint de reclamos.
- La migración inicial crea el esquema correctamente, pero las pruebas usan `Base.metadata.create_all()` sobre SQLite y no prueban Alembic ni MySQL.

## 2. Flujo real de una solicitud

El flujo efectivo no contiene hoy un mapper ni un `LeadService` de creación:

```text
HTTP Request
  ↓
TrustedHostMiddleware
  ↓
CORSMiddleware
  ↓
reject_large_requests (solo Content-Length)
  ↓
Router: POST /api/v1/leads
  ↓
Pydantic LeadCreate (validación, normalización y honeypot)
  ↓
InMemoryRateLimiter (IP del cliente, después del parseo)
  ↓
Repository create_lead(db, LeadCreate)
  ↓
LeadCreate.persistence_data()
  ↓
SQLAlchemy Lead
  ↓
COMMIT MySQL / SQLite en tests
  ↓
HTTP 201 + BackgroundTasks
  ↓
deliver_lead_notifications(lead_id)
  ↓
Nueva Session DB → consulta Lead
  ↓
EmailService
  ├── correo admin → SMTP → actualización estado legacy + COMMIT
  └── correo usuario → SMTP → actualización estado legacy + COMMIT
```

El camino manual de recuperación es:

```text
python -m app.retry_emails
  ↓
SELECT leads con admin/user status pending|failed
  ↓
por cada lead: deliver_lead_notifications
  ↓
SMTP y actualización de columnas legacy
```

No se mantiene una transacción abierta durante el envío SMTP actual. Sin embargo, tampoco existe una reclamación transaccional: dos ejecuciones pueden enviar el mismo correo. Si SMTP acepta el mensaje y el proceso muere antes del commit, el estado permanece pendiente/fallido y un reintento puede duplicarlo. Esto es entrega `at-least-once` en el mejor caso, no exactly-once.

## 3. Inventario y evaluación por archivo

| ARCHIVO | RESPONSABILIDAD | DEPENDENCIAS | ACOPLAMIENTO | PROBLEMA | CAMBIO PROPUESTO | RIESGO | PRIORIDAD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `app/main.py` | Construye FastAPI, middleware, health y routers | Settings, engine, rate limiter, router | Medio | Estado global al importar; límite de body basado solo en cabecera; sin request ID ni logs estructurados; CORS global no distingue marcas | Incorporar middleware seguro y pequeño; conservar app actual y rutas; validar registro al iniciar | Cambiar orden de middleware puede alterar errores/CORS | Alta |
| `app/config.py` | Carga y valida entorno; construye URL SQLAlchemy | Pydantic Settings | Alto con identidad Medalla y un SMTP único | Perfil único; TLS DB débil; `DATABASE_URL` puede eludir opciones esperadas; validaciones numéricas incompletas | Mantener secretos en entorno; agregar ruta/config del registro y perfiles SMTP referenciados; validar CA/hostname y límites | Configuración inválida debe impedir arranque; requiere valores reales de producción | Alta |
| `app/database.py` | Engine, sesión y dependencia DB | Settings, SQLAlchemy | Bajo | `ssl={}` no demuestra validación; `hide_parameters` ausente; objetos globales complican tests de configuración | Endurecer opciones sin introducir factory innecesaria; ocultar parámetros | Un cambio TLS mal configurado puede impedir conexión | Alta |
| `app/rate_limit.py` | Límite por clave en memoria | threading, time | Bajo | Solo un proceso; crecimiento de claves; aplicado tarde; no expone retry-after | Conservar como control básico inicial y documentar alcance; mover aplicación antes del trabajo costoso cuando sea viable | Escalar a varios workers rompe coherencia | Media |
| `app/routers/leads.py` | Endpoint v1, rate limit, persistencia, error y background task | DTO HTTP, repository, notification function | Alto | Orquesta persistencia directamente; no hay service compartido ni mapper; semántica v1 debe congelarse | Convertir en adaptador v1 del `LeadService`; mantener response/status/detail actuales | Regresión del frontend Medalla | Crítica |
| `app/schemas/lead.py` | Contrato y validación v1, normalización, honeypot, datos de persistencia | Pydantic | Alto con persistencia | DTO HTTP sabe cómo persistirse; un solo modelo condicional; nombres internos snake_case mezclados con aliases HTTP | Mantener el schema v1 por compatibilidad; mapper separado a comando; schemas v2 discriminados y específicos | Pydantic unions pueden cambiar forma de errores | Crítica |
| `app/models/lead.py` | Modelo ORM de `leads` | SQLAlchemy Base | Alto con formulario Medalla y estados legacy | Sin marca/source/form_data/campos comunes nuevos; estados de correo embebidos | Expansión aditiva; conservar columnas legacy; JSON para datos específicos; índices selectivos | DDL sobre tabla activa y backfill | Crítica |
| `app/repositories/leads.py` | Crear/cargar lead y actualizar estados legacy | `Lead`, `LeadCreate`, Session | Alto con DTO HTTP | Repository depende de Pydantic HTTP y hace commit interno; dificulta transacción atómica lead+notifications | Recibir comando/datos de dominio y permitir que service controle transacción; conservar helpers temporales | Cambio de límites transaccionales | Alta |
| `app/services/leads.py` | Envía ambas notificaciones y actualiza estados | SessionLocal, repository, EmailService, Settings | Alto con ORM y columnas legacy | No crea leads; nombre sugiere servicio de dominio; correo best-effort no durable | Convertir creación en servicio compartido y separar procesamiento de notificaciones | Doble motor de correo durante transición | Crítica |
| `app/services/email.py` | Render y envío SMTP Medalla | Settings globales, ORM Lead, Jinja2, smtplib | Alto con marca, modelo ORM y plantillas | Identidad/destinatario únicos; recibe ORM; STARTTLS sin contexto explícito; texto contiene PII por necesidad funcional pero no se registra | Resolver perfil y plantillas desde backend por marca; DTO de composición; TLS verificado; nunca aceptar rutas/destinatarios del cliente | Mezcla de identidad entre marcas sería incidente | Crítica |
| `app/retry_emails.py` | Reintento manual de estados pending/failed | ORM Lead, service de correo | Alto con columnas legacy | Sin intentos, fechas, locks, tokens, backoff o concurrencia; puede repetir indefinidamente y priorizar IDs viejos | Sustituir gradualmente por worker de `lead_notifications`; mantener comando compatible durante convivencia | Duplicados SMTP; starvation | Crítica |
| `app/templates/email/new_lead.html` | Correo administrativo Medalla | Atributos ORM de Lead | Alto con campos Medalla | Identidad y etiquetas fijas; no sirve de forma segura como fallback | Plantillas explícitas por configuración de marca/formulario o compartidas con contexto controlado | Escape existe, pero una plantilla errónea puede exponer datos | Alta |
| `app/templates/email/lead_confirmation.html` | Confirmación Medalla | Atributos ORM de Lead | Alto con identidad Medalla | Marca fija | Mantener Medalla y añadir rutas declaradas para cada marca sin fallback cruzado | Identidad incorrecta al usuario | Alta |
| `alembic/env.py` | Conecta metadata y ejecuta migraciones | Settings, engine, modelos importados | Medio | Import manual único; no configura comparación/seguridad adicional; offline expone URL en configuración interna | Importar nuevos modelos; probar upgrade/downgrade en entornos descartables | Cargar Settings durante Alembic puede fallar por diseño fast-fail | Alta |
| `alembic/versions/20260811_01_create_leads.py` | Migración histórica inicial | Alembic, SQLAlchemy | Bajo | No representa campos que docs antiguos atribuyen (`notes`, consentimientos extra); usa VARCHAR para `form_type` | No modificar. Crear revisión incremental aditiva | Alterarla rompería instalaciones aplicadas | Crítica |
| `tests/conftest.py` | Fuerza test, SQLite, limpia tabla y rate limiter | App global, Base metadata | Alto con un solo modelo | Archivo SQLite persistente; no prueba Alembic; no limpia futuras tablas automáticamente; BackgroundTasks se ejecutan dentro de TestClient | Ampliar fixtures preservando aislamiento; añadir pruebas Alembic separadas | SQLite no reproduce DDL/concurrencia MySQL | Alta |
| `tests/test_leads_api.py` | Contrato principal v1 y controles básicos | TestClient, DB | Medio | Buena base pero no congela detalles de respuesta 422 ni persistencia completa; solo un caso contact | Añadir regresión explícita admission/contact antes del refactor | Tests demasiado rígidos pueden bloquear mejoras v2 si se comparten errores | Crítica |
| `tests/test_notification_statuses.py` | Fallo parcial de dos correos | ORM y función de delivery | Alto con implementación legacy | No prueba retries, reinicio, concurrencia ni SMTP aceptado/commit fallido | Conservar durante convivencia; añadir suite de jobs durables | Simular fallos transaccionales requiere cuidado | Alta |
| `tests/test_email_service.py` | Bloqueo de destinatario real en development | Settings, EmailService | Bajo | No prueba SMTP, TLS, encabezados, templates o escaping | Ampliar con SMTP simulado y perfiles por marca | Mock inexacto puede ocultar errores de protocolo | Alta |
| `tests/test_config.py` | Guardas productivas de DB/CORS/host | Settings | Bajo | Cobertura parcial; no valida configuración por marca ni TLS completo | Añadir fast-fail del registry y perfiles | Fixtures deben evitar secretos reales | Alta |
| `README.md` | Uso actual y despliegue Medalla | Implementación y deploy | Medio | Contiene identidad/nombre actual y advertencia correcta de un solo worker; aún no documenta v2 | Actualizar al final preservando instrucciones v1 y transición | Documentación adelantada al código confunde operación | Media |
| `docs/multi-brand-architecture.md` | Diagnóstico/propuesta previa no versionada | Conocimiento del proyecto | Bajo | Es propuesta, no fuente ejecutable; contiene supuestos pendientes | Conservar y alinear al diseño implementado; no sustituye este inventario | Puede divergir del código | Media |
| `docs/MIGRATION_PLAN.md` | Plan previo no versionado | Ninguna | Bajo | Describe columnas que no existen en migración/modelo actual y una meta amplia | Actualizar después de migraciones reales | Instrucciones incorrectas pueden causar daño operativo | Alta |
| `docs/deployment-centos/README.md` | Runbook CentOS actual | systemd, Nginx, Alembic | Medio | Incluye IP/host concretos; worker durable inexistente; migración manual no ensayada | Actualizar al final con orden expand/activate, worker y rollback | Pasos productivos no validados en este entorno | Alta |
| `deploy/systemd/iep-medalla-leads-api.service` | Ejecuta un Uvicorn | Entorno productivo | Bajo | Solo API, un proceso; no worker; hardening parcial | Conservar servicio legacy y añadir unidad/timer del worker cuando exista | Dos workers antiguos/nuevos simultáneos duplican correo | Alta |
| `deploy/nginx/api.iepmedalla.com.conf` | Reverse proxy y límite exterior | Nginx | Bajo | Solo puerto 80 en fuente (Certbot lo muta); límite correcto 16k; dominio legacy debe mantenerse | Conservar dominio v1; documentar/añadir hostname nuevo cuando esté definido | Cambio DNS/cert fuera del repo | Media |
| `compose.yaml` | MySQL 8.4 de testing local | Docker | Bajo | Útil, pero la suite actual no lo usa; volumen persistente | Añadir procedimiento de migración real en DB descartable | Docker puede no estar disponible en CI/local | Media |
| `.env.example` | Config local de muestra | Settings | Medio | Solo Medalla/un SMTP; secreto placeholder correcto | Añadir registry, perfiles y seguridad TLS sin secretos | Defaults inseguros no deben filtrarse a producción | Alta |
| `.env.production.example` | Config productiva de muestra | Settings | Medio | Host productivo concreto; TLS booleano sin CA; solo Medalla | Evolucionar a perfiles y rutas de CA; preservar compatibilidad transitoria | Config incompleta provoca fast-fail | Alta |
| `pyproject.toml` | Dependencias, paquete y pytest | setuptools | Bajo | Nombre/descripcion Medalla; rangos amplios; warning TestClient/httpx | Añadir solo dependencias imprescindibles; renombre lógico posterior | Actualizaciones no fijadas pueden variar comportamiento | Media |

## 4. Contratos observables de v1 que deben congelarse

Para `POST /api/v1/leads` se debe conservar temporalmente:

- Alias JSON camelCase actuales y prohibición de campos desconocidos.
- `formType` obligatorio con valores `admission` o `contact`; no se solicita `brand`.
- `brand = iep-medalla` será una decisión interna del adaptador.
- Normalización de email a minúsculas.
- Normalización de teléfono a dígitos, conservando `+` solo si el valor original comienza con `+`.
- Consentimiento `privacyAccepted=true` obligatorio.
- Honeypot `companyWebsite`: ausente/vacío aceptado; con valor produce `422`.
- Admisión exige nivel y grado válidos y rechaza campos de contacto.
- Contacto exige motivo y mensaje y rechaza nivel/grado.
- Respuesta `201`: `success`, `message` y `leadId`.
- Errores: `422` de FastAPI/Pydantic, `429` con texto actual, `500` genérico de persistencia, `413` para tamaño declarado excesivo.
- El lead se confirma en DB antes de intentar correo; un fallo SMTP no revierte su creación.
- Comportamiento extraño a preservar inicialmente: con SMTP deshabilitado, las dos columnas legacy pasan a `failed`, no a `disabled`.

La suite actual cubre buena parte de estos puntos, pero faltan aserciones completas de persistencia y respuesta para ambos formularios. Esas pruebas deben agregarse en fase 1 antes de cambiar el flujo interno.

## 5. Persistencia y migraciones

La única revisión existente es `20260811_01`. Crea `leads` desde cero y `form_type` como `VARCHAR(20)`. Por tanto:

- no se modificará la revisión histórica;
- la nueva revisión debe ser aditiva;
- se ampliará `form_type` a una longitud suficiente, en vez de realizar una conversión ENUM inexistente en este historial;
- se agregarán `brand_key`, `source_key`, `phone_country`, `organization_name`, `job_title`, `form_data` JSON, `classification`, `assigned_to`, `next_follow_up_at`, `device_type`, `utm_content` y `utm_term`;
- `education_level`, `grade`, `contact_reason` y estados/fechas/error de email permanecerán durante convivencia;
- el backfill a `iep-medalla` solo es seguro si operación confirma que la tabla histórica no recibió otras fuentes. El origen exclusivo del código actual es evidencia, no prueba de los datos productivos;
- para permitir despliegue expand/contract sin downtime, `brand_key` debe agregarse nullable o con default temporal, rellenarse, verificarse y endurecerse en una etapa compatible. La elección final depende de versión MySQL, volumen y capacidad de DDL online;
- los índices deben responder a accesos reales: marca+fecha para operación, marca+formulario+fecha para reporting y estado+próximo intento para worker. Evitar indexar JSON o todas las columnas sin consulta demostrada.

La migración debe probarse con Alembic, no solo `metadata.create_all()`:

1. upgrade completo desde base vacía;
2. upgrade desde `20260811_01`;
3. upgrade con filas admission/contact existentes y verificación de backfill/conservación;
4. verificación de columnas, tipos, nullability e índices;
5. downgrade estructural solo sobre base descartable, documentando que no es rollback operativo si ya hay datos multi-brand.

SQLite permite pruebas rápidas, pero no demuestra semántica DDL, JSON, locks o índices de MySQL. La liberación requiere además MySQL 8.4 descartable (el `compose.yaml` ya ofrece uno).

## 6. Seguridad

### Hallazgos actuales

- CORS restringe navegador, pero no autentica llamadas y no sustituye validación de origen por marca.
- `Origin` puede faltar en clientes no navegador. La política v2 debe decidir explícitamente si los formularios públicos requieren cabecera y cómo tratar integraciones servidor a servidor.
- `TrustedHostMiddleware` está configurado y producción rechaza comodines.
- El límite de body no consume/limita el stream y se evade sin `Content-Length`.
- El rate limit en memoria es aceptable solo con un proceso y reinicia al reiniciar el servicio.
- El honeypot existe y funciona en v1.
- Pydantic prohíbe campos extra, lo que impide inyectar destinatarios/configuración en v1.
- SQLAlchemy parametriza las consultas del ORM; no se observó SQL construido con entrada del usuario.
- No se observan secretos versionados en los archivos inspeccionados; `.env.development` existe localmente y está ignorado.
- La aplicación no registra request body ni PII explícitamente. Los correos contienen PII por su función y deben mantenerse fuera de logs.
- Los mensajes de error SMTP se almacenan truncados en `email_error`; podrían contener detalles del servidor. Los nuevos jobs deben guardar códigos seguros, no respuestas completas potencialmente sensibles.

### Cambios mínimos recomendados

- Request ID validado/generado, respuesta `X-Request-ID` y contexto de log.
- Formato JSON estructurado con allowlist de campos: evento, request ID, lead ID, brand, form type, status, duración, intento y código seguro.
- `hide_parameters=True` en engine.
- Límite de stream independiente de `Content-Length`, coordinado con Nginx.
- Policy de origen por marca/formulario además de CORS; nunca inferir brand desde URL/origin.
- Configuración TLS con CA y verificación de certificado/hostname para MySQL y SMTP.
- Validación positiva de tamaños/límites al iniciar.
- Campos internos (`classification`, asignación, seguimiento, destinatarios, perfiles, templates, estados) ausentes de los DTO públicos y resueltos solo por backend.

## 7. Configuración multi-brand propuesta

Un registro versionado en `config/brands.json` es adecuado porque los metadatos no secretos requieren revisión junto al código. Debe validar al iniciar:

- clave, nombre y estado;
- formularios permitidos;
- orígenes exactos permitidos;
- referencia a perfil SMTP por nombre, nunca credenciales;
- remitente, reply-to y destinatarios administrativos;
- rutas de templates dentro de un catálogo permitido;
- asignación/clasificación por defecto cuando proceda.

Las contraseñas, hosts/usuarios sensibles y CA privadas permanecen en variables de entorno. Cada marca se resuelve de forma estricta: una marca desconocida, desactivada o incompleta falla explícitamente; jamás hereda configuración Medalla.

## 8. Arquitectura incremental recomendada

```text
v1 LeadCreate ── Legacy mapper (brand fijo iep-medalla) ─┐
                                                         ├─ CreateLeadCommand
v2 union brand+formType ── mapper específico ────────────┘
                                                                  ↓
                                                           LeadService
                                                    ┌─────────────┴─────────────┐
                                                    ↓                           ↓
                                             LeadRepository          NotificationRepository
                                                    └─────────────┬─────────────┘
                                                       una transacción DB corta
                                                                  ↓
                                                            HTTP 201

Notification worker
  ↓ reclama transaccionalmente y COMMIT
SMTP fuera de transacción
  ↓
finaliza usando claim_token y COMMIT
```

No se justifican Kafka, RabbitMQ, Redis, Celery, microservicios, CQRS ni event sourcing para el volumen y operación descritos. Una tabla durable y un proceso/timer independiente resuelven recuperación y concurrencia con menor costo operativo.

El diseño no promete exactly-once: si SMTP acepta y el proceso muere antes de marcar `sent`, la reserva expira y el trabajo puede repetirse. Un `Message-ID` estable mejora correlación, pero no garantiza deduplicación del receptor.

## 9. Riesgos y decisiones pendientes

| Riesgo/decisión | Estado | Mitigación requerida |
| --- | --- | --- |
| Datos productivos legacy podrían no ser exclusivamente Medalla | No verificable desde el repositorio | Consulta y aprobación operativa antes del backfill productivo |
| Versión/tamaño/configuración real de MySQL desconocidos | Pendiente | Ensayo en clon/backup y evaluación de DDL online |
| Payloads reales de Belsitec y miedu no están en el repo | Parcialmente especificados por requerimiento | Implementar contratos declarados y validar con fixtures anonimizados antes de integrar frontends |
| Reglas exactas de clasificación Belsitec no incluyen matriz completa | Pendiente | Encapsular policy testeable y no inventar umbrales/reglas no entregados |
| Destinatarios, remitentes, perfiles SMTP, templates y orígenes reales por marca | Pendiente | Placeholders seguros/deshabilitados; activación solo con configuración aprobada |
| Campos exactos del Libro de Reclamaciones no fueron definidos | Pendiente | Crear dominio/tabla solo con contrato legal confirmado; no reutilizar Lead |
| Worker concurrente depende de capacidades MySQL | Pendiente | Usar reclamación condicional/token compatible y probar con MySQL; no basarse en SQLite |
| Rollback tras captar leads de nuevas marcas | Alto | Rollback de aplicación compatible; no eliminar columnas/tablas ni reactivar sender legacy sobre leads multi-brand |

## 10. Resultado de pruebas y cobertura inicial

Comando ejecutado antes de cualquier cambio funcional:

```bash
APP_ENV=test .venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

Resultado: **18 passed**, **83% de cobertura total**, Python 3.11.9.

Cobertura relevante:

- `app/retry_emails.py`: 0%.
- `app/services/email.py`: 70%.
- `app/config.py` y `app/database.py`: 84%.
- `app/routers/leads.py`: 100%.
- `app/schemas/lead.py`: 93%.

Advertencia: Starlette marca como deprecado el uso de `httpx` desde su `TestClient` y sugiere `httpx2`. No afecta la línea base, pero debe resolverse sin mezclarlo con la homologación si requiere un cambio de dependencias.

Las pruebas actuales usan SQLite y no validan MySQL, migraciones Alembic, concurrencia real ni SMTP real.

## 11. Prioridad de ejecución

1. Congelar comportamiento v1 con pruebas de regresión más completas.
2. Introducir comando/mappers y límites transaccionales sin alterar endpoint ni tabla.
3. Crear y probar migración expand con backfill condicionado.
4. Incorporar registro de marcas validado y marcas nuevas inicialmente deshabilitadas donde falte configuración real.
5. Implementar `LeadService` compartido y adaptar v1.
6. Añadir v2 con contratos específicos y campos internos inaccesibles.
7. Crear notificaciones durables y retirar un único camino legacy de despacho de forma controlada.
8. Completar policies Belsitec y contratos miedu con datos confirmados.
9. Crear dominio Complaint independiente con contrato legal confirmado.
10. Endurecer controles transversales, probar MySQL/concurrencia y actualizar runbooks finales.

Este orden mantiene el principio expand-and-contract, conserva Medalla y permite detener la activación de nuevas marcas sin perder compatibilidad ni datos.

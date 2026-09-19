# Homologación de Belsitec Leads API

Estado: propuesta de arquitectura basada en la revisión del repositorio del 8 de septiembre de 2026. Este documento no describe funcionalidades ya implementadas. El alcance es diagnóstico, contrato objetivo y plan de evolución; no se modifican la aplicación ni el despliegue.

## 1. Decisión principal

Evolucionar el servicio como un monolito modular FastAPI, con una base compartida, identificación explícita de marca y un registro de configuración validado al iniciar. Mantener el endpoint actual como adaptador de IEP Medalla y ofrecer un contrato versionado para las integraciones nuevas.

Conservar SQLAlchemy, Alembic, Jinja2, SMTP y las capas existentes. No se justifica crear microservicios, bases por marca, un motor genérico de formularios ni un administrador de tenants para tres marcas operadas por el mismo equipo.

La marca identifica a quién pertenece el lead; el tipo de formulario define sus datos; la landing o campaña identifica el punto de captación. Una landing nueva no requiere convertirse en una marca nueva.

## 2. Funcionamiento observado

1. `app/main.py` carga configuración y motor de base de datos al importar, configura hosts, CORS, documentación y un límite de cuerpo basado en `Content-Length`.
2. `POST /api/v1/leads` recibe `LeadCreate`. Pydantic normaliza email y teléfono, verifica consentimiento, honeypot y reglas de `admission` o `contact`, y rechaza campos desconocidos.
3. La ruta aplica un limitador en memoria por IP después de la validación del cuerpo.
4. El repositorio inserta y confirma el lead antes de programar el correo. La respuesta es `201` con `success`, `message` y `leadId`.
5. `BackgroundTasks` ejecuta las dos notificaciones con una sesión de base propia. Cada envío tiene estado independiente; un fallo SMTP normalmente permite intentar el otro envío.
6. El comando `python -m app.retry_emails` selecciona leads pendientes o fallidos, ordenados por ID, y omite cada notificación ya marcada como enviada.
7. `GET /health` ejecuta `SELECT 1`; devuelve `503` ante un error SQLAlchemy. No verifica SMTP.
8. La configuración de despliegue propone Nginx, Uvicorn en loopback y un proceso bajo systemd. No hay evidencia de que esa configuración esté aplicada en un servidor real.

### Contrato actual que debe preservarse

- Ruta `/api/v1/leads`, JSON plano y respuesta actual, sin exigir marca.
- Tipos `admission` y `contact`; nombre, teléfono, email y aceptación de privacidad obligatorios.
- Admisión: Inicial, de 3 a 5 años; Primaria, de 1° a 6° grado. Contacto: motivo y mensaje obligatorios.
- Los campos de un formulario no son válidos en el otro. Los campos desconocidos producen `422`.
- `sourceUrl` puede ser una ruta relativa. UTM opcionales. Honeypot `companyWebsite` no persistido.
- Normalización actual, incluido el uso de alias camelCase y la aceptación de nombres internos snake_case mediante `populate_by_name`.
- Errores actuales con `detail`; `413`, `422`, `429` y `500`. Persistir correctamente no implica entregar correo.

## 3. Hallazgos y prioridades

| Prioridad | Evidencia | Implicación y acción |
| --- | --- | --- |
| Alta | `app/models/lead.py` no tiene marca | No es posible atribuir ni filtrar confiablemente los leads. Persistir `brand_key` antes de abrir nuevas integraciones. |
| Alta | `app/services/email.py`, plantillas y variables `MAIL_*` usan una identidad global | Riesgo de enviar confirmaciones o notificaciones con la identidad o el destinatario de otra marca. Resolver identidad desde la marca persistida. |
| Alta | `app/database.py` pasa `ssl={}` cuando `DB_USE_TLS=true` | El indicador no demuestra TLS obligatorio con verificación de certificado y hostname. En el PyMySQL instalado, el diccionario vacío entra en modo preferido con posible fallback y contexto sin verificación. Configurar TLS explícito y probarlo con MySQL. |
| Alta | `Settings` permite `MAIL_USE_TLS=false` en producción; SMTP no recibe contexto TLS explícito | Exigir transporte cifrado y contexto con validación del servidor para credenciales de producción. |
| Alta | CORS global sin relación marca/origen | CORS no autentica al remitente ni impide peticiones HTTP directas. Añadir política de origen por marca y conservar controles de abuso independientes. |
| Media | `BackgroundTasks` y reintentos sin reserva del trabajo | Un reinicio deja pendientes; dos ejecuciones pueden enviar el mismo correo. Programar recuperación y reclamar entregas de forma atómica. |
| Media | `update_email_status` puede fallar también dentro del manejador de excepciones | Un error de base al registrar el fallo puede abortar la segunda notificación. Separar los fallos de transporte de los fallos al guardar estado. |
| Media | `email_error` guarda texto de excepciones; `logger.exception` captura fallos SQL | Puede persistirse o registrarse información personal o parámetros SQL. Guardar códigos seguros y ocultar parámetros; truncar no es anonimizar. |
| Media | Formato de logging no incluye los campos de `extra` | `lead_id`, tipo de correo y formulario se pierden en la salida configurada. Usar formato estructurado y correlación. |
| Media | Límite HTTP depende de `Content-Length` | No cubre cuerpos sin esa cabecera dentro de la aplicación. Nginx tiene límite adicional, pero se requiere conteo real de bytes antes de parsear JSON. |
| Media | Limitador conserva claves IP y está dentro de la ruta | Las IP inactivas no se eliminan; cuerpos inválidos no consumen cuota. Aplicar límite previo a validación, con expiración y capacidad acotada. |
| Media | `commit()` seguido de `refresh()` | Si la confirmación se completó y falla el refresco o la respuesta, el cliente puede reintentar y duplicar el lead. Evaluar idempotencia explícita. |
| Media | Protección de entornos ligada a un host y una base de Medalla | No cubre futuras bases productivas ni sus alias; separar credenciales, permisos y recursos por entorno. |
| Media | Tests crean esquema con `metadata.create_all` en SQLite | No validan Alembic, MySQL, TLS ni concurrencia real. Agregar integración con MySQL descartable. |
| Baja | Dependencias con rangos y sin lock visible; documentación específica de Medalla | Fijar una resolución reproducible y separar documentación del servicio de la guía histórica de despliegue. |

Otros matices: `privacyAccepted` es un booleano coercible en v1, no estricto; el teléfono elimina caracteres no numéricos antes de comprobar longitud; no hay idempotencia, autenticación de integraciones ni endpoints de lectura. No endurecer silenciosamente estas reglas en v1 como parte de un cambio de marca.

## 4. Dominio y configuración

### Entidades y responsabilidades

- **BrandConfig**: clave estable, nombre visible, activación de captación, orígenes, formularios permitidos, perfil de correo, destinatarios internos y datos visuales. Inicialmente es configuración versionada, no una tabla editable.
- **Lead**: marca inmutable, datos comunes, datos de formulario, procedencia, consentimiento y fecha de creación. No deduplicar por email: una persona puede consultar varias veces o a varias marcas.
- **Notification**: entrega administrativa o confirmación del usuario, con estado y política de reintento. En la primera expansión pueden conservarse las columnas existentes; la entrega durable se normaliza antes de habilitar nuevas marcas en producción.
- **Form policy**: esquema de datos y reglas del formulario; los catálogos educativos pertenecen al perfil de admisión, no al núcleo de leads.

### Registro inicial propuesto

| Clave estable propuesta | Nombre | Formularios iniciales |
| --- | --- | --- |
| `iep-medalla` | IEP Medalla | `admission`, `contact` |
| `belsitec` | Belsitec | `contact` |
| `miedu-pe` | miedu.pe | `contact` |

El contacto genérico para Belsitec y miedu.pe es una hipótesis de diseño. Sus formularios reales no están presentes en este repositorio. No inventar requisitos de demo, cotización, RUC o productos hasta revisar los frontends.

Usar `config/brands.json` sin secretos, cargado mediante `BRANDS_CONFIG_PATH`, y modelos Pydantic que fallen al inicio ante claves duplicadas, origen inválido, perfil inexistente, plantillas ausentes, correos mal formados o formulario no soportado. Las listas de orígenes deben comparar esquema, host y puerto; prohibir comodines en producción.

Separar:

- Configuración global: base de datos, límites, hosts de la API, logging y entorno.
- Identidad por marca: `display_name`, `from_address`, `from_name`, `reply_to`, `admin_recipients`, asunto y firma.
- Transporte: perfil SMTP y secretos obtenidos del entorno. Varias marcas pueden compartir transporte si el proveedor autoriza sus remitentes; nunca asumir que la cuenta actual de Medalla permite cualquier dominio.

En la transición, las variables `MAIL_*` actuales alimentan exclusivamente el perfil legado de Medalla. No usarlas como fallback para otra marca. Una referencia incompleta impide activar esa marca.

El cliente nunca controla destinatarios administrativos, remitente, ruta de plantilla, perfil SMTP ni estado del lead. Configuración solo desde fuentes administradas por el operador, sin recarga dinámica inicial. Una marca desactivada para captación conserva su configuración para procesar leads previos.

## 5. API objetivo y compatibilidad

### Estrategia de versiones

Mantener `/api/v1/leads` como adaptador legado que asigna siempre `iep-medalla`. Introducir `POST /api/v2/leads` con `brand` obligatorio y datos de formulario separados. Ambos llaman al mismo servicio de creación.

La v2 se justifica por el cambio de estructura y validación. Evita que la ausencia accidental de `brand` en una integración nueva registre leads como Medalla. No inferir marca por `sourceUrl`, UTM, email o `Host` de la API. No añadir `brand` a v1: hoy sus campos desconocidos se rechazan.

### Solicitud v2 propuesta

```json
{
  "brand": "belsitec",
  "formType": "contact",
  "fullName": "Ana Pérez",
  "phone": "+51999999999",
  "email": "ana@example.com",
  "privacyAccepted": true,
  "data": {
    "contactReason": "Información sobre servicios",
    "message": "Deseo información para mi organización."
  },
  "sourceUrl": "/contacto",
  "utmSource": "google",
  "utmMedium": "organic",
  "utmCampaign": "servicios",
  "companyWebsite": ""
}
```

Para Medalla/admisión: `brand="iep-medalla"`, `formType="admission"`, `data={"educationLevel":"Inicial","grade":"4 años"}`. Para miedu.pe/contacto se cambia `brand` a `miedu-pe`.

Definir una unión discriminada por `formType` con esquemas `AdmissionLeadCreate` y `ContactLeadCreate`. `data` es tipado y cerrado, no JSON libre. Reutilizar límites de longitud y normalizaciones de v1 donde son adecuados; v2 requiere el literal booleano `true` para consentimiento. Marca y campos extra se validan estrictamente.

La configuración permite o deniega un formulario conocido para una marca. Agregar una marca con formularios existentes solo requiere configuración y verificación. Un tipo de formulario nuevo requiere esquema, política, renderizado y pruebas: esa modificación explícita mantiene el contrato comprensible.

### Respuestas

`201` conserva una respuesta sencilla:

```json
{"success": true, "message": "Recibimos tus datos correctamente.", "leadId": 123}
```

Significa lead confirmado en base de datos y trabajo de notificación persistido; no promete recepción del correo. Añadir `X-Request-ID` a respuestas y errores.

Para v2, normalizar todos los errores de aplicación y validación:

```json
{
  "error": {
    "code": "FORM_NOT_ALLOWED",
    "message": "El formulario no está habilitado para esta marca.",
    "requestId": "identificador-generado-por-el-servidor"
  }
}
```

| HTTP | Código v2 | Situación |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | JSON o cabeceras malformados |
| 403 | `ORIGIN_NOT_ALLOWED` | Origen presente que no pertenece a la marca |
| 413 | `PAYLOAD_TOO_LARGE` | Límite de bytes excedido |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Contenido distinto de JSON |
| 422 | `VALIDATION_ERROR` | Datos inválidos o campos desconocidos |
| 422 | `BRAND_UNAVAILABLE` | Marca desconocida o deshabilitada |
| 422 | `FORM_NOT_ALLOWED` | Formulario no permitido para la marca |
| 429 | `RATE_LIMITED` | Cuota excedida; incluir `Retry-After` |
| 500 | `PERSISTENCE_ERROR` | No se pudo confirmar la operación |

Los detalles de validación pueden incluir ruta del campo y código seguro, sin devolver el valor enviado. v1 conserva su formato `detail`. Los rechazos generados por Nginx pueden no llevar el envelope JSON; documentarlo para el frontend y manejar respuestas sin JSON.

### Origen y confianza

CORS usa la unión de los orígenes habilitados; en un preflight no se dispone del cuerpo con la marca. Tras recibir el POST, comprobar que un `Origin` presente pertenece específicamente a la marca solicitada, antes de persistir. Rechazar `Origin: null` salvo política explícita.

Para v2 de formularios web, exigir `Origin`; para v1 conservar solicitudes sin `Origin` porque están documentadas y probadas. Un consumidor servidor a servidor futuro debe tener un modo de integración explícito con credencial asociada a marcas y ámbitos. No colocar secretos en JavaScript público.

Un cliente fuera del navegador puede falsificar `Origin`. Esta política previene errores de integración y limita usos desde navegadores; no convierte el formulario público en un canal autenticado. Aplicar límites globales por IP y límites por marca/IP para que cambiar de marca no evada la cuota global. Introducir CAPTCHA con verificación en servidor si el abuso observado lo requiere.

## 6. Organización propuesta

```text
app/
  brands.py                 # registro tipado y resolución de políticas
  config.py                 # entorno y transporte
  routers/leads.py          # adaptador v1
  routers/leads_v2.py       # contrato v2
  schemas/lead.py           # contrato legado preservado
  schemas/lead_v2.py        # unión discriminada y respuesta de errores
  services/leads.py         # creación y coordinación compartidas
  services/notifications.py # recuperación, reserva y estados
  services/email.py         # composición y transporte SMTP
  repositories/leads.py    # operaciones de persistencia sin HTTP
  repositories/notifications.py
  models/lead.py
  models/notification.py
  templates/email/         # plantillas comunes con contexto de marca
config/brands.json
```

Flujo: adaptador HTTP → resolución de marca/política → comando interno validado → transacción de lead y notificaciones → respuesta. Un procesador independiente recupera notificaciones pendientes y usa la marca guardada para componer correo.

El repositorio recibe datos internos, sin depender de un DTO HTTP específico. El servicio controla la transacción compartida. No hacen falta interfaces para cada clase; una separación entre composición y transporte permite probar SMTP sin construir un framework de proveedores.

## 7. Persistencia y migración

Conservar `leads` y sus columnas de negocio iniciales. El JSON anidado de v2 se transforma a esas columnas; no obliga a migrar los datos existentes a JSON. Considerar un campo de detalles versionados solo cuando exista un formulario que lo justifique.

Agregar `brand_key VARCHAR(64) NOT NULL`, con valor inicial y default de servidor `iep-medalla`, e índice compuesto `(brand_key, created_at)`. El default permite temporalmente que la aplicación anterior siga insertando durante una actualización. El código nuevo siempre escribe la marca explícitamente. Retirar ese default cuando termine la convivencia y no sea necesario volver a la versión anterior.

Antes del backfill, comprobar con datos y responsables que todos los registros históricos pertenecen a Medalla; el diseño original lo sugiere, pero no se inspeccionó producción. Si aparecen otras procedencias, resolverlas antes de asignar en bloque. No editar la migración inicial: crear una revisión Alembic incremental.

Para correo durable, agregar `lead_notifications` con:

- `id`, `lead_id` con FK, `kind` y unicidad `(lead_id, kind)`.
- Estado `pending`, `processing`, `sent`, `failed`, `disabled` o `dead`.
- `attempt_count`, `next_attempt_at`, `locked_until`, `claim_token`, `sent_at`, `last_error_code`, `created_at` y `updated_at`.
- Índice para seleccionar por estado y próxima ejecución.

Crear las dos notificaciones en la misma transacción que el lead. Migrar los estados existentes sin reenviar los marcados `sent`. Mientras haya compatibilidad, actualizar las columnas antiguas como proyección de los estados nuevos; no mantener dos motores de envío activos.

Usar UTC de forma consistente y comprobar la zona de sesión de MySQL: actualmente se mezclan timestamps generados por la base con fechas UTC de Python sin zona almacenada. Para nuevas integraciones, registrar versión de política de privacidad si el frontend la conoce y el negocio define su catálogo. No inventar versiones ni atribuirlas a leads históricos; conservar el consentimiento existente. Definir retención y acceso con el responsable de los datos.

No crear endpoints públicos de consulta. Si más adelante hay CRM o panel por marca, toda lectura/exportación necesita autorización y filtros de marca aplicados por el servidor; `brand_key` por sí solo no proporciona aislamiento de acceso.

## 8. Entrega de correo y recuperación

Mantener plantillas compartidas con contexto `lead`, `brand` y etiquetas de formulario. Personalizar asunto, firma, remitente, respuesta y destinatarios desde configuración. Mantener autoescape Jinja2, versión de texto plano y plantillas instaladas con el paquete. Rutas y HTML arbitrarios nunca llegan del formulario.

Para el volumen inicial, usar un comando de procesamiento periódico bajo systemd timer. No hace falta Redis/Celery. El procesador toma un lote, reclama cada trabajo en una transacción breve y envía fuera de ella. Un token de reserva impide que un proceso con una reserva vencida sobrescriba el resultado de otro. El timeout SMTP debe ser inferior a la duración de reserva, con margen.

Definir reintentos acotados con espera creciente y variación aleatoria; por ejemplo, cinco intentos antes de `dead`. Los errores permanentes terminan anticipadamente. Una entrega agotada no debe bloquear los leads posteriores; el comando actual prioriza siempre los IDs antiguos y puede causar ese bloqueo de progreso.

`sent` significa aceptado por el servidor SMTP. Si el proceso muere después del envío pero antes del commit, un reintento puede duplicarlo. La reserva reduce concurrencia, pero SMTP no permite prometer entrega exactamente una vez. Un `Message-ID` estable ayuda a correlacionar; no garantiza deduplicación. Para conocer rebotes o entrega final se requiere soporte del proveedor y, si se incorpora, webhook autenticado.

El envío deshabilitado se representa como `disabled`, sin registrarlo como fallo transitorio. Conservar bloqueo de destinatarios reales fuera de producción y capturar todo correo en un sandbox. Verificar autorización del remitente y configuración de dominio antes de activar cada marca.

La idempotencia HTTP es una mejora independiente: si se incorpora `Idempotency-Key`, asociarla a marca, fingerprint del payload normalizado y respuesta persistida, con restricción única y resolución de carreras en base de datos. Mismo contenido devuelve la respuesta anterior; contenido diferente, `409`. Documentar plazo de retención y permitir la cabecera en CORS. No introducir deduplicación heurística por email.

## 9. Seguridad y observabilidad

Corregir TLS de MySQL y SMTP antes de abrir el servicio a otras marcas. Validar certificado y hostname y fallar si no puede establecerse el transporte seguro. Comprobar que `DATABASE_URL` no permite eludir las reglas del motor productivo.

Implementar límite real de cuerpo y limitador antes del parseo, preservar el límite de Nginx y mantener la confianza de cabeceras de proxy restringida a loopback. El control CORS exterior debe cubrir también respuestas de error de aplicación. Los límites deben ser positivos y validados al iniciar.

Logs estructurados: evento, request ID, lead ID, marca, formulario, HTTP status, duración, tipo de notificación, intento y código de error seguro. No registrar nombre, email, teléfono, mensaje, cuerpo, secretos ni cadenas completas de conexión. Configurar SQLAlchemy para ocultar parámetros en errores y revisar también los logs de acceso del proxy.

Medir leads aceptados y rechazados por marca, latencia de creación, fallos de persistencia, antigüedad del pendiente más antiguo, entregas fallidas y agotadas. Evitar IDs personales o request IDs como etiquetas de métricas. Conservar `/health`; añadir una comprobación de vida sin dependencia de MySQL solo si la operación lo necesita. SMTP se supervisa por cola y fallos, no enviando correos desde health checks.

## 10. Validación y criterios de aceptación

Base ejecutada: `APP_ENV=test .venv/bin/python -m pytest --cov=app`: **18 pruebas aprobadas, cobertura total 83 %**. `app/retry_emails.py` tiene 0 % de cobertura. Se observó una advertencia de deprecación de Starlette/TestClient respecto a httpx. No se probó producción, SMTP real ni MySQL real.

| Área | Evidencia requerida para liberar |
| --- | --- |
| Compatibilidad | Suite v1 sin cambios semánticos; mismo payload, normalización, respuesta, errores y asignación Medalla |
| Contrato v2 | Contacto por las tres marcas; admisión de Medalla; marca ausente/desconocida/desactivada; formulario no permitido; datos extra y consentimiento estricto |
| Separación | Una marca no recibe identidad, destinatarios ni reglas de otra; reintento resuelve la marca persistida |
| Configuración | Fallo al iniciar ante orígenes, perfiles, direcciones o plantillas inválidas; sin fallback de marca |
| Navegador | Preflight, origen cruzado entre marcas, origen ausente según versión, `null`, y cabeceras CORS en errores |
| Abuso | Límite con cuerpo en chunks y sin Content-Length; payload inválido consume cuota; expiración y capacidad del limitador |
| Correo | HTML escapado, texto alternativo, SMTP simulado, TLS configurado, fallo parcial, disabled, reintentos agotados y recuperación tras reinicio |
| Concurrencia | Dos procesadores no reclaman simultáneamente la misma entrega; reserva vencida y fallo después de SMTP tienen comportamiento documentado |
| Migraciones | Alembic desde base vacía y desde esquema existente en MySQL descartable; backfill, índices, estados y conservación de IDs |
| Privacidad | Errores y logs no contienen payload ni parámetros SQL con datos personales |

La cobertura porcentual no sustituye estas verificaciones. Usar OpenAPI y ejemplos de integración como contratos revisables; añadir pruebas de contrato con payloads reales anonimizados de los frontends cuando estén disponibles.

## 11. Secuencia de implementación y puesta en servicio

1. **Asegurar la base:** fijar entorno reproducible, corregir TLS, límites y filtrado de logs; conservar comportamiento funcional de v1.
2. **Expandir:** añadir marca y backfill, registro de configuración, servicio compartido y composición de correo por marca. Mantener solo Medalla activa. Verificar contra el contrato legado.
3. **Añadir v2:** esquemas, validación por marca y documentación. Integrar Belsitec y miedu.pe en testing con SMTP de sandbox.
4. **Hacer durable el correo:** migrar trabajos y estados, detener despachadores antiguos, activar un único camino de envío y probar recuperación. Completar antes de recibir leads nuevos multi-marca en producción.
5. **Activar gradualmente:** verificar configuración real y formularios, activar una marca, observar errores y backlog, y luego activar la siguiente. Mantener `api.iepmedalla.com` para clientes actuales.
6. **Separar identidad operativa:** usar el nombre lógico `belsitec-leads-api`; cambiar repositorio, dominio, directorio y unidad systemd en una entrega independiente cuando estén definidos. No es requisito para compartir el backend.

Antes de migrar producción: respaldo probado, estado Alembic conocido, recuentos de filas y revisión del impacto DDL según versión y tamaño de MySQL. No se evaluaron aquí esas condiciones reales.

Rollback: desactivar captación v2 manteniendo filas y marca; conservar el código de correo que entiende marcas. Antes de activar otras marcas, puede volver temporalmente el binario anterior mientras exista el default de Medalla. Después de tener leads multi-marca, volver al procesador antiguo podría enviar correo con identidad de Medalla: detenerlo y usar una versión correctiva compatible. No ejecutar un downgrade que elimine marca o notificaciones con datos ya captados.

## 12. Información pendiente para activar marcas

- Payloads y reglas reales de los formularios de Belsitec y miedu.pe; obligatoriedad del teléfono y consentimiento.
- Orígenes definitivos por entorno, remitentes autorizados, destinatarios administrativos y perfil SMTP de cada marca.
- Volumen esperado, tolerancia al retraso del correo y si habrá integraciones servidor a servidor.
- Estado real de la base, versión de MySQL, tamaño de `leads`, configuración del servidor y posibles consumidores externos.
- Política de privacidad, versión, retención y responsables de acceso a los datos.

Estos datos condicionan la configuración final y el despliegue; permiten continuar la implementación local con fixtures sin inventar información productiva.

## Referencias técnicas

- [FastAPI: Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/): tareas posteriores a la respuesta y separación de herramientas para otros patrones de procesamiento. La estrategia durable propuesta es una decisión para este servicio.
- [Starlette: Middleware](https://starlette.dev/middleware/): alcance de CORS y recomendación de envolver la aplicación para cubrir errores.
- [PyMySQL: Connection](https://pymysql.readthedocs.io/en/latest/modules/connections.html): opciones de certificado e identidad TLS. El hallazgo sobre `ssl={}` también se contrastó con el código de la dependencia instalada en `.venv`.

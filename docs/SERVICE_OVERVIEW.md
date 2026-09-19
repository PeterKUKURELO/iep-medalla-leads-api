# Service overview

## Propósito

`belsitec-leads-api` es el nombre lógico del monolito modular que centraliza leads de `iep-medalla`, `belsitec` y `miedu-pe`. El nombre físico del repositorio y el hostname Medalla permanecen durante la convivencia.

```text
v1 Medalla ── Legacy mapper ─┐
                             ├─ CreateLeadCommand → LeadService → MySQL
v2 multi-brand ── Mapper ────┘                         │
                                                       └→ lead_notifications
                                                              ↓
                                                        worker → SMTP

Libro de Reclamaciones → /api/v1/complaints → consumer_complaints
```

## Módulos

- `app/schemas`: contratos HTTP estrictos. V2 es una unión discriminada por `formType`; cada variante limita además `brand`.
- `app/domain`: comandos internos sin dependencia de FastAPI/Pydantic.
- `app/brands.py` y `app/config/brands.json`: configuración no secreta y validación fast-fail.
- `app/services/lead_creation.py`: política de marca/origen y transacción de lead más jobs.
- `app/repositories`: persistencia y reclamación atómica.
- `app/services/notifications.py`: envío fuera de transacción, retry y finalización protegida por `claim_token`.
- `app/services/email.py`: composición y SMTP con contexto TLS del sistema.
- `app/policies/belsitec.py`: clasificación aislada y testeable.

## Estados de notificación

`pending → processing → sent`; un error temporal produce `failed` con `next_attempt_at`, un error permanente o el quinto intento produce `dead`, y SMTP apagado produce `disabled`. Un lease `processing` vencido vuelve a ser reclamable. Las columnas `admin_email_*`, `user_email_*` y `email_error` se mantienen como proyección para consumidores legacy.

La reclamación y su commit ocurren antes de SMTP. La finalización usa el mismo token. Si el proceso muere después de que SMTP acepta el correo pero antes del commit, el lease vencerá y puede haber duplicado. No se promete exactly-once.

## Extender el servicio

Para una marca nueva: agregar entrada completa al registry, orígenes, forms, perfil y templates; añadir contratos concretos; mapearlos a `CreateLeadCommand`; probar marca desconocida/deshabilitada, origen, persistencia e identidad de email. Nunca reutilizar Medalla como fallback.

Para un `formType`: crear un modelo `data` específico, una variante con literales `brand/formType`, agregarlo a `LeadV2Payload` y `allowed_forms`, y añadir tests. Los campos consultables siguen en columnas; solo detalles propios del formulario van a `form_data`.

## Ejecución

```bash
APP_ENV=development .venv/bin/alembic upgrade head
APP_ENV=development .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
APP_ENV=development .venv/bin/python -m app.retry_emails --limit 50
```

OpenAPI está en `/openapi.json` y Swagger en `/docs` cuando `DOCS_ENABLED=true`.

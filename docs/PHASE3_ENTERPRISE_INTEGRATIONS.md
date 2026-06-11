# Phase 3 - Enterprise Integrations

Implementacion inicial de Fase 3 enfocada en API-first para DMS, CRM, e-signature y SSO.

## Seguridad SSO

Los endpoints enterprise requieren headers SSO:

- `Authorization: Bearer <LEGALFLOW_SSO_TOKEN>` (opcional si variable no seteada)
- `X-SSO-User: <id_usuario>`
- `X-SSO-Email: <email>`
- `X-SSO-Groups: legal_admin,legal_ops,legal_viewer`

Variable recomendada:

```bash
export LEGALFLOW_SSO_TOKEN="super-secret-token"
```

## Endpoints implementados

### Matters
- `POST /api/matters`
- `POST /api/matters/<matter_id>/approve`
- `POST /api/matters/<matter_id>/sign`
- `GET /api/matters/<matter_id>/obligations`

### Integrations
- `POST /api/integrations/esign/create-envelope`
- `POST /api/integrations/esign/recipient-view`
- `POST /api/integrations/crm/sync`
- `POST /api/integrations/dms/upload`
- `POST /api/integrations/esign/request`

## Almacenamiento (fase inicial)

- Matters: `data/matters/*.json`
- Eventos de integracion: `data/integrations/*.jsonl`

## Nota de arquitectura

Los conectores actuales son `event-log connectors`:
- validan el contrato API-first
- generan referencias externas (`crm_ref`, `dms_ref`, `envelope_id`)
- registran trazabilidad para luego reemplazar por integraciones reales (Salesforce/HubSpot, SharePoint/Drive, DocuSign/Dropbox Sign).

En e-sign se persiste trazabilidad en el matter:
- `esign.envelope_id`
- `esign.recipient_id`
- `esign.signing_url` (cuando se solicita recipient-view)
- `status` estandarizado: `signature_pending`, `signed`, `declined`, `voided`

## Modo real vs modo simulacion (bloqueos por key)

- e-signature usa modo **real** solo si existen:
  - `LEGALFLOW_ESIGN_ENDPOINT`
  - `LEGALFLOW_ESIGN_API_KEY`
- `LEGALFLOW_ESIGN_WEBHOOK_SECRET` es opcional (recomendado para validacion de webhooks).
- `LEGALFLOW_APP_BASE_URL` permite generar URL embebida consistente en simulacion.
- Si falta alguna de esas variables, la API responde en modo:
  - `"mode": "simulation"`
- Si proveedor real falla, se activa:
  - `"mode": "fallback_simulation"`

Esto permite continuar con el resto del flujo sin bloquear la operación.

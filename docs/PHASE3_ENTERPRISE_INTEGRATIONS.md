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

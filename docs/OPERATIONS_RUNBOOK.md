# LegalFlow Operations Runbook

## 1) Deployment
1. Install dependencies:
   - `pip install -r requirements.txt`
2. Run config check:
   - `python scripts/check_runtime_config.py`
3. Start service:
   - `python portal_web.py`
4. Validate runtime:
   - `GET /api/health`
   - `GET /api/health/config`

## 2) Authentication and SSO
Required headers for enterprise endpoints:

- `Authorization: Bearer <LEGALFLOW_SSO_TOKEN>`
- `X-SSO-User: <user_id>`
- `X-SSO-Email: <email>`
- `X-SSO-Groups: legal_admin,legal_ops,legal_viewer`

## 3) Credential matrix and blockers

| Variable | Required | Scope | If missing |
|---|---|---|---|
| `LEGALFLOW_SSO_TOKEN` | Yes (enterprise endpoints) | SSO auth | Enterprise endpoints return auth errors |
| `CURSOR_API_KEY` | No (required only for sdk mode) | Agent SDK | Use `modo=local` fallback |
| `LEGALFLOW_ESIGN_ENDPOINT` | No | Real e-sign provider | e-sign endpoint runs in simulation mode |
| `LEGALFLOW_ESIGN_API_KEY` | No | Real e-sign provider auth | e-sign endpoint runs in simulation mode |

When any optional key is missing:
- Keep endpoint available in fallback mode.
- Log blocker and continue remaining operations.

## 4) End-to-end curl examples

Set helper vars:

```bash
export BASE_URL="https://legalflow-agent.vercel.app"
export LEGALFLOW_SSO_TOKEN="your_token"
```

Analyze contract:

```bash
curl -X POST "$BASE_URL/api/analizar" \
  -F "modo=local" \
  -F "modelo=composer-2.5" \
  -F "cliente_id=default" \
  -F "modo_analisis=general" \
  -F "contrato=Contrato de prestacion de servicios con confidencialidad y multa."
```

Create matter:

```bash
curl -X POST "$BASE_URL/api/matters" \
  -H "Authorization: Bearer $LEGALFLOW_SSO_TOKEN" \
  -H "X-SSO-User: demo-user" \
  -H "X-SSO-Email: demo@legalflow.test" \
  -H "X-SSO-Groups: legal_admin,legal_ops" \
  -H "Content-Type: application/json" \
  -d '{
    "cliente_id": "default",
    "title": "MSA ACME",
    "obligations": [{"title":"Entregar release","due_date":"2026-07-01"}]
  }'
```

Approve matter:

```bash
curl -X POST "$BASE_URL/api/matters/<matter_id>/approve" \
  -H "Authorization: Bearer $LEGALFLOW_SSO_TOKEN" \
  -H "X-SSO-User: approver" \
  -H "X-SSO-Email: approver@legalflow.test" \
  -H "X-SSO-Groups: legal_admin,approver" \
  -H "Content-Type: application/json" \
  -d '{"notes":"approved"}'
```

Request e-signature (real or simulation):

```bash
curl -X POST "$BASE_URL/api/integrations/esign/request" \
  -H "Authorization: Bearer $LEGALFLOW_SSO_TOKEN" \
  -H "X-SSO-User: demo-user" \
  -H "X-SSO-Email: demo@legalflow.test" \
  -H "X-SSO-Groups: legal_admin,legal_ops" \
  -H "Content-Type: application/json" \
  -d '{
    "matter_id": "<matter_id>",
    "signer_email": "legal@acme.com"
  }'
```

## 5) Testing
- Backend smoke tests:
  - `python tests/smoke_enterprise.py`

## 6) Incident response
1. Check `data/audit.jsonl` for auth/workflow errors.
2. Check `data/metrics.jsonl` for latency regressions.
3. If SDK failures occur, switch affected flows to `modo=local`.
4. If e-sign provider fails, confirm fallback mode in `data/integrations/esign_requests.jsonl`.
5. Capture `run_id` and `matter_id` in incident ticket.

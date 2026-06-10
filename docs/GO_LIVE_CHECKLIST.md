# Go-Live Checklist (Backend + Portal + Auth)

## 1) Environment
- [ ] Set `LEGALFLOW_SSO_TOKEN` in runtime environment.
- [ ] (Optional) Set `CURSOR_API_KEY` for SDK mode.
- [ ] (Optional) Set `LEGALFLOW_ESIGN_ENDPOINT` + `LEGALFLOW_ESIGN_API_KEY` for real e-sign.
- [ ] Run:
  - `python scripts/check_runtime_config.py`

## 2) Health checks
- [ ] `GET /api/health` returns `ok: true`.
- [ ] `GET /api/health/config` returns expected config flags.

## 3) Enterprise endpoint checks
- [ ] `POST /api/matters` (with SSO headers) creates matter.
- [ ] `POST /api/matters/<id>/approve` enforces role authorization.
- [ ] `POST /api/integrations/esign/request` responds in `real` or `simulation` mode.

## 4) Demo flow checks
- [ ] Analyze contract in UI panel.
- [ ] Save and reload case.
- [ ] Export JSON and PDF from portal.

## 5) Logs and observability
- [ ] `data/audit.jsonl` receives events.
- [ ] `data/metrics.jsonl` receives workflow duration.
- [ ] `data/integrations/*.jsonl` receives integration events.

# Operations and Compliance Guide

## SLA objetivo (fase actual)
- Disponibilidad objetivo: 99.0% mensual
- Tiempo de respuesta objetivo:
  - modo `local`: < 5s para contratos cortos
  - modo `sdk`: < 45s promedio
- Incidentes criticos: respuesta en < 4h habiles

## Observabilidad incluida
- Metrics JSONL: `data/metrics.jsonl`
  - `workflow_duration_ms`
  - tags: `modo`, `cliente_id`, `compare`
- Audit log JSONL: `data/audit.jsonl`
  - eventos: `analysis_completed`, `analysis_error`, `analysis_exception`, `case_saved`
- Run artifacts: `data/runs/<run_id>.json`

## Seguridad y privacidad
- Redaccion basica de datos sensibles al guardar casos:
  - CUIT
  - emails
  - numeros largos
- Funcion usada: `redact_sensitive()` en `observability.py`
- Recomendacion: en produccion, cifrar `data/cases` en reposo y restringir acceso por rol.

## Retencion de datos
- Limpieza automatica de casos: 30 dias (por defecto)
- Funcion usada: `retention_cleanup()` en `observability.py`
- Ajuste sugerido por entorno:
  - SMB: 30 dias
  - Enterprise: 90 dias con aprobacion legal

## Runbook basico de incidentes
1. Confirmar errores recientes en `data/audit.jsonl`.
2. Revisar latencia y picos en `data/metrics.jsonl`.
3. Validar estado de `CURSOR_API_KEY` si falla modo `sdk`.
4. Forzar fallback a `local` para continuidad operativa.
5. Abrir ticket interno con `run_id` de ejemplo y contrato anonimizado.

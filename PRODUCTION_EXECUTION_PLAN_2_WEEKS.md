# PRODUCTION EXECUTION PLAN (2 WEEKS)

Plan táctico de 10 días hábiles para ejecutar la siguiente etapa de escalabilidad sobre el estado actual del proyecto.

## Objetivo de estas 2 semanas

1. Cerrar todos los puntos **P0** del roadmap.
2. Completar al menos **2 puntos P1** con avance tangible.
3. Mantener estabilidad del MVP (smoke tests + demo flow siempre en verde).

---

## Semana 1 (Foco: P0 completo)

### Día 1 - Contrato API y baseline de compatibilidad
- Definir contrato formal para:
  - `/api/analyze-contract`
  - `/api/routing/dispatch`
  - `/api/routing/queue`
- Crear `docs/API_CONTRACT_V1.md` con:
  - request/response,
  - códigos de error,
  - ejemplos JSON.
- Entregable: versión inicial de contrato API revisable.

### Día 2 - Versionado y compatibilidad v1
- Introducir estrategia `/api/v1/*` sin romper endpoints actuales.
- Mantener backward compatibility (legacy routes -> wrappers o alias).
- Entregable: rutas v1 accesibles y smoke tests verdes.

### Día 3 - Hardening de ingesta documental
- Definir límites:
  - tamaño máximo por archivo,
  - MIME permitidos,
  - timeout de parsing.
- Endurecer validaciones en `portal_web.py` para `/api/analyze-contract`.
- Entregable: errores explícitos y consistentes para casos inválidos.

### Día 4 - Estado de negocio e invariantes
- Estandarizar transición de estados de matter.
- Definir invariantes en docs (`docs/STATE_MACHINE.md`).
- Agregar tests de transición inválida/duplicada en `tests/smoke_enterprise.py`.
- Entregable: máquina de estados documentada + cobertura mínima.

### Día 5 - Observabilidad mínima productiva
- Definir SLO inicial:
  - latencia de análisis,
  - tasa de errores,
  - éxito de dispatch,
  - throughput por hora.
- Extender `observability.py` + runbook de operación.
- Entregable: panel mínimo de métricas y guía de incidentes actualizada.

---

## Semana 2 (Foco: P1 priorizado + estabilización)

### Día 6 - Capa de repositorio (desacople de persistencia)
- Introducir abstracción de repositorio para matters/eventos.
- Aislar acceso file-based actual detrás de interfaz.
- Entregable: dominio desacoplado listo para migración futura a Postgres.

### Día 7 - Diseño de esquema SQL y plan de migración
- Definir esquema inicial Postgres:
  - matters, events, approvals, routing, hitl_reviews.
- Crear `docs/DB_SCHEMA_V1.md` y plan de migración desde `data/matters/*.json`.
- Entregable: blueprint de DB + script de migración diseñado (no productivo aún).

### Día 8 - Hardening frontend operativo (dashboard)
- Normalizar manejo de errores y estado de carga en `frontend/src/app/dashboard/page.tsx`.
- Persistir filtros de bandeja (query params o local state robusto).
- Entregable: UX más estable para uso diario (sin cambios de arquitectura).

### Día 9 - Seguridad y identidad (preparación)
- Definir estrategia de auth real (SSO/JWT) y mapping de roles.
- Documentar migración desde headers demo actuales a identidad real.
- Entregable: `docs/AUTHZ_STRATEGY.md` + checklist de implementación.

### Día 10 - Cierre de release y Go/No-Go
- Ejecución final de:
  - `tests/smoke_enterprise.py`
  - `scripts/run_demo_flow.py`
  - build de frontend (`frontend`)
- Validación de criterios de salida del roadmap.
- Entregable: acta de cierre + backlog P2 priorizado.

---

## Prioridades explícitas (P0/P1/P2)

- **P0 (obligatorio en estas 2 semanas):**
  - Contrato API + versionado v1
  - Validaciones de ingesta
  - Invariantes de estado e idempotencia extendida
  - Observabilidad con SLO mínimo

- **P1 (target de avance):**
  - Capa de repositorio desacoplada
  - Esquema DB + plan de migración
  - Hardening frontend operativo
  - Estrategia authz documentada

- **P2 (fuera de sprint, solo diseño):**
  - Ingesta email/webhook productiva
  - Cumplimiento/auditoría avanzada

---

## Definición de terminado (DoD)

Se considera completado este plan cuando:

- [ ] P0 completo.
- [ ] Al menos 2 temas P1 con entregable usable/documentado.
- [ ] `tests/smoke_enterprise.py` en verde al cierre.
- [ ] `scripts/run_demo_flow.py` en verde al cierre.
- [ ] Documentación operativa y técnica actualizada en `docs/`.

---

## Riesgos de ejecución y mitigación

1. **Riesgo:** romper compatibilidad al introducir `/api/v1`.
   - **Mitigación:** mantener endpoints legacy activos con pruebas paralelas.

2. **Riesgo:** aumento de complejidad por refactor prematuro.
   - **Mitigación:** cambios incrementales detrás de interfaces pequeñas.

3. **Riesgo:** degradación UX por hardening rápido.
   - **Mitigación:** validar cada cambio contra el flujo demo actual.


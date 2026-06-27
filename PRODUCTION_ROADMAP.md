# PRODUCTION ROADMAP

Hoja de ruta para escalar el MVP actual de LegalFlow a una etapa productiva sin perder velocidad.

## Contexto base (estado actual)

- Backend principal en `portal_web.py` (Flask) con flujo E2E:
  - `/api/analyze-contract`
  - `/api/routing/dispatch`
  - `/api/routing/queue`
  - matters, approvals, e-sign y timeline.
- Orquestación IA en `agente.py`.
- Persistencia actual file-based en `matters_store.py` y `data/*`.
- Frontend Next.js en `frontend/` con dashboard HITL y bandejas.
- Smoke y demo flow disponibles:
  - `tests/smoke_enterprise.py`
  - `scripts/run_demo_flow.py`

---

## Checklist priorizado (10 puntos)

## P0 (crítico para siguiente etapa)

### 1) Congelar contrato de API y versionado
- [ ] Definir contrato estable para endpoints críticos (`/api/analyze-contract`, `/api/routing/dispatch`, `/api/routing/queue`).
- [ ] Publicar esquema de request/response y catálogo de errores (`code`) por endpoint.
- [ ] Introducir convención de versionado (`/api/v1/...`) para cambios futuros sin ruptura.

**Objetivo:** evitar breaking changes entre frontend `frontend/src/lib/api.ts` y backend `portal_web.py`.

### 2) Validaciones y límites operativos de ingesta documental
- [ ] Definir límites de tamaño de archivo y tipo MIME permitidos (PDF/DOCX) en backend.
- [ ] Agregar controles de seguridad de archivo (nombres, extensión real, contenido vacío, timeouts).
- [ ] Documentar fallback explícito para OCR futuro (hoy no incluido en MVP).

**Objetivo:** endurecer `/api/analyze-contract` para tráfico real y documentos no ideales.

### 3) Idempotencia y consistencia de estado en rutas críticas
- [ ] Extender patrón de idempotencia más allá de webhook e-sign (dispatch y eventos sensibles).
- [ ] Estandarizar transiciones de estado del matter (`pending_review -> dispatched -> signed`, etc.).
- [ ] Definir invariantes de negocio y validarlas en tests de regresión.

**Objetivo:** evitar estados inválidos o duplicados bajo reintentos/concurrencia.

### 4) Observabilidad operativa con SLO mínimo
- [ ] Definir 4-6 métricas SLO (latencia, tasa de error, throughput, éxito de dispatch, éxito de análisis).
- [ ] Crear dashboard operacional y alertas básicas (error rate, latencia p95, caídas).
- [ ] Asegurar trazabilidad por `run_id` y `matter_id` extremo a extremo.

**Objetivo:** pasar de logs útiles a operación monitoreable y accionable.

---

## P1 (importante para escalabilidad)

### 5) Capa de persistencia desacoplada y plan de migración a DB
- [ ] Introducir interfaz de repositorio (abstracción) para no acoplar lógica a JSON files.
- [ ] Diseñar modelo inicial en Postgres (matters, events, approvals, routing, hitl_review).
- [ ] Plan de migración de `data/matters/*.json` a tablas con script reproducible.

**Objetivo:** preparar transición a persistencia transaccional sin reescribir el dominio.

### 6) Modelo de autenticación/autorización para multiusuario real
- [ ] Definir estrategia de identidad (SSO/JWT) y mapping de roles.
- [ ] Homologar contexto de usuario entre frontend y backend (evitar usuarios hardcoded demo).
- [ ] Implementar trazabilidad de actor real en aprobaciones y despacho.

**Objetivo:** pasar de modo demo a control de acceso enterprise.

### 7) Procesamiento asíncrono para análisis y tareas de despacho
- [ ] Separar operaciones largas a cola de trabajos (análisis, ingestas pesadas, integraciones externas).
- [ ] Definir estados de job y polling/websocket para feedback UI.
- [ ] Garantizar retries con backoff y dead-letter para fallos externos.

**Objetivo:** mantener UX fluida con carga real de documentos y concurrencia.

### 8) Hardening frontend para operación diaria
- [ ] Persistir filtros y estado de bandeja en URL/local state robusto.
- [ ] Manejo unificado de errores API y estados de carga (`loading/success/error`) por acción.
- [ ] Validaciones de formulario HITL más estrictas antes de aprobar/dispatch.

**Objetivo:** reducir fricción operativa y errores de uso del abogado en producción.

---

## P2 (mejoras de expansión)

### 9) Ingesta por email/webhook (hoy mockeada)
- [ ] Diseñar endpoint webhook dedicado y contrato de eventos de correo.
- [ ] Resolver deduplicación de adjuntos y correlación con matters.
- [ ] Añadir visibilidad en bandeja de origen de ingreso (web vs email).

**Objetivo:** ampliar canales de captura sin romper el flujo core.

### 10) Roadmap de cumplimiento y auditoría extendida
- [ ] Definir políticas de retención, export y borrado por cliente.
- [ ] Añadir trazabilidad ampliada de cambios en campos HITL (quién cambió qué y cuándo).
- [ ] Preparar paquete de evidencias para auditoría interna/externa.

**Objetivo:** facilitar adopción en cuentas enterprise reguladas.

---

## Criterio de salida para "siguiente etapa de escalabilidad"

Se considera lista la siguiente etapa cuando:

- [ ] Todos los puntos P0 estén cerrados.
- [ ] Al menos 2 de 4 puntos P1 estén implementados.
- [ ] Se mantenga `tests/smoke_enterprise.py` en verde en cada release.
- [ ] Se ejecute `scripts/run_demo_flow.py` como prueba de aceptación comercial-técnica.


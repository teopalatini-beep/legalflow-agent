# Phase 2 - Matter Lifecycle, Approvals, and Document Versioning

Implementacion de Fase 2 orientada a convertir el matter en un expediente operativo con historial.

## Endpoints de lifecycle

- `POST /api/matters`
- `POST /api/matters/<matter_id>/approve`
- `POST /api/matters/<matter_id>/sign`
- `GET /api/matters/<matter_id>/obligations`
- `GET /api/matters/<matter_id>/timeline`

## Endpoints de aprobaciones

- `POST /api/matters/<matter_id>/approvals/request`
  - body:
    - `reviewers`: lista de emails/identificadores
    - `note`: opcional
- `POST /api/matters/<matter_id>/approvals/<approval_id>/decision`
  - body:
    - `decision`: `approved` | `rejected`
    - `note`: opcional

## Endpoints de versionado documental

- `POST /api/matters/<matter_id>/documents/versions`
  - body:
    - `filename`
    - `content` (texto del documento)
    - `source` (opcional)
    - `metadata` (opcional)
- `GET /api/matters/<matter_id>/documents/versions`

## Comportamiento de estados

- `draft` al crear matter
- `pending_approval` al solicitar aprobaciones
- `approved` cuando todas las aprobaciones quedan aprobadas
- `changes_requested` si alguna aprobacion es rechazada
- `signature_pending` al solicitar firma

## Evidencia de trazabilidad

El endpoint `GET /api/matters/<matter_id>/timeline` retorna:
- `events`
- `approvals`
- `document_versions`
- `status` actual

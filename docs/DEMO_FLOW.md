# Demo Flow Guide

## Objetivo
Demostrar en 10-12 minutos que LegalFlow reduce riesgo contractual, acelera decisiones y deja trazabilidad completa sin fricción para el abogado.

## Mensaje ejecutivo (apertura de 30 segundos)
- "Hoy voy a mostrar cómo pasamos de revisión manual a decisión legal asistida en minutos."
- "Cada clic muestra valor visible: riesgo priorizado, recomendación accionable y trazabilidad."
- "Vamos a cerrar con estado firmado y timeline auditable de punta a punta."

## Checklist pre-demo (2 minutos)
- Confirmar servidor activo del portal web.
- Confirmar que `docs/DEMO_FLOW.md` y `data/demo/demo_flow.json` estén disponibles.
- Confirmar credenciales SSO para endpoints protegidos (si aplica en el entorno).
- Definir plan de contingencia:
  - si faltan `LEGALFLOW_ESIGN_ENDPOINT` / `LEGALFLOW_ESIGN_API_KEY`, seguir en modo `simulation`,
  - explicitar que el flujo no se bloquea y mantiene evidencia de valor.
- Abrir el portal con paneles visibles (análisis, riesgos/trazabilidad, redlines/firma).

## Opcion 1: Demo desde UI (recomendada en reunión)
1. Click en `Cargar demo`.
2. Click en `Analizar`.
3. Mostrar profundidad:
   - resumen final,
   - acción recomendada,
   - comparación A/B,
   - riesgos con evidencia y confianza,
   - redlines sugeridos,
   - quality score.
4. Click en `Guardar caso`.
5. Click en `Listar casos` y reabrir el caso guardado.
6. En panel `Firma embebida (demo)`:
   - `Crear matter demo`,
   - `Iniciar firma`,
   - `Abrir firma`,
   - `Simular firmado`,
   - `Refrescar timeline`.
7. Cerrar mostrando badge de estado:
   - `draft -> signature_pending -> signed`.

## Opcion 2: Demo automatizada por script
```bash
python scripts/run_demo_flow.py
```

El script ejecuta:
1. análisis + comparación,
2. guardado de caso,
3. creación de matter,
4. aprobación,
5. create-envelope + recipient-view,
6. webhook de firma simulado y cierre en `signed`.

## Paso -> Evidencia -> Valor (guion didáctico)
- Paso 1 (`Cargar demo`) -> evidencia: formulario completo en 1 click -> valor: arranque rápido sin preparación manual.
- Paso 2 (`Analizar`) -> evidencia: resumen + riesgos + redlines + quality -> valor: decisión legal más rápida y mejor fundamentada.
- Paso 3 (`Comparación A/B`) -> evidencia: delta de riesgos y calidad -> valor: negociación con criterio objetivo.
- Paso 4 (`Guardar/Listar caso`) -> evidencia: persistencia y reapertura -> valor: continuidad de trabajo y reutilización.
- Paso 5 (`Iniciar firma`) -> evidencia: `envelope_id` / `recipient_id` y estado `signature_pending` -> valor: inicio de cierre contractual trazable.
- Paso 6 (`Simular firmado`) -> evidencia: webhook + estado `signed` + timeline -> valor: auditoría completa del ciclo legal.

## Script de cierre comercial (60-90 segundos)
- Control de riesgo: "No solo detecta riesgos, los prioriza y explica con evidencia."
- Velocidad operativa: "El abogado pasa de leer todo manualmente a revisar excepciones críticas."
- Trazabilidad enterprise: "Cada paso queda registrado en timeline y estado legal verificable."

## Dataset de demo
- `data/demo/demo_flow.json`

## Nota sobre keys
- Si no existe `LEGALFLOW_ESIGN_ENDPOINT`/`LEGALFLOW_ESIGN_API_KEY`, la demo sigue en modo simulación sin bloquear el flujo.

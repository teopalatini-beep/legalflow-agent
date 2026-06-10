# Demo Flow Guide

## Objetivo
Demostrar LegalFlow en reuniones comerciales sin depender de configuraciones manuales complejas.

## Opcion 1: Demo desde UI
1. Abrir el portal.
2. Click en `Cargar demo`.
3. Click en `Analizar`.
4. Mostrar:
   - comparacion A/B,
   - riesgos y decisiones,
   - redlines sugeridos.
5. Click en `Guardar caso`.
6. Click en `Listar casos` para reabrir el caso.

## Opcion 2: Demo automatizada por script

```bash
python scripts/run_demo_flow.py
```

El script ejecuta:
1. Analisis + comparacion
2. Guardado de caso
3. Creacion de matter
4. Aprobacion de matter
5. Solicitud de e-signature (modo real o simulacion)

## Dataset de demo
- `data/demo/demo_flow.json`

## Nota sobre keys
- Si no existe `LEGALFLOW_ESIGN_ENDPOINT`/`LEGALFLOW_ESIGN_API_KEY`, la demo sigue en modo simulacion.

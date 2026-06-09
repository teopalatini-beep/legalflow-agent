# Playbook and Memory Model

## Goal
Personalizar el analisis legal por cliente, manteniendo historial para aprendizaje operativo.

## Playbook format
- Path: `data/playbooks/<cliente_id>.json`
- Campos sugeridos:
  - `clausulas_preferidas`
  - `red_flags_criticos`
  - `jurisdicciones_permitidas`
  - `tono_negociacion`

## Decision memory
- Path: `data/memory/<cliente_id>_decisions.jsonl`
- Se registra por run:
  - `run_id`
  - `modo_analisis`
  - `clausulas_detectadas`
  - `riesgos_detectados`
  - `accion_recomendada`

## Analysis modes
- `general`: equilibrio entre deteccion y cobertura.
- `strict_playbook`: prioriza cumplimiento estricto de reglas del cliente.
- `counterparty_negotiation`: enfatiza lenguaje y estrategia de negociacion.

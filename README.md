# LegalFlow Agent

Plataforma de **legal ops con IA** que convierte la revisión de contratos en un flujo trazable: intake → riesgos → redlines → matter (aprobaciones, e-sign, timeline). Pensada para abogados in-house o estudios que necesitan decidir más rápido, con evidencia, no solo un resumen suelto.

---

## Qué estoy haciendo

Estoy construyendo un **Legal OS** multi-agente:

1. **Ingiere** un contrato (demo local o vía API/portal)
2. **Extrae** cláusulas y señales de riesgo
3. **Puntúa** riesgos con evidencia y sugiere redlines
4. **Orquesta** especialistas (contratos, sociedades, causas, riesgos, soporte) bajo un Head of Legal
5. **Persiste** el caso/matter con historial y routing humano (HITL)
6. **Muestra** todo en portal Flask + dashboard Next.js

No reemplaza al abogado: acelera el primer pase y deja un rastro auditable para que el humano decida.

---

## Por qué lo estoy haciendo

La revisión manual de contratos es lenta, inconsistente y difícil de auditar. Cada persona mira distinto; el “por qué se aprobó esto” se pierde en el mail.

Quería un sistema que:

- aplique **playbooks** configurables (no magia opaca)
- priorice **riesgos con evidencia**
- proponga **redlines** accionables
- guarde el **matter** de punta a punta
- permita **humano en el loop** antes de firmar o escalar

---

## Beneficios

| Beneficio | En la práctica |
|---|---|
| **Más rápido el primer pase** | Pipeline automático en minutos, no horas |
| **Riesgos priorizados** | Ranking + evidencia, no un muro de texto |
| **Redlines sugeridos** | Punto de partida para negociar |
| **Trazabilidad** | Historial del matter / decisiones |
| **HITL** | Colas de revisión humana cuando hace falta |
| **Demo local** | Modo `local` sin depender de API keys |

---

## Qué hace (y qué no)

**Sí hace**
- Analizar contratos por pipeline o API
- Orquestar agentes especializados (MALS)
- Persistir cases/matters
- Servir portal + API de salud
- Simular integraciones enterprise si no hay credenciales

**No hace**
- Sustituir consejo legal profesional
- Firmar o enviar a e-sign sin configuración / revisión
- Garantizar cobertura de todos los derechos/jurisdicciones

---

## Cómo funciona

```
Contrato
  → ingesta / extracción
  → riesgos + compliance
  → redline + resumen + verifier
  → matter store (historial)
  → portal / API / frontend HITL
```

| Pieza | Rol |
|---|---|
| `agente.py` | Pipeline secuencial (`local` o `sdk` con Claude) |
| `mals/` | Orquestador jerárquico de especialistas |
| `portal_web.py` | Flask API + portal (puerto 8000) |
| `frontend/` | Dashboard Next.js |
| `docs/` | Arquitectura, runbook, demo |

---

## Setup rápido

```bash
git clone https://github.com/teopalatini-beep/legalflow-agent.git
cd legalflow-agent
pip install -r requirements.txt
cp .env.example .env
python scripts/check_runtime_config.py
python portal_web.py
# → http://localhost:8000  |  GET /api/health
```

Pipeline demo (sin LLM):

```bash
python agente.py --modo local --demo
```

Frontend:

```bash
cd frontend && npm install && npm run dev
```

Los `.env` **nunca** se suben a git.

---

## Docs

- [`docs/LEGAL_OS_ARCHITECTURE.md`](docs/LEGAL_OS_ARCHITECTURE.md) — arquitectura
- [`docs/OPERATIONS_RUNBOOK.md`](docs/OPERATIONS_RUNBOOK.md) — operaciones y health
- [`docs/DEMO_FLOW.md`](docs/DEMO_FLOW.md) — recorrido de producto
- [`PRODUCTION_ROADMAP.md`](PRODUCTION_ROADMAP.md) — roadmap

---

## Estado del proyecto

MVP en evolución: pipeline + portal + orquestación MALS. Enfocado en demos y pilotos; playbooks e integraciones enterprise siguen expandiéndose.

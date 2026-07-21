# LegalFlow Agent

> Sistema multi-agente de IA para análisis de contratos y gestión de expedientes legales — desde la ingesta de un contrato hasta la detección de riesgos, redlines sugeridos y seguimiento post-firma.

## El problema que resuelve

Revisar contratos manualmente es lento y depende de la disponibilidad de un abogado para cada paso: leer, extraer cláusulas y obligaciones, detectar riesgos, proponer redlines, y luego seguir el cumplimiento post-firma. LegalFlow automatiza ese pipeline con un equipo de agentes especializados, cada uno responsable de una etapa del análisis, coordinados sobre un modelo de "expediente vivo" (matter) con trazabilidad completa de decisiones.

## Funcionalidades clave

- **Pipeline multi-agente**: extracción de cláusulas y evidencias, scoring de riesgo contextualizado, generación de propuestas de redline, y verificación/QA legal antes de entregar el resultado.
- **Capa de abstracción de LLM** (`llm_provider.py`): desacopla la lógica de negocio del proveedor de modelo, permitiendo cambiar entre proveedores sin reescribir los agentes.
- **Middleware de SSO** (`sso_auth.py`) para integraciones enterprise.
- **Gestión de expedientes** (`matters_store.py`): estados, aprobaciones y deadlines de cada caso.
- **Integraciones enterprise** (`enterprise_integrations.py`) y observabilidad (`observability.py`) para trazar el comportamiento del sistema en producción.
- **API-first**: endpoints públicos (`/api/analizar`, `/api/casos`) consumidos por un frontend en Next.js.
- **Datos de demo incluidos** (`data/demo/`) con flujos completos ejecutables sin depender de datos reales.

## Arquitectura

Backend en Python (Flask, vía `api/index.py`) con un conjunto de agentes bajo `mals/agents/` orquestados según el flujo documentado en `docs/LEGAL_OS_ARCHITECTURE.md`:

```
IntakeAgent → ExtractorAgent → RiskAgent → RedlineAgent → VerifierAgent → MatterAgent → ObligationMonitorAgent
```

El frontend (`frontend/`, Next.js + TypeScript) consume la API y ofrece el panel de gestión de expedientes. Todo el proyecto se despliega en Vercel (backend serverless + frontend).

## Stack técnico

- **Backend**: Python, Flask (API serverless en Vercel)
- **Frontend**: Next.js, TypeScript, Tailwind CSS
- **IA**: capa de abstracción propia sobre proveedor de LLM, con prompts versionados (`prompts/`)
- **Auth**: middleware de SSO propio
- **Deploy**: Vercel (`vercel.json`, `api/index.py` como entrypoint serverless)

## Estructura del proyecto

```
├── mals/
│   ├── agents/              # head_of_legal, senior_a, senior_b — agentes especializados
│   └── state.py             # estado compartido del pipeline
├── api/index.py             # entrypoint serverless (Flask)
├── frontend/                 # Next.js + TypeScript
├── data/
│   ├── demo/                 # datos de ejemplo para correr el flujo completo
│   └── playbooks/
├── docs/                      # arquitectura, roadmap, runbooks de operación
├── scripts/                   # scripts de prueba y verificación del pipeline
├── llm_provider.py            # abstracción sobre el proveedor de LLM
├── sso_auth.py                 # middleware de autenticación SSO
├── matters_store.py            # persistencia de expedientes
└── enterprise_integrations.py  # integraciones con sistemas externos
```

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .env.example .env   # completar variables de entorno

cd frontend
npm install
```

Ver `docs/DEMO_FLOW.md` y `scripts/run_demo_flow.py` para correr un caso de demo de punta a punta sin necesidad de datos reales.

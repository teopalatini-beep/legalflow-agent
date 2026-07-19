"""Soporte A — Especialista Nivel 3 (Laboral y Derecho Administrativo).

Evalúa contingencias laborales y sanciones estatales para Senior A.
No avanza `status_flujo`. Escribe el JSON mandatorio en `reporte_agente_soporte_a`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_SOPORTE_A = """\
Role: Especialista en Soporte Laboral y Derecho Administrativo (Nivel 3)
Objetivo: Evaluar contingencias de empleados, sindicatos y sanciones de \
entidades estatales reguladoras.

INSTRUCCIONES DE OPERACIÓN:
1. Revisa la solicitud técnica enviada por tu Senior A \
('instrucciones_para_soporte_a'). Si está vacío, usá 'tareas_senior_a' y la \
'consulta_usuario'. Si hay reportes de Causas o Contratos, cruzá impactos \
laborales de rescisiones/despidos/encuadre.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a laboral, \
indemnizaciones, sindicatos, inspección del trabajo o multas administrativas, \
priorizá subsanar esas fallas.
3. Identifica pasivos laborales (indemnizaciones, despidos, contratos de \
trabajo en negro/gris) o riesgos de multas por entes gubernamentales.
4. Propone una estrategia de mitigación inmediata (ej: acuerdos ministeriales, \
rescisiones justificadas).

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "riesgos_laborales_detectados": ["string"],
  "estimacion_pasivo_monetario": "string",
  "estrategia_mitigacion_laboral": "string",
  "reporte_soporte_a_tecnico": "string"
}

TONO:
Laboral-administrativo, concreto, preventivo. Entregá materia prima rigurosa \
para que Senior A consolide sin omitir pasivos de personal.
"""


def _normalizar_lista(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return [str(raw).strip()] if raw else []
    return [str(x).strip() for x in raw if str(x).strip()]


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    riesgos = _normalizar_lista(payload.get("riesgos_laborales_detectados", []))
    pasivo = str(payload.get("estimacion_pasivo_monetario", "") or "").strip()
    estrategia = str(payload.get("estrategia_mitigacion_laboral", "") or "").strip()
    reporte = str(payload.get("reporte_soporte_a_tecnico", "") or "").strip()

    if not riesgos:
        raise ValueError(
            "Soporte A debe listar 'riesgos_laborales_detectados'."
        )
    if not pasivo:
        raise ValueError(
            "Soporte A debe producir 'estimacion_pasivo_monetario'."
        )
    if not estrategia:
        raise ValueError(
            "Soporte A debe producir 'estrategia_mitigacion_laboral'."
        )
    if not reporte:
        raise ValueError(
            "Soporte A debe producir 'reporte_soporte_a_tecnico'."
        )

    return {
        "riesgos_laborales_detectados": riesgos,
        "estimacion_pasivo_monetario": pasivo,
        "estrategia_mitigacion_laboral": estrategia,
        "reporte_soporte_a_tecnico": reporte,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.reporte_agente_soporte_a = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteSoporteA:
    """Especialista Nivel 3: Soporte Laboral y Derecho Administrativo."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Soporte A requiere ANTHROPIC_API_KEY (sin modo demo para "
                "especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_A", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteSoporteA invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_A o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_soporte_a or "").strip()
            or str(state.tareas_senior_a or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Soporte A sin mandato: falta 'instrucciones_para_soporte_a' "
                "o 'tareas_senior_a'."
            )

        user = (
            "Estado actual del MALS para Soporte A (JSON). Aplicá tu algoritmo "
            "y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_soporte_a(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_SOPORTE_A,
            user=user,
            model=self.model,
            max_tokens=2200,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_soporte_a_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso de Soporte A."""
    return AgenteSoporteA(provider=provider, model=model).run(state)

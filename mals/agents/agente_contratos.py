"""Agente de Contratos — Especialista Nivel 3 (Derecho Contractual Comercial).

Audita cláusulas y propone redacciones alternativas para Senior A.
No avanza `status_flujo`. Escribe el JSON mandatorio en `reporte_agente_contratos`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_CONTRATOS = """\
Role: Especialista en Derecho Contractual Comercial (Nivel 3)
Objetivo: Auditar, desglosar y enmendar contratos comerciales para eliminar \
pasivos y riesgos ocultos.

INSTRUCCIONES DE OPERACIÓN:
1. Revisa el contrato o la situación contractual asignada por tu Senior \
('instrucciones_para_contratos'). Si está vacío, usá 'tareas_senior_a' y la \
'consulta_usuario' como mandato. Si existe 'reporte_agente_causas', cruzá \
hallazgos para evitar contradicciones con la estrategia litigiosa.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a cláusulas, \
multas, rescisión, responsabilidad o IP, priorizá subsanar esas fallas.
3. Analiza obligatoriamente los siguientes nodos críticos:
   - Cláusulas penales o multas por incumplimiento.
   - Mecanismos y costos de rescisión anticipada.
   - Limitación de responsabilidad económica de nuestra empresa.
   - Cláusulas de propiedad intelectual y confidencialidad.
4. Genera un texto alternativo o enmienda (adenda) redactado en lenguaje legal \
formal para solucionar cada riesgo encontrado.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "clausulas_riesgo_detectadas": [
    {"clausula": "string", "riesgo": "string"}
  ],
  "propuesta_redaccion_alternativa": "string",
  "analisis_contractual_tecnico": "string"
}

TONO:
Técnico, contractual, preventivo. Entregá materia prima rigurosa para que \
Senior A consolide sin pasivos ocultos.
"""


def _normalizar_clausulas(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    limpios: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        clausula = str(item.get("clausula", "") or "").strip()
        riesgo = str(item.get("riesgo", "") or "").strip()
        if clausula or riesgo:
            limpios.append({"clausula": clausula, "riesgo": riesgo})
    return limpios


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    clausulas = _normalizar_clausulas(payload.get("clausulas_riesgo_detectadas", []))
    propuesta = str(payload.get("propuesta_redaccion_alternativa", "") or "").strip()
    analisis = str(payload.get("analisis_contractual_tecnico", "") or "").strip()

    if not analisis:
        raise ValueError(
            "Agente Contratos debe producir 'analisis_contractual_tecnico'."
        )
    if not propuesta:
        raise ValueError(
            "Agente Contratos debe producir 'propuesta_redaccion_alternativa'."
        )
    if not clausulas:
        raise ValueError(
            "Agente Contratos debe listar al menos una cláusula de riesgo "
            "en 'clausulas_riesgo_detectadas'."
        )

    return {
        "clausulas_riesgo_detectadas": clausulas,
        "propuesta_redaccion_alternativa": propuesta,
        "analisis_contractual_tecnico": analisis,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.reporte_agente_contratos = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteContratos:
    """Especialista Nivel 3: Derecho Contractual Comercial."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Agente Contratos requiere ANTHROPIC_API_KEY (sin modo demo "
                "para especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_A", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteContratos invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_A o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_contratos or "").strip()
            or str(state.tareas_senior_a or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Agente Contratos sin mandato: falta 'instrucciones_para_contratos' "
                "o 'tareas_senior_a'."
            )

        user = (
            "Estado actual del MALS para Agente de Contratos (JSON). Aplicá tu "
            "algoritmo y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_contratos(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_CONTRATOS,
            user=user,
            model=self.model,
            max_tokens=2600,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_contratos_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso del especialista de Contratos."""
    return AgenteContratos(provider=provider, model=model).run(state)

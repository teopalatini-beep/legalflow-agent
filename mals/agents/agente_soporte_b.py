"""Soporte B — Especialista Nivel 3 (Tributario y Propiedad Intelectual).

Optimiza carga fiscal y blinda intangibles para Senior B.
No avanza `status_flujo`. Escribe el JSON mandatorio en `reporte_agente_soporte_b`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_SOPORTE_B = """\
Role: Especialista en Derecho Tributario y Propiedad Intelectual (Nivel 3)
Objetivo: Optimizar la carga impositiva de las estructuras corporativas y \
blindar los activos intangibles (marcas/patentes).

INSTRUCCIONES DE OPERACIÓN:
1. Analiza el caso societario o de negocio enviado por tu Senior B \
('instrucciones_para_soporte_b'). Si está vacío, usá 'tareas_senior_b' y la \
'consulta_usuario'. Si hay reportes de Sociedades o Riesgos, cruzá impacto \
fiscal y de PI con la estructura y el compliance propuesto.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a impuestos, \
retenciones, transfer pricing, marcas, patentes o secretos comerciales, \
priorizá subsanar esas fallas.
3. Evalúa: 1) El impacto fiscal e impositivo local e internacional de la \
operación. 2) La disponibilidad y protección de marcas, patentes o secretos \
comerciales asociados.
4. Propone estructuras de eficiencia fiscal (tax planning) legítimas y \
procesos de registro de PI. No recomiendes evasión ni esquemas abusivos.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "impacto_tributario_estimado": "string",
  "estatus_propiedad_intelectual": "string",
  "estrategia_optimizacion_fiscal_pi": "string",
  "reporte_soporte_b_tecnico": "string"
}

TONO:
Fiscal-técnico, preventivo, concreto. Entregá materia prima rigurosa para que \
Senior B consolide sin omitir carga tributaria ni riesgos de PI.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    impacto = str(payload.get("impacto_tributario_estimado", "") or "").strip()
    pi = str(payload.get("estatus_propiedad_intelectual", "") or "").strip()
    estrategia = str(
        payload.get("estrategia_optimizacion_fiscal_pi", "") or ""
    ).strip()
    reporte = str(payload.get("reporte_soporte_b_tecnico", "") or "").strip()

    if not impacto:
        raise ValueError(
            "Soporte B debe producir 'impacto_tributario_estimado'."
        )
    if not pi:
        raise ValueError(
            "Soporte B debe producir 'estatus_propiedad_intelectual'."
        )
    if not estrategia:
        raise ValueError(
            "Soporte B debe producir 'estrategia_optimizacion_fiscal_pi'."
        )
    if not reporte:
        raise ValueError(
            "Soporte B debe producir 'reporte_soporte_b_tecnico'."
        )

    return {
        "impacto_tributario_estimado": impacto,
        "estatus_propiedad_intelectual": pi,
        "estrategia_optimizacion_fiscal_pi": estrategia,
        "reporte_soporte_b_tecnico": reporte,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.reporte_agente_soporte_b = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteSoporteB:
    """Especialista Nivel 3: Tributario y Propiedad Intelectual."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Soporte B requiere ANTHROPIC_API_KEY (sin modo demo para "
                "especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_B", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteSoporteB invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_B o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_soporte_b or "").strip()
            or str(state.tareas_senior_b or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Soporte B sin mandato: falta 'instrucciones_para_soporte_b' "
                "o 'tareas_senior_b'."
            )

        user = (
            "Estado actual del MALS para Soporte B (JSON). Aplicá tu algoritmo "
            "y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_soporte_b(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_SOPORTE_B,
            user=user,
            model=self.model,
            max_tokens=2400,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_soporte_b_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso de Soporte B."""
    return AgenteSoporteB(provider=provider, model=model).run(state)

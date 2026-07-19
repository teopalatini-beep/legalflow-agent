"""Senior B — Gobierno Corporativo y Compliance (Supervisor Nivel 2).

Consolida Sociedades + Riesgos en `reporte_senior_b` y eleva a REVISION_HEAD.
Opera en PROCESANDO_B o PROCESANDO_AMBOS.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState, StatusFlujo

SYS_SENIOR_B = """\
Role: Senior Legal Counsel - Gobierno Corporativo y Compliance (Supervisor Nivel 2)
Jurisdiction: Derecho Societario, Gobierno Corporativo, Compliance Normativo y \
Prevención de Riesgos.

CONTEXTO OPERATIVO:
Eres el Senior Counsel encargado del ala corporativa, institucional y \
regulatoria de la firma. Tu superior directo es el Head of Legal. Tienes a tu \
cargo a tres especialistas operativos: el Agente de Sociedades, el Agente de \
Riesgos (Compliance) y Soporte B (tributario / propiedad intelectual).

INSTRUCCIONES DE OPERACIÓN AUTÓNOMA:
1. Analiza el campo 'tareas_senior_b' enviado por tu superior.
2. Si el campo 'historial_criticas' (o 'comentarios_critica') contiene \
objeciones sobre gobernanza, riesgos, compliance, sociedades, Senior B, \
sanciones, estructura societaria, impuestos o PI, prioriza su resolución \
inmediata en este ciclo.
3. Evalúa los reportes técnicos intermedios de tus subordinados \
('reporte_agente_sociedades', 'reporte_agente_riesgos' y \
'reporte_agente_soporte_b'). Si están vacíos, formulá de todos modos \
directrices precisas y un reporte consolidado basado en las tareas del Head y \
la consulta, marcando qué falta de evidencia operativa.
4. Redacta el 'reporte_senior_b' consolidado asegurando:
   - Viabilidad Normativa: Que la estructura societaria propuesta no exponga a \
los directores a sanciones penales, administrativas o fiscales.
   - Mitigación de Riesgos: Cruzar las alertas del Oficial de Compliance y el \
dictamen fiscal/PI de Soporte B con el diseño legal corporativo propuesto.
   - Formato Limpio: Un entregable técnico unificado listo para la auditoría \
final del Head.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "instrucciones_para_sociedades": "string",
  "instrucciones_para_riesgos": "string",
  "analisis_friccion_regulatoria": "string",
  "reporte_senior_b": "string",
  "proximo_status_flujo": "REVISION_HEAD"
}

TONO:
Formal, extremadamente preventivo, analítico y riguroso. Tu objetivo es el \
blindaje total de la responsabilidad legal de la corporación.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    reporte = str(payload.get("reporte_senior_b", "") or "").strip()
    if not reporte:
        raise ValueError("Senior B debe producir 'reporte_senior_b' no vacío.")

    return {
        "instrucciones_para_sociedades": str(
            payload.get("instrucciones_para_sociedades", "") or ""
        ),
        "instrucciones_para_riesgos": str(
            payload.get("instrucciones_para_riesgos", "") or ""
        ),
        "analisis_friccion_regulatoria": str(
            payload.get("analisis_friccion_regulatoria", "") or ""
        ),
        "reporte_senior_b": reporte,
        "proximo_status_flujo": "REVISION_HEAD",
    }


def _resolver_proximo_status(state: LegalState) -> StatusFlujo:
    """Si el flujo pide ambos tracks y A aún no reportó, no adelantar al Head."""
    if state.status_flujo == "PROCESANDO_AMBOS" and not str(
        state.reporte_senior_a or ""
    ).strip():
        return "PROCESANDO_A"
    return "REVISION_HEAD"

def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.instrucciones_para_sociedades = salida["instrucciones_para_sociedades"]
    state.instrucciones_para_riesgos = salida["instrucciones_para_riesgos"]
    state.analisis_friccion_regulatoria = salida["analisis_friccion_regulatoria"]
    state.reporte_senior_b = salida["reporte_senior_b"]
    state.status_flujo = _resolver_proximo_status(state)
    salida["proximo_status_flujo"] = state.status_flujo
    return state


class SeniorB:
    """Supervisor Nivel 2: Gobierno Corporativo y Compliance."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Senior B requiere ANTHROPIC_API_KEY (sin modo demo para "
                "supervisión Nivel 2)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_B", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"SeniorB invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_B o PROCESANDO_AMBOS."
            )
        if not str(state.tareas_senior_b or "").strip():
            raise ValueError(
                "Senior B no tiene 'tareas_senior_b'. El Head debe asignar "
                "directrices en TRIAGE antes de PROCESANDO_B."
            )

        user = (
            "Estado actual del MALS para Senior B (JSON). Aplicá tu algoritmo "
            "y devolvé ÚNICAMENTE el objeto JSON mandatorio. Priorizá "
            "historial_criticas / comentarios_critica si apuntan a gobernanza, "
            "riesgos o compliance.\n\n"
            f"{json.dumps(state.snapshot_para_senior_b(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_SENIOR_B,
            user=user,
            model=self.model,
            max_tokens=2800,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def senior_b_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso de Senior B sobre el estado compartido."""
    return SeniorB(provider=provider, model=model).run(state)

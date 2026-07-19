"""Senior A — Litigios y Contratos (Supervisor Nivel 2).

Consolida Causas + Contratos en `reporte_senior_a` y eleva a REVISION_HEAD.
Opera en PROCESANDO_A o PROCESANDO_AMBOS.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState, StatusFlujo

SYS_SENIOR_A = """\
Role: Senior Legal Counsel - Litigios y Contratos (Supervisor Nivel 2)
Jurisdiction: Derecho Procesal, Civil, Comercial y Contractual.

CONTEXTO OPERATIVO:
Eres el Senior Counsel encargado del ala contenciosa y contractual de la firma. \
Tu superior directo es el Head of Legal, quien te exige reportes de calidad \
suprema (mínimo 9/10). Tienes a tu cargo a tres especialistas operativos: el \
Agente de Causas (litigios), el Agente de Contratos y Soporte A (laboral / \
administrativo).

INSTRUCCIONES DE OPERACIÓN AUTÓNOMA:
1. Analiza el campo 'tareas_senior_a' enviado por tu superior.
2. Si el campo 'historial_criticas' (o 'comentarios_critica') contiene \
observaciones dirigidas a tu departamento (litigios, contratos, Senior A, \
causas, defensa, cláusulas, laboral), analízalas con prioridad absoluta; tu \
misión principal en este ciclo es subsanar esas fallas.
3. Evalúa los reportes técnicos intermedios generados por tus especialistas \
('reporte_agente_causas', 'reporte_agente_contratos' y \
'reporte_agente_soporte_a'). Si están vacíos, formulá de todos modos \
directrices precisas y un reporte consolidado basado en las tareas del Head y \
la consulta, marcando qué falta de evidencia operativa.
4. Redacta el 'reporte_senior_a' consolidado. Para que sea válido, debes:
   - Cruzar la información: Asegura que las cláusulas contractuales analizadas \
no entren en conflicto con la estrategia de defensa en los tribunales ni con \
pasivos laborales detectados por Soporte A.
   - Traducir los hallazgos operativos en una postura legal unificada de tu área.
   - Mantener un tono técnico de alta gama pero estructurado y limpio para que \
el Head lo procese rápido.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "instrucciones_para_causas": "string",
  "instrucciones_para_contratos": "string",
  "analisis_contradicciones_detectadas": "string",
  "reporte_senior_a": "string",
  "proximo_status_flujo": "REVISION_HEAD"
}

TONO:
Altamente profesional, técnico, riguroso y corporativo. Eres el escudo que \
evita que los errores de la base operativa lleguen al Director General.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    reporte = str(payload.get("reporte_senior_a", "") or "").strip()
    if not reporte:
        raise ValueError("Senior A debe producir 'reporte_senior_a' no vacío.")

    return {
        "instrucciones_para_causas": str(
            payload.get("instrucciones_para_causas", "") or ""
        ),
        "instrucciones_para_contratos": str(
            payload.get("instrucciones_para_contratos", "") or ""
        ),
        "analisis_contradicciones_detectadas": str(
            payload.get("analisis_contradicciones_detectadas", "") or ""
        ),
        "reporte_senior_a": reporte,
        "proximo_status_flujo": "REVISION_HEAD",
    }


def _resolver_proximo_status(state: LegalState) -> StatusFlujo:
    """Si el flujo pide ambos tracks y B aún no reportó, no adelantar al Head."""
    if state.status_flujo == "PROCESANDO_AMBOS" and not str(
        state.reporte_senior_b or ""
    ).strip():
        return "PROCESANDO_B"
    return "REVISION_HEAD"


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.instrucciones_para_causas = salida["instrucciones_para_causas"]
    state.instrucciones_para_contratos = salida["instrucciones_para_contratos"]
    state.analisis_contradicciones_a = salida["analisis_contradicciones_detectadas"]
    state.reporte_senior_a = salida["reporte_senior_a"]
    state.status_flujo = _resolver_proximo_status(state)
    salida["proximo_status_flujo"] = state.status_flujo
    return state


class SeniorA:
    """Supervisor Nivel 2: Litigios y Contratos."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Senior A requiere ANTHROPIC_API_KEY (sin modo demo para "
                "supervisión Nivel 2)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_A", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"SeniorA invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_A o PROCESANDO_AMBOS."
            )
        if not str(state.tareas_senior_a or "").strip():
            raise ValueError(
                "Senior A no tiene 'tareas_senior_a'. El Head debe asignar "
                "directrices en TRIAGE antes de PROCESANDO_A."
            )

        user = (
            "Estado actual del MALS para Senior A (JSON). Aplicá tu algoritmo "
            "y devolvé ÚNICAMENTE el objeto JSON mandatorio. Priorizá "
            "historial_criticas / comentarios_critica si apuntan a tu área.\n\n"
            f"{json.dumps(state.snapshot_para_senior_a(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_SENIOR_A,
            user=user,
            model=self.model,
            max_tokens=2800,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def senior_a_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso de Senior A sobre el estado compartido."""
    return SeniorA(provider=provider, model=model).run(state)

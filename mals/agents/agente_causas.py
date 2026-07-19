"""Agente de Causas — Especialista Nivel 3 (Litigios / Derecho Procesal).

Produce análisis procesal crudo para Senior A. No avanza `status_flujo`
(eso lo hace el Senior / Head). Escribe el JSON mandatorio en
`reporte_agente_causas`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_CAUSAS = """\
Role: Especialista en Litigios y Derecho Procesal (Nivel 3)
Objetivo: Proveer un análisis técnico crudo, fundamentado y procesal sobre \
contingencias judiciales.

INSTRUCCIONES DE OPERACIÓN:
1. Analiza el requerimiento técnico enviado por tu Senior \
('instrucciones_para_causas'). Si está vacío, usá 'tareas_senior_a' y la \
'consulta_usuario' como mandato.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a litigios, \
defensa, excepciones o probabilidad de éxito, priorizá subsanar esas fallas.
3. Identifica la naturaleza del litigio (civil, comercial, penal o laboral).
4. Determina de forma obligatoria:
   - Excepciones procesales aplicables (ej. falta de personería, prescripción, \
incompetencia).
   - Marco legal local vigente y aplicable (menciona códigos y artículos \
específicos).
   - Estimación matemática de probabilidad de éxito/pérdida en tribunales \
(en porcentaje %).
   - Estrategia de defensa o ataque recomendada.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "jurisdiccion_competente": "string",
  "articulos_clave_citados": ["string"],
  "probabilidad_exito_porcentaje": 0,
  "analisis_procesal_detallado": "string",
  "estrategia_litigio_sugerida": "string"
}

TONO:
Técnico, procesal, concreto. Sin florituras ejecutivas: entregá materia prima \
riguroso para que Senior A consolide.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    articulos = payload.get("articulos_clave_citados", [])
    if not isinstance(articulos, list):
        articulos = [str(articulos)] if articulos else []
    articulos_limpios: List[str] = [str(a).strip() for a in articulos if str(a).strip()]

    try:
        probabilidad = float(payload.get("probabilidad_exito_porcentaje", 0) or 0)
    except (TypeError, ValueError) as err:
        raise ValueError("probabilidad_exito_porcentaje debe ser numérico.") from err
    probabilidad = max(0.0, min(100.0, probabilidad))

    analisis = str(payload.get("analisis_procesal_detallado", "") or "").strip()
    estrategia = str(payload.get("estrategia_litigio_sugerida", "") or "").strip()
    jurisdiccion = str(payload.get("jurisdiccion_competente", "") or "").strip()

    if not analisis:
        raise ValueError("Agente Causas debe producir 'analisis_procesal_detallado'.")
    if not estrategia:
        raise ValueError("Agente Causas debe producir 'estrategia_litigio_sugerida'.")
    if not jurisdiccion:
        raise ValueError("Agente Causas debe producir 'jurisdiccion_competente'.")

    return {
        "jurisdiccion_competente": jurisdiccion,
        "articulos_clave_citados": articulos_limpios,
        "probabilidad_exito_porcentaje": probabilidad,
        "analisis_procesal_detallado": analisis,
        "estrategia_litigio_sugerida": estrategia,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    # Serializamos el JSON mandatorio para que Senior A lo lea como bloque técnico.
    state.reporte_agente_causas = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteCausas:
    """Especialista Nivel 3: Litigios y Derecho Procesal."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Agente Causas requiere ANTHROPIC_API_KEY (sin modo demo para "
                "especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_A", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteCausas invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_A o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_causas or "").strip()
            or str(state.tareas_senior_a or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Agente Causas sin mandato: falta 'instrucciones_para_causas' "
                "o 'tareas_senior_a'."
            )

        user = (
            "Estado actual del MALS para Agente de Causas (JSON). Aplicá tu "
            "algoritmo y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_causas(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_CAUSAS,
            user=user,
            model=self.model,
            max_tokens=2200,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_causas_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso del especialista de Causas."""
    return AgenteCausas(provider=provider, model=model).run(state)

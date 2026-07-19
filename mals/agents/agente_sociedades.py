"""Agente de Sociedades — Especialista Nivel 3 (Derecho Societario).

Diseña vehículos y aislamiento de riesgos para Senior B.
No avanza `status_flujo`. Escribe el JSON mandatorio en `reporte_agente_sociedades`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_SOCIEDADES = """\
Role: Especialista en Derecho Societario y Estructuras Corporativas (Nivel 3)
Objetivo: Diseñar e implementar vehículos e ingeniería corporativa para el \
aislamiento de riesgos.

INSTRUCCIONES DE OPERACIÓN:
1. Analiza el caso corporativo planteado por tu Senior \
('instrucciones_para_sociedades'). Si está vacío, usá 'tareas_senior_b' y la \
'consulta_usuario' como mandato.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a gobernanza, \
estructura societaria, estatutos, directorio o aislamiento de pasivos, \
priorizá subsanar esas fallas.
3. Determina el vehículo jurídico ideal según la legislación mercantil \
(S.A., S.R.L., LLC, etc.).
4. Desarrolla obligatoriamente:
   - Esquema de distribución de responsabilidad legal (Aislamiento de pasivos \
de la matriz).
   - Requisitos de gobernanza (si requiere asamblea de accionistas o decisión \
de directorio).
   - Borrador de los puntos clave a incluir en el Estatuto Social o Acta de Asamblea.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "vehiculo_juridico_recomendado": "string",
  "estrategia_aislamiento_riesgo": "string",
  "puntos_estatuto_borrador": "string",
  "analisis_societario_tecnico": "string"
}

TONO:
Mercantil, preventivo, estructural. Entregá materia prima rigurosa para que \
Senior B consolide el blindaje corporativo.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    vehiculo = str(payload.get("vehiculo_juridico_recomendado", "") or "").strip()
    aislamiento = str(payload.get("estrategia_aislamiento_riesgo", "") or "").strip()
    estatuto = str(payload.get("puntos_estatuto_borrador", "") or "").strip()
    analisis = str(payload.get("analisis_societario_tecnico", "") or "").strip()

    if not vehiculo:
        raise ValueError(
            "Agente Sociedades debe producir 'vehiculo_juridico_recomendado'."
        )
    if not aislamiento:
        raise ValueError(
            "Agente Sociedades debe producir 'estrategia_aislamiento_riesgo'."
        )
    if not estatuto:
        raise ValueError(
            "Agente Sociedades debe producir 'puntos_estatuto_borrador'."
        )
    if not analisis:
        raise ValueError(
            "Agente Sociedades debe producir 'analisis_societario_tecnico'."
        )

    return {
        "vehiculo_juridico_recomendado": vehiculo,
        "estrategia_aislamiento_riesgo": aislamiento,
        "puntos_estatuto_borrador": estatuto,
        "analisis_societario_tecnico": analisis,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.reporte_agente_sociedades = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteSociedades:
    """Especialista Nivel 3: Derecho Societario y Estructuras Corporativas."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Agente Sociedades requiere ANTHROPIC_API_KEY (sin modo demo "
                "para especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_B", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteSociedades invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_B o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_sociedades or "").strip()
            or str(state.tareas_senior_b or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Agente Sociedades sin mandato: falta 'instrucciones_para_sociedades' "
                "o 'tareas_senior_b'."
            )

        user = (
            "Estado actual del MALS para Agente de Sociedades (JSON). Aplicá tu "
            "algoritmo y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_sociedades(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_SOCIEDADES,
            user=user,
            model=self.model,
            max_tokens=2400,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_sociedades_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso del especialista de Sociedades."""
    return AgenteSociedades(provider=provider, model=model).run(state)

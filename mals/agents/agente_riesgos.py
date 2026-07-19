"""Agente de Riesgos — Oficial de Cumplimiento Normativo (Nivel 3).

Matriz regulatoria y alertas de compliance para Senior B.
No avanza `status_flujo`. Escribe el JSON mandatorio en `reporte_agente_riesgos`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState

SYS_AGENTE_RIESGOS = """\
Role: Oficial de Cumplimiento Normativo / Compliance Officer (Nivel 3)
Objetivo: Identificar riesgos regulatorios penales, administrativos y de \
privacidad para asegurar el cumplimiento de la ley (Compliance).

INSTRUCCIONES DE OPERACIÓN:
1. Analiza la situación operativa enviada por tu Senior \
('instrucciones_para_riesgos'). Si está vacío, usá 'tareas_senior_b' y la \
'consulta_usuario' como mandato. Si existe 'reporte_agente_sociedades', \
cruzá fricciones entre estructura societaria y obligaciones de compliance.
2. Si 'historial_criticas' / 'comentarios_critica' apuntan a compliance, \
GDPR, AML, anticorrupción, privacidad o sanciones, priorizá subsanar esas fallas.
3. Evalúa riesgos en las siguientes áreas críticas: Privacidad/Protección de \
Datos (GDPR/Locales), Antilavado de Dinero (AML), Anticorrupción y \
Regulaciones Sectoriales Estatales.
4. Diseña una matriz de mitigación de riesgos con parámetros claros.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "matriz_riesgo_regulatorio": [
    {
      "factor_riesgo": "string",
      "impacto": "Alto|Medio|Bajo",
      "probabilidad": "Alta|Media|Baja",
      "mitigacion_obligatoria": "string"
    }
  ],
  "alertas_legales_criticas": ["string"],
  "analisis_compliance_tecnico": "string"
}

TONO:
Preventivo, auditor, normativo. Entregá materia prima rigurosa para que \
Senior B consolide el blindaje de cumplimiento.
"""

_IMPACTOS = {"alto", "medio", "bajo"}
_PROBABILIDADES = {"alta", "media", "baja"}


def _norm_label(value: Any, permitted: set[str], default: str) -> str:
    text = str(value or "").strip()
    if text.lower() in permitted:
        # Preserve canonical Spanish casing from default map
        canon = {
            "alto": "Alto",
            "medio": "Medio",
            "bajo": "Bajo",
            "alta": "Alta",
            "media": "Media",
            "baja": "Baja",
        }
        return canon.get(text.lower(), text)
    return default


def _normalizar_matriz(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    limpios: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor_riesgo", "") or "").strip()
        mitigacion = str(item.get("mitigacion_obligatoria", "") or "").strip()
        if not factor and not mitigacion:
            continue
        limpios.append(
            {
                "factor_riesgo": factor,
                "impacto": _norm_label(item.get("impacto"), _IMPACTOS, "Medio"),
                "probabilidad": _norm_label(
                    item.get("probabilidad"), _PROBABILIDADES, "Media"
                ),
                "mitigacion_obligatoria": mitigacion,
            }
        )
    return limpios


def _normalizar_alertas(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return [str(raw).strip()] if raw else []
    return [str(x).strip() for x in raw if str(x).strip()]


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    matriz = _normalizar_matriz(payload.get("matriz_riesgo_regulatorio", []))
    alertas = _normalizar_alertas(payload.get("alertas_legales_criticas", []))
    analisis = str(payload.get("analisis_compliance_tecnico", "") or "").strip()

    if not matriz:
        raise ValueError(
            "Agente Riesgos debe incluir al menos un ítem en "
            "'matriz_riesgo_regulatorio'."
        )
    if not alertas:
        raise ValueError(
            "Agente Riesgos debe listar 'alertas_legales_criticas'."
        )
    if not analisis:
        raise ValueError(
            "Agente Riesgos debe producir 'analisis_compliance_tecnico'."
        )

    return {
        "matriz_riesgo_regulatorio": matriz,
        "alertas_legales_criticas": alertas,
        "analisis_compliance_tecnico": analisis,
    }


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.reporte_agente_riesgos = json.dumps(salida, ensure_ascii=False, indent=2)
    return state


class AgenteRiesgos:
    """Especialista Nivel 3: Compliance Officer / Riesgos regulatorios."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Agente Riesgos requiere ANTHROPIC_API_KEY (sin modo demo "
                "para especialistas Nivel 3)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        if state.status_flujo not in {"PROCESANDO_B", "PROCESANDO_AMBOS"}:
            raise ValueError(
                f"AgenteRiesgos invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: PROCESANDO_B o PROCESANDO_AMBOS."
            )
        mandato = (
            str(state.instrucciones_para_riesgos or "").strip()
            or str(state.tareas_senior_b or "").strip()
        )
        if not mandato:
            raise ValueError(
                "Agente Riesgos sin mandato: falta 'instrucciones_para_riesgos' "
                "o 'tareas_senior_b'."
            )

        user = (
            "Estado actual del MALS para Agente de Riesgos / Compliance (JSON). "
            "Aplicá tu algoritmo y devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_agente_riesgos(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_AGENTE_RIESGOS,
            user=user,
            model=self.model,
            max_tokens=2600,
        )
        salida = _normalizar_salida(raw)
        _aplicar_al_estado(state, salida)
        return salida


def agente_riesgos_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso del especialista de Riesgos/Compliance."""
    return AgenteRiesgos(provider=provider, model=model).run(state)

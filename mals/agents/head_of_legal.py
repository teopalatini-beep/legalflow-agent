"""Head of Legal / CLO — Nivel 1 (Directivo).

Orquestador supremo y auditor de calidad. Opera solo en TRIAGE y REVISION_HEAD.
Responde exclusivamente con el contrato JSON mandatorio del rol.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMError, LLMProvider, get_provider
from mals.state import LegalState, StatusFlujo

STATUS_PERMITIDOS: tuple[str, ...] = (
    "PROCESANDO_A",
    "PROCESANDO_B",
    "PROCESANDO_AMBOS",
    "REVISION_HEAD",
    "APROBADO",
)

SYS_HEAD_OF_LEGAL = """\
Role: Head of Legal / Chief Legal Officer (CLO) & Quality Auditor
Jurisdiction: International Corporate Law & Enterprise Risk Management

CONTEXTO OPERATIVO:
Eres el Director Supremo de un departamento legal corporativo automatizado. Tu \
responsabilidad principal es proteger los intereses de la empresa, tomar \
decisiones macro-estratégicas y auditar de forma implacable el trabajo técnico \
de tus dos subordinados directos: Senior A (Litigios y Contratos) y Senior B \
(Sociedades y Compliance). El sistema opera en un bucle autónomo basado en el \
estado actual del flujo.

INSTRUCCIONES DE ALGORITMO INTERNO:

1. SI EL 'STATUS_FLUJO' ES "TRIAGE":
   - Analiza con frialdad la 'consulta_usuario'.
   - Determina el impacto y las áreas afectadas.
   - Diseña un 'plan_estrategico' macro.
   - Divide las instrucciones de investigación. Si el problema requiere análisis \
de contratos o demandas, escribe directrices en 'tareas_senior_a'. Si requiere \
ver estructuras de la empresa, actas o riesgos regulatorios/multas, escribe en \
'tareas_senior_b'.
   - Cambia el 'proximo_status_flujo' a "PROCESANDO_A", "PROCESANDO_B" o \
"PROCESANDO_AMBOS" según corresponda.
   - En TRIAGE: evaluacion_calidad=0, comentarios_critica="", dictamen_ejecutivo_final="".

2. SI EL 'STATUS_FLUJO' ES "REVISION_HEAD":
   - Evalúa con el más alto rigor los campos 'reporte_senior_a' y/o \
'reporte_senior_b' acumulados en el Estado.
   - Actúa como un auditor hostil: Busca lagunas legales, contradicciones entre \
áreas, lenguaje ambiguo o falta de soluciones de negocio reales.
   - Asigna una calificación interna del 1 al 10 en 'evaluacion_calidad'.
   - CRITERIO DE RECHAZO (LOOP ACTIVATED): Si la calidad es MENOR a 9, debes \
RECHAZAR el entregable. Describe minuciosamente qué errores técnicos o vacíos \
encontraste y regístralos en 'comentarios_critica'. Cambia el \
'proximo_status_flujo' de vuelta al Senior responsable ("PROCESANDO_A", \
"PROCESANDO_B" o "PROCESANDO_AMBOS") para forzar el re-procesamiento. Dejá \
dictamen_ejecutivo_final vacío.
   - CRITERIO DE APROBACIÓN: Si la calidad es 9 o 10, redacta el \
'dictamen_ejecutivo_final'. Debe ser un texto ejecutivo impecable, directo, \
orientado a la toma de decisiones del CEO, con los pasos legales exactos a \
seguir. Cambia el 'proximo_status_flujo' a "APROBADO". comentarios_critica vacío.

FORMATO MANDATORIO DE SALIDA:
Respondés ÚNICA Y EXCLUSIVAMENTE con un objeto JSON válido (sin markdown). \
Claves exactas:
{
  "analisis_macro": "string",
  "plan_estrategico": "string",
  "tareas_senior_a": "string",
  "tareas_senior_b": "string",
  "evaluacion_calidad": 0.0,
  "comentarios_critica": "string",
  "dictamen_ejecutivo_final": "string",
  "proximo_status_flujo": "PROCESANDO_A|PROCESANDO_B|PROCESANDO_AMBOS|REVISION_HEAD|APROBADO"
}

TONO:
Ejecutivo, severo, analítico, enfocado en el negocio y la mitigación absoluta \
de riesgos. No toleras respuestas incompletas de tu equipo.
"""


def _normalizar_salida(payload: Dict[str, Any]) -> Dict[str, Any]:
    proximo = str(payload.get("proximo_status_flujo", "")).strip().upper()
    if proximo not in STATUS_PERMITIDOS:
        raise ValueError(
            f"proximo_status_flujo inválido: '{proximo}'. "
            f"Permitidos: {', '.join(STATUS_PERMITIDOS)}"
        )

    try:
        calidad = float(payload.get("evaluacion_calidad", 0) or 0)
    except (TypeError, ValueError) as err:
        raise ValueError("evaluacion_calidad debe ser numérico.") from err
    calidad = max(0.0, min(10.0, calidad))

    return {
        "analisis_macro": str(payload.get("analisis_macro", "") or ""),
        "plan_estrategico": str(payload.get("plan_estrategico", "") or ""),
        "tareas_senior_a": str(payload.get("tareas_senior_a", "") or ""),
        "tareas_senior_b": str(payload.get("tareas_senior_b", "") or ""),
        "evaluacion_calidad": calidad,
        "comentarios_critica": str(payload.get("comentarios_critica", "") or ""),
        "dictamen_ejecutivo_final": str(
            payload.get("dictamen_ejecutivo_final", "") or ""
        ),
        "proximo_status_flujo": proximo,
    }


def _aplicar_reglas_negocio(
    status_actual: StatusFlujo, salida: Dict[str, Any]
) -> Dict[str, Any]:
    """Endurece el contrato del rol (no confiar solo en el LLM)."""
    proximo = salida["proximo_status_flujo"]
    calidad = salida["evaluacion_calidad"]

    if status_actual == "TRIAGE":
        salida["evaluacion_calidad"] = 0.0
        salida["comentarios_critica"] = ""
        salida["dictamen_ejecutivo_final"] = ""
        if proximo not in {"PROCESANDO_A", "PROCESANDO_B", "PROCESANDO_AMBOS"}:
            # Inferencia segura si el modelo se desvía
            tiene_a = bool(salida["tareas_senior_a"].strip())
            tiene_b = bool(salida["tareas_senior_b"].strip())
            if tiene_a and tiene_b:
                salida["proximo_status_flujo"] = "PROCESANDO_AMBOS"
            elif tiene_b:
                salida["proximo_status_flujo"] = "PROCESANDO_B"
            else:
                salida["proximo_status_flujo"] = "PROCESANDO_A"
        return salida

    if status_actual == "REVISION_HEAD":
        if calidad < 9.0:
            salida["dictamen_ejecutivo_final"] = ""
            if not salida["comentarios_critica"].strip():
                salida["comentarios_critica"] = (
                    "Rechazo automático: calidad < 9/10 sin detalle suficiente. "
                    "Reprocesar con evidencia, contradicciones resueltas y "
                    "recomendaciones de negocio concretas."
                )
            if proximo not in {"PROCESANDO_A", "PROCESANDO_B", "PROCESANDO_AMBOS"}:
                # Por defecto reabrir ambos si no especifica
                salida["proximo_status_flujo"] = "PROCESANDO_AMBOS"
        else:
            salida["comentarios_critica"] = ""
            salida["proximo_status_flujo"] = "APROBADO"
            if not salida["dictamen_ejecutivo_final"].strip():
                salida["dictamen_ejecutivo_final"] = (
                    "Aprobado con calidad >= 9. Ejecutar el plan estratégico "
                    "acordado; legal ops debe documentar owners y deadlines."
                )
        return salida

    raise ValueError(
        f"Head of Legal no opera en status_flujo='{status_actual}'. "
        "Solo TRIAGE o REVISION_HEAD."
    )


def _aplicar_al_estado(state: LegalState, salida: Dict[str, Any]) -> LegalState:
    state.analisis_macro = salida["analisis_macro"]
    state.plan_estrategico = salida["plan_estrategico"]
    state.tareas_senior_a = salida["tareas_senior_a"]
    state.tareas_senior_b = salida["tareas_senior_b"]
    state.evaluacion_calidad = salida["evaluacion_calidad"]
    state.comentarios_critica = salida["comentarios_critica"]
    state.dictamen_ejecutivo_final = salida["dictamen_ejecutivo_final"]

    if state.status_flujo == "REVISION_HEAD" and salida["evaluacion_calidad"] < 9.0:
        state.ciclo_revision += 1
        state.historial_criticas.append(
            {
                "ciclo": state.ciclo_revision,
                "evaluacion_calidad": salida["evaluacion_calidad"],
                "comentarios_critica": salida["comentarios_critica"],
                "proximo_status_flujo": salida["proximo_status_flujo"],
            }
        )

    state.status_flujo = salida["proximo_status_flujo"]  # type: ignore[assignment]
    return state


class HeadOfLegal:
    """Agente Nivel 1: triage estratégico + auditoría hostil de Seniors."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
    ) -> None:
        self.provider = provider or get_provider(prefer="claude", default_model=model)
        self.model = model
        if self.provider is None:
            raise LLMError(
                "Head of Legal requiere ANTHROPIC_API_KEY (no hay modo demo "
                "para el CLO: las decisiones macro no se simulan por keywords)."
            )

    def run(self, state: LegalState) -> Dict[str, Any]:
        """Ejecuta un turno del Head y muta `state`. Devuelve el JSON normalizado."""
        if state.status_flujo not in {"TRIAGE", "REVISION_HEAD"}:
            raise ValueError(
                f"HeadOfLegal invocado con status_flujo='{state.status_flujo}'. "
                "Esperado: TRIAGE o REVISION_HEAD."
            )

        user = (
            "Estado actual del MALS (JSON). Aplicá el algoritmo de tu rol y "
            "devolvé ÚNICAMENTE el objeto JSON mandatorio.\n\n"
            f"{json.dumps(state.snapshot_para_head(), ensure_ascii=False, indent=2)}"
        )
        raw = self.provider.complete_json(
            system=SYS_HEAD_OF_LEGAL,
            user=user,
            model=self.model,
            max_tokens=2500,
        )
        salida = _aplicar_reglas_negocio(state.status_flujo, _normalizar_salida(raw))
        _aplicar_al_estado(state, salida)
        return salida


def head_of_legal_step(
    state: LegalState,
    *,
    provider: Optional[LLMProvider] = None,
    model: str = DEFAULT_CLAUDE_MODEL,
) -> Dict[str, Any]:
    """Atajo funcional: un paso del Head of Legal sobre el estado compartido."""
    return HeadOfLegal(provider=provider, model=model).run(state)

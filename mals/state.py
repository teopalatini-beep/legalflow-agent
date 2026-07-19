"""Estado global compartido del MALS.

Fuente de verdad del bucle cerrado. Los agentes leen este objeto y escriben
solo los campos de su responsabilidad; el orquestador avanza `status_flujo`
según `proximo_status_flujo` que emite cada agente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


StatusFlujo = Literal[
    "TRIAGE",
    "PROCESANDO_A",
    "PROCESANDO_B",
    "PROCESANDO_AMBOS",
    "REVISION_HEAD",
    "APROBADO",
]


@dataclass
class LegalState:
    """Estado compartido del sistema multi-agente legal."""

    consulta_usuario: str = ""
    status_flujo: StatusFlujo = "TRIAGE"

    # Salidas del Head (triage / auditoría)
    analisis_macro: str = ""
    plan_estrategico: str = ""
    tareas_senior_a: str = ""
    tareas_senior_b: str = ""
    evaluacion_calidad: float = 0.0
    comentarios_critica: str = ""
    dictamen_ejecutivo_final: str = ""

    # Reportes de Seniors
    reporte_senior_a: str = ""
    reporte_senior_b: str = ""

    # Intermedios Nivel 3 bajo Senior A (Causas / Contratos)
    reporte_agente_causas: str = ""
    reporte_agente_contratos: str = ""
    instrucciones_para_causas: str = ""
    instrucciones_para_contratos: str = ""
    analisis_contradicciones_a: str = ""

    # Intermedios Nivel 3 bajo Senior B (Sociedades / Riesgos)
    reporte_agente_sociedades: str = ""
    reporte_agente_riesgos: str = ""
    instrucciones_para_sociedades: str = ""
    instrucciones_para_riesgos: str = ""
    analisis_friccion_regulatoria: str = ""

    # Memoria del loop de calidad
    historial_criticas: List[Dict[str, Any]] = field(default_factory=list)
    ciclo_revision: int = 0

    def snapshot_para_head(self) -> Dict[str, Any]:
        """Vista mínima que necesita el Head of Legal para decidir."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "tareas_senior_a": self.tareas_senior_a,
            "tareas_senior_b": self.tareas_senior_b,
            "reporte_senior_a": self.reporte_senior_a,
            "reporte_senior_b": self.reporte_senior_b,
            "historial_criticas": self.historial_criticas,
            "ciclo_revision": self.ciclo_revision,
            "evaluacion_calidad": self.evaluacion_calidad,
            "comentarios_critica": self.comentarios_critica,
            "dictamen_ejecutivo_final": self.dictamen_ejecutivo_final,
        }

    def snapshot_para_senior_a(self) -> Dict[str, Any]:
        """Vista para Senior A (Litigios y Contratos)."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_a": self.tareas_senior_a,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_causas": self.reporte_agente_causas,
            "reporte_agente_contratos": self.reporte_agente_contratos,
            "reporte_senior_a_previo": self.reporte_senior_a,
        }

    def snapshot_para_senior_b(self) -> Dict[str, Any]:
        """Vista para Senior B (Sociedades y Compliance)."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_b": self.tareas_senior_b,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_sociedades": self.reporte_agente_sociedades,
            "reporte_agente_riesgos": self.reporte_agente_riesgos,
            "reporte_senior_b_previo": self.reporte_senior_b,
        }

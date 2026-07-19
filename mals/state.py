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

    # Intermedios Nivel 3 bajo Senior A (Causas / Contratos / Soporte A)
    reporte_agente_causas: str = ""
    reporte_agente_contratos: str = ""
    reporte_agente_soporte_a: str = ""
    instrucciones_para_causas: str = ""
    instrucciones_para_contratos: str = ""
    instrucciones_para_soporte_a: str = ""
    analisis_contradicciones_a: str = ""

    # Intermedios Nivel 3 bajo Senior B (Sociedades / Riesgos / Soporte B)
    reporte_agente_sociedades: str = ""
    reporte_agente_riesgos: str = ""
    reporte_agente_soporte_b: str = ""
    instrucciones_para_sociedades: str = ""
    instrucciones_para_riesgos: str = ""
    instrucciones_para_soporte_b: str = ""
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
            "reporte_agente_soporte_a": self.reporte_agente_soporte_a,
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
            "reporte_agente_soporte_b": self.reporte_agente_soporte_b,
            "reporte_senior_b_previo": self.reporte_senior_b,
        }

    def snapshot_para_agente_causas(self) -> Dict[str, Any]:
        """Vista para el especialista Nivel 3 de Litigios/Causas."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_a": self.tareas_senior_a,
            "instrucciones_para_causas": self.instrucciones_para_causas,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_causas_previo": self.reporte_agente_causas,
        }

    def snapshot_para_agente_contratos(self) -> Dict[str, Any]:
        """Vista para el especialista Nivel 3 de Contratos."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_a": self.tareas_senior_a,
            "instrucciones_para_contratos": self.instrucciones_para_contratos,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_causas": self.reporte_agente_causas,
            "reporte_agente_contratos_previo": self.reporte_agente_contratos,
        }

    def snapshot_para_agente_sociedades(self) -> Dict[str, Any]:
        """Vista para el especialista Nivel 3 de Sociedades."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_b": self.tareas_senior_b,
            "instrucciones_para_sociedades": self.instrucciones_para_sociedades,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_sociedades_previo": self.reporte_agente_sociedades,
        }

    def snapshot_para_agente_riesgos(self) -> Dict[str, Any]:
        """Vista para el especialista Nivel 3 de Riesgos/Compliance."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_b": self.tareas_senior_b,
            "instrucciones_para_riesgos": self.instrucciones_para_riesgos,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_sociedades": self.reporte_agente_sociedades,
            "reporte_agente_riesgos_previo": self.reporte_agente_riesgos,
        }

    def snapshot_para_agente_soporte_a(self) -> Dict[str, Any]:
        """Vista para Soporte A (Laboral / Administrativo)."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_a": self.tareas_senior_a,
            "instrucciones_para_soporte_a": self.instrucciones_para_soporte_a,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_causas": self.reporte_agente_causas,
            "reporte_agente_contratos": self.reporte_agente_contratos,
            "reporte_agente_soporte_a_previo": self.reporte_agente_soporte_a,
        }

    def snapshot_para_agente_soporte_b(self) -> Dict[str, Any]:
        """Vista para Soporte B (Tributario / Propiedad Intelectual)."""
        return {
            "status_flujo": self.status_flujo,
            "consulta_usuario": self.consulta_usuario,
            "plan_estrategico": self.plan_estrategico,
            "tareas_senior_b": self.tareas_senior_b,
            "instrucciones_para_soporte_b": self.instrucciones_para_soporte_b,
            "historial_criticas": self.historial_criticas,
            "comentarios_critica": self.comentarios_critica,
            "ciclo_revision": self.ciclo_revision,
            "reporte_agente_sociedades": self.reporte_agente_sociedades,
            "reporte_agente_riesgos": self.reporte_agente_riesgos,
            "reporte_agente_soporte_b_previo": self.reporte_agente_soporte_b,
        }

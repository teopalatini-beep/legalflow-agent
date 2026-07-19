"""Agentes del MALS."""

from mals.agents.agente_causas import AgenteCausas, agente_causas_step
from mals.agents.agente_contratos import AgenteContratos, agente_contratos_step
from mals.agents.agente_riesgos import AgenteRiesgos, agente_riesgos_step
from mals.agents.agente_sociedades import AgenteSociedades, agente_sociedades_step
from mals.agents.agente_soporte_a import AgenteSoporteA, agente_soporte_a_step
from mals.agents.agente_soporte_b import AgenteSoporteB, agente_soporte_b_step
from mals.agents.head_of_legal import HeadOfLegal, head_of_legal_step
from mals.agents.senior_a import SeniorA, senior_a_step
from mals.agents.senior_b import SeniorB, senior_b_step

__all__ = [
    "HeadOfLegal",
    "head_of_legal_step",
    "SeniorA",
    "senior_a_step",
    "SeniorB",
    "senior_b_step",
    "AgenteCausas",
    "agente_causas_step",
    "AgenteContratos",
    "agente_contratos_step",
    "AgenteSociedades",
    "agente_sociedades_step",
    "AgenteRiesgos",
    "agente_riesgos_step",
    "AgenteSoporteA",
    "agente_soporte_a_step",
    "AgenteSoporteB",
    "agente_soporte_b_step",
]
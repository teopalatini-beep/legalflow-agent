"""Paquete de especialistas Nivel 3 (paths de importación estables)."""

from mals.agents.specialists.causas import AgenteCausas
from mals.agents.specialists.contratos import AgenteContratos
from mals.agents.specialists.riesgos import AgenteRiesgos
from mals.agents.specialists.sociedades import AgenteSociedades
from mals.agents.specialists.soporte_a import AgenteSoporteA
from mals.agents.specialists.soporte_b import AgenteSoporteB

__all__ = [
    "AgenteCausas",
    "AgenteContratos",
    "AgenteSociedades",
    "AgenteRiesgos",
    "AgenteSoporteA",
    "AgenteSoporteB",
]

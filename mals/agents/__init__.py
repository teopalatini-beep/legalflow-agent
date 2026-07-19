"""Agentes del MALS."""

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
]
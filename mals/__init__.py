"""MALS — Multi-Agent Legal System (jerárquico, state-driven)."""

from mals.orchestrator import MALSOrchestrator
from mals.state import LegalState, StatusFlujo

__all__ = ["LegalState", "StatusFlujo", "MALSOrchestrator"]

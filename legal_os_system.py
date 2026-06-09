from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class MatterEvent:
    timestamp: str
    type: str
    payload: Dict[str, Any]


@dataclass
class Matter:
    matter_id: str
    cliente_id: str
    status: str = "draft"
    metadata: Dict[str, Any] = field(default_factory=dict)
    events: List[MatterEvent] = field(default_factory=list)

    def add_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.events.append(
            MatterEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                type=event_type,
                payload=payload,
            )
        )


class MatterAgent:
    """Primer esqueleto para el Legal OS.

    Centraliza la evolucion del expediente legal y sus hitos.
    """

    def create_matter(self, matter_id: str, cliente_id: str, metadata: Dict[str, Any]) -> Matter:
        matter = Matter(matter_id=matter_id, cliente_id=cliente_id, metadata=metadata)
        matter.add_event("matter_created", metadata)
        return matter

    def attach_analysis(self, matter: Matter, analysis_result: Dict[str, Any]) -> None:
        matter.status = "analysis_ready"
        matter.add_event("analysis_attached", {"quality_score": analysis_result.get("quality_score", 0)})

    def request_approval(self, matter: Matter, approver: str) -> None:
        matter.status = "pending_approval"
        matter.add_event("approval_requested", {"approver": approver})

    def mark_signed(self, matter: Matter, signed_by: str) -> None:
        matter.status = "signed"
        matter.add_event("contract_signed", {"signed_by": signed_by})

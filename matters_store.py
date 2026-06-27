from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

BASE_PATH = Path(__file__).parent
MATTERS_DIR = BASE_PATH / "data" / "matters"


def _ensure_dir() -> None:
    MATTERS_DIR.mkdir(parents=True, exist_ok=True)


def _matter_path(matter_id: str) -> Path:
    return MATTERS_DIR / f"{matter_id}.json"


def create_matter(matter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dir()
    data = {
        "matter_id": matter_id,
        "status": "draft",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "events": [],
        "document_versions": [],
        "approvals": [],
        **payload,
    }
    save_matter(matter_id, data)
    return data


def save_matter(matter_id: str, data: Dict[str, Any]) -> None:
    _ensure_dir()
    _matter_path(matter_id).write_text(
        json.dumps(data, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )


def get_matter(matter_id: str) -> Dict[str, Any] | None:
    path = _matter_path(matter_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_matters(limit: int = 200) -> list[Dict[str, Any]]:
    _ensure_dir()
    items: list[Dict[str, Any]] = []
    for path in MATTERS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if "matter_id" not in data:
            data["matter_id"] = path.stem
        items.append(data)

    def _sort_key(item: Dict[str, Any]) -> str:
        return str(item.get("updated_at") or item.get("created_at") or "")

    items.sort(key=_sort_key, reverse=True)
    return items[:limit]


def append_event(matter_id: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "payload": payload,
    }
    matter.setdefault("events", []).append(event)
    save_matter(matter_id, matter)
    return matter


def update_status(matter_id: str, status: str) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    matter["status"] = status
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return matter


def update_esign_tracking(matter_id: str, tracking: Dict[str, Any]) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    esign = matter.setdefault("esign", {})
    esign.update(tracking)
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return matter


def save_hitl_dispatch(
    matter_id: str,
    *,
    approved_by: str,
    approved_at: str,
    analysis_reviewed: Dict[str, Any],
    destination: str,
    routing_status: str = "dispatched",
) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    matter["hitl"] = {
        "approved_by": approved_by,
        "approved_at": approved_at,
        "analysis_reviewed": analysis_reviewed,
    }
    matter["routing"] = {
        "destination": destination,
        "status": routing_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    matter["status"] = "Despachado / Enviado"
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return matter


def register_esign_webhook_event_id(matter_id: str, event_id: str) -> bool:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    esign = matter.setdefault("esign", {})
    processed = esign.setdefault("processed_event_ids", [])
    if event_id in processed:
        return False
    processed.append(event_id)
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return True


def find_matter_by_envelope_id(envelope_id: str) -> Dict[str, Any] | None:
    _ensure_dir()
    for path in MATTERS_DIR.glob("*.json"):
        matter = json.loads(path.read_text(encoding="utf-8"))
        if matter.get("esign", {}).get("envelope_id") == envelope_id:
            return matter
    return None


def add_document_version(
    matter_id: str,
    *,
    filename: str,
    doc_hash: str,
    created_by: str,
    source: str = "manual",
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    versions = matter.setdefault("document_versions", [])
    version_number = len(versions) + 1
    version = {
        "version_id": f"ver_{uuid4().hex[:12]}",
        "number": version_number,
        "filename": filename,
        "doc_hash": doc_hash,
        "source": source,
        "metadata": metadata or {},
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    versions.append(version)
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return version


def request_approvals(
    matter_id: str, *, reviewers: list[str], requested_by: str, note: str = ""
) -> Dict[str, Any]:
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    approvals = matter.setdefault("approvals", [])
    created = []
    for reviewer in reviewers:
        item = {
            "approval_id": f"apr_{uuid4().hex[:12]}",
            "reviewer": reviewer,
            "status": "pending",
            "requested_by": requested_by,
            "note": note,
            "requested_at": datetime.now(timezone.utc).isoformat(),
        }
        approvals.append(item)
        created.append(item)
    matter["status"] = "pending_approval"
    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return {"created": created, "total": len(created)}


def decision_approval(
    matter_id: str, approval_id: str, *, decision: str, decided_by: str, note: str = ""
) -> Dict[str, Any]:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Decision invalida.")
    matter = get_matter(matter_id)
    if not matter:
        raise FileNotFoundError(f"Matter '{matter_id}' no existe.")
    approvals = matter.setdefault("approvals", [])
    target = None
    for item in approvals:
        if item.get("approval_id") == approval_id:
            target = item
            break
    if not target:
        raise KeyError(f"Approval '{approval_id}' no existe.")
    target["status"] = decision
    target["decided_by"] = decided_by
    target["decision_note"] = note
    target["decided_at"] = datetime.now(timezone.utc).isoformat()

    if any(x.get("status") == "rejected" for x in approvals):
        matter["status"] = "changes_requested"
    elif approvals and all(x.get("status") == "approved" for x in approvals):
        matter["status"] = "approved"
    else:
        matter["status"] = "pending_approval"

    matter["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_matter(matter_id, matter)
    return target

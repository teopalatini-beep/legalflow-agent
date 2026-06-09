from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

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

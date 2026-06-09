from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

BASE_PATH = Path(__file__).parent
DATA_DIR = BASE_PATH / "data"
METRICS_FILE = DATA_DIR / "metrics.jsonl"
AUDIT_FILE = DATA_DIR / "audit.jsonl"
CASES_DIR = DATA_DIR / "cases"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CASES_DIR.mkdir(parents=True, exist_ok=True)


def redact_sensitive(text: str) -> str:
    text = re.sub(r"\b\d{2}-\d{8}-\d\b", "[CUIT_REDACTED]", text)
    text = re.sub(r"\b[\w\.-]+@[\w\.-]+\.\w+\b", "[EMAIL_REDACTED]", text)
    text = re.sub(r"\b\d{6,}\b", "[NUMBER_REDACTED]", text)
    return text


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    ensure_data_dirs()
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")


def audit_log(event: str, details: Dict[str, Any]) -> None:
    append_jsonl(
        AUDIT_FILE,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details,
        },
    )


def metric_log(metric_name: str, value: Any, tags: Dict[str, Any]) -> None:
    append_jsonl(
        METRICS_FILE,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metric": metric_name,
            "value": value,
            "tags": tags,
        },
    )


def retention_cleanup(retention_days: int = 30) -> int:
    ensure_data_dirs()
    deleted = 0
    limit = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for path in CASES_DIR.glob("*.json"):
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if mtime < limit:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted

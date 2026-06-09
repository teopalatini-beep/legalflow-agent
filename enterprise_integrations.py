from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

BASE_PATH = Path(__file__).parent
INTEGRATIONS_DIR = BASE_PATH / "data" / "integrations"


def _ensure_dirs() -> None:
    INTEGRATIONS_DIR.mkdir(parents=True, exist_ok=True)


def _append_event(stream: str, payload: Dict[str, Any]) -> None:
    _ensure_dirs()
    path = INTEGRATIONS_DIR / f"{stream}.jsonl"
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(event, ensure_ascii=True) + "\n")


class CRMConnector:
    """Conector CRM inicial (modo event-log para fase 3)."""

    provider = "generic-crm"

    def sync_matter(self, matter_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        crm_ref = f"crm_{hashlib.sha1(matter_id.encode()).hexdigest()[:12]}"
        _append_event(
            "crm_sync",
            {
                "provider": self.provider,
                "matter_id": matter_id,
                "crm_ref": crm_ref,
                "payload": payload,
            },
        )
        return {"provider": self.provider, "crm_ref": crm_ref, "status": "synced"}


class DMSConnector:
    """Conector DMS inicial (metadata + hash de documento)."""

    provider = "generic-dms"

    def upload_document(
        self, matter_id: str, filename: str, content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        dms_ref = f"dms_{doc_hash[:16]}"
        _append_event(
            "dms_upload",
            {
                "provider": self.provider,
                "matter_id": matter_id,
                "dms_ref": dms_ref,
                "filename": filename,
                "doc_hash": doc_hash,
                "metadata": metadata,
            },
        )
        return {"provider": self.provider, "dms_ref": dms_ref, "status": "uploaded"}


class ESignatureConnector:
    """Conector e-signature inicial (solicitud de firma)."""

    provider = "generic-esign"

    def request_signature(
        self, matter_id: str, signer_email: str, document_ref: str
    ) -> Dict[str, Any]:
        envelope_id = f"env_{hashlib.md5(f'{matter_id}:{signer_email}'.encode()).hexdigest()[:14]}"
        _append_event(
            "esign_requests",
            {
                "provider": self.provider,
                "matter_id": matter_id,
                "signer_email": signer_email,
                "document_ref": document_ref,
                "envelope_id": envelope_id,
                "status": "signature_requested",
            },
        )
        return {
            "provider": self.provider,
            "envelope_id": envelope_id,
            "status": "signature_requested",
        }

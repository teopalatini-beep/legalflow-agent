from __future__ import annotations

import hashlib
import json
import os
from urllib import error, request
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

    def _real_provider_config(self) -> Dict[str, str]:
        return {
            "endpoint": os.getenv("LEGALFLOW_ESIGN_ENDPOINT", "").strip(),
            "api_key": os.getenv("LEGALFLOW_ESIGN_API_KEY", "").strip(),
        }

    def _real_request(
        self, endpoint: str, api_key: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with request.urlopen(req, timeout=10) as resp:
            response_raw = resp.read().decode("utf-8")
            try:
                return json.loads(response_raw) if response_raw else {}
            except json.JSONDecodeError:
                return {"raw_response": response_raw}

    def request_signature(
        self, matter_id: str, signer_email: str, document_ref: str
    ) -> Dict[str, Any]:
        cfg = self._real_provider_config()
        if cfg["endpoint"] and cfg["api_key"]:
            payload = {
                "matter_id": matter_id,
                "signer_email": signer_email,
                "document_ref": document_ref,
            }
            try:
                external = self._real_request(cfg["endpoint"], cfg["api_key"], payload)
                envelope_id = external.get("envelope_id") or external.get("id") or f"env_real_{hashlib.md5(matter_id.encode()).hexdigest()[:12]}"
                _append_event(
                    "esign_requests",
                    {
                        "provider": "external-esign",
                        "mode": "real",
                        "matter_id": matter_id,
                        "signer_email": signer_email,
                        "document_ref": document_ref,
                        "envelope_id": envelope_id,
                        "external_response": external,
                        "status": "signature_requested",
                    },
                )
                return {
                    "provider": "external-esign",
                    "mode": "real",
                    "envelope_id": envelope_id,
                    "status": "signature_requested",
                }
            except (error.URLError, TimeoutError, ValueError) as err:
                _append_event(
                    "esign_requests",
                    {
                        "provider": "external-esign",
                        "mode": "fallback_simulation",
                        "matter_id": matter_id,
                        "signer_email": signer_email,
                        "document_ref": document_ref,
                        "status": "provider_error_fallback",
                        "error": str(err),
                    },
                )

        envelope_id = f"env_{hashlib.md5(f'{matter_id}:{signer_email}'.encode()).hexdigest()[:14]}"
        _append_event(
            "esign_requests",
            {
                "provider": self.provider,
                "mode": "simulation",
                "matter_id": matter_id,
                "signer_email": signer_email,
                "document_ref": document_ref,
                "envelope_id": envelope_id,
                "status": "signature_requested",
            },
        )
        return {
            "provider": self.provider,
            "mode": "simulation",
            "envelope_id": envelope_id,
            "status": "signature_requested",
        }

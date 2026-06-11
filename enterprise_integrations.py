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
    signature_status_pending = "signature_pending"
    signature_statuses = {"signature_pending", "signed", "declined", "voided"}

    def _real_provider_config(self) -> Dict[str, str]:
        return {
            "endpoint": os.getenv("LEGALFLOW_ESIGN_ENDPOINT", "").strip(),
            "api_key": os.getenv("LEGALFLOW_ESIGN_API_KEY", "").strip(),
            "webhook_secret": os.getenv("LEGALFLOW_ESIGN_WEBHOOK_SECRET", "").strip(),
            "app_base_url": os.getenv("LEGALFLOW_APP_BASE_URL", "").strip(),
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

    def integration_health(self) -> Dict[str, Any]:
        cfg = self._real_provider_config()
        missing = []
        if not cfg["endpoint"]:
            missing.append("LEGALFLOW_ESIGN_ENDPOINT")
        if not cfg["api_key"]:
            missing.append("LEGALFLOW_ESIGN_API_KEY")
        mode = "real" if not missing else "simulation"
        return {
            "provider": self.provider,
            "mode": mode,
            "required_vars_present": not missing,
            "missing_vars": missing,
            "webhook_secret_set": bool(cfg["webhook_secret"]),
        }

    def _simulation_envelope_id(self, matter_id: str, signer_email: str) -> str:
        return f"env_{hashlib.md5(f'{matter_id}:{signer_email}'.encode()).hexdigest()[:14]}"

    def _simulation_recipient_id(self, envelope_id: str, signer_email: str) -> str:
        return f"rcp_{hashlib.md5(f'{envelope_id}:{signer_email}'.encode()).hexdigest()[:14]}"

    def _simulation_signing_url(
        self, envelope_id: str, recipient_id: str, return_url: str | None = None
    ) -> str:
        base = self._real_provider_config().get("app_base_url") or "https://legalflow.local"
        callback = return_url or f"{base}/api/integrations/esign/callback"
        return (
            f"{base}/embedded-sign?envelope_id={envelope_id}"
            f"&recipient_id={recipient_id}&return_url={callback}"
        )

    def create_envelope(
        self,
        matter_id: str,
        signer_email: str,
        document_ref: str,
        signer_name: str = "",
    ) -> Dict[str, Any]:
        cfg = self._real_provider_config()
        payload = {
            "action": "create_envelope",
            "matter_id": matter_id,
            "signer_email": signer_email,
            "signer_name": signer_name,
            "document_ref": document_ref,
        }
        if cfg["endpoint"] and cfg["api_key"]:
            try:
                external = self._real_request(cfg["endpoint"], cfg["api_key"], payload)
                envelope_id = (
                    external.get("envelope_id")
                    or external.get("id")
                    or f"env_real_{hashlib.md5(matter_id.encode()).hexdigest()[:12]}"
                )
                recipient_id = (
                    external.get("recipient_id")
                    or external.get("signer_id")
                    or self._simulation_recipient_id(envelope_id, signer_email)
                )
                result = {
                    "provider": "external-esign",
                    "mode": "real",
                    "envelope_id": envelope_id,
                    "recipient_id": recipient_id,
                    "status": self.signature_status_pending,
                    "external_response": external,
                }
                _append_event(
                    "esign_requests",
                    {
                        "provider": "external-esign",
                        "mode": "real",
                        "status": "envelope_created",
                        "matter_id": matter_id,
                        "signer_email": signer_email,
                        "document_ref": document_ref,
                        "envelope_id": envelope_id,
                        "recipient_id": recipient_id,
                        "external_response": external,
                    },
                )
                return result
            except (error.URLError, TimeoutError, ValueError) as err:
                _append_event(
                    "esign_requests",
                    {
                        "provider": "external-esign",
                        "mode": "fallback_simulation",
                        "status": "provider_error_fallback",
                        "matter_id": matter_id,
                        "signer_email": signer_email,
                        "document_ref": document_ref,
                        "error": str(err),
                    },
                )

        envelope_id = self._simulation_envelope_id(matter_id, signer_email)
        recipient_id = self._simulation_recipient_id(envelope_id, signer_email)
        _append_event(
            "esign_requests",
            {
                "provider": self.provider,
                "mode": "simulation",
                "status": "envelope_created",
                "matter_id": matter_id,
                "signer_email": signer_email,
                "document_ref": document_ref,
                "envelope_id": envelope_id,
                "recipient_id": recipient_id,
            },
        )
        return {
            "provider": self.provider,
            "mode": "simulation",
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "status": self.signature_status_pending,
        }

    def recipient_view(
        self,
        envelope_id: str,
        recipient_id: str,
        return_url: str | None = None,
    ) -> Dict[str, Any]:
        cfg = self._real_provider_config()
        payload = {
            "action": "recipient_view",
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "return_url": return_url,
        }
        if cfg["endpoint"] and cfg["api_key"]:
            try:
                external = self._real_request(cfg["endpoint"], cfg["api_key"], payload)
                signing_url = external.get("signing_url") or external.get("url")
                if signing_url:
                    result = {
                        "provider": "external-esign",
                        "mode": "real",
                        "envelope_id": envelope_id,
                        "recipient_id": recipient_id,
                        "signing_url": signing_url,
                        "status": self.signature_status_pending,
                    }
                    _append_event(
                        "esign_requests",
                        {
                            "provider": "external-esign",
                            "mode": "real",
                            "status": "recipient_view_created",
                            "envelope_id": envelope_id,
                            "recipient_id": recipient_id,
                            "signing_url": signing_url,
                        },
                    )
                    return result
            except (error.URLError, TimeoutError, ValueError) as err:
                _append_event(
                    "esign_requests",
                    {
                        "provider": "external-esign",
                        "mode": "fallback_simulation",
                        "status": "recipient_view_fallback",
                        "envelope_id": envelope_id,
                        "recipient_id": recipient_id,
                        "error": str(err),
                    },
                )

        signing_url = self._simulation_signing_url(envelope_id, recipient_id, return_url)
        _append_event(
            "esign_requests",
            {
                "provider": self.provider,
                "mode": "simulation",
                "status": "recipient_view_created",
                "envelope_id": envelope_id,
                "recipient_id": recipient_id,
                "signing_url": signing_url,
            },
        )
        return {
            "provider": self.provider,
            "mode": "simulation",
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "signing_url": signing_url,
            "status": self.signature_status_pending,
        }

    def request_signature(
        self, matter_id: str, signer_email: str, document_ref: str
    ) -> Dict[str, Any]:
        envelope = self.create_envelope(matter_id, signer_email, document_ref)
        _append_event(
            "esign_requests",
            {
                "provider": envelope.get("provider", self.provider),
                "mode": envelope.get("mode", "simulation"),
                "matter_id": matter_id,
                "signer_email": signer_email,
                "document_ref": document_ref,
                "envelope_id": envelope.get("envelope_id"),
                "recipient_id": envelope.get("recipient_id"),
                "status": "signature_requested",
            },
        )
        return {
            "provider": envelope.get("provider", self.provider),
            "mode": envelope.get("mode", "simulation"),
            "envelope_id": envelope.get("envelope_id"),
            "recipient_id": envelope.get("recipient_id"),
            "status": self.signature_status_pending,
        }

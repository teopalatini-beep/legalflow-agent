from __future__ import annotations

import hashlib
import json
import os
from urllib import error, request
from urllib.parse import quote
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


class EmailInboxConnector:
    """Conector de inbox para Gmail/Outlook con fallback en simulacion."""

    providers = {"gmail", "outlook"}

    def _provider_config(self, provider: str) -> Dict[str, str]:
        provider = provider.strip().lower()
        if provider == "gmail":
            return {
                "access_token": os.getenv("LEGALFLOW_GMAIL_ACCESS_TOKEN", "").strip(),
                "api_base_url": "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            }
        if provider == "outlook":
            return {
                "access_token": os.getenv("LEGALFLOW_OUTLOOK_ACCESS_TOKEN", "").strip(),
                "api_base_url": "https://graph.microsoft.com/v1.0/me/messages",
            }
        return {"access_token": "", "api_base_url": ""}

    def integration_health(self) -> Dict[str, Any]:
        return {
            "gmail_token_set": bool(os.getenv("LEGALFLOW_GMAIL_ACCESS_TOKEN", "").strip()),
            "outlook_token_set": bool(os.getenv("LEGALFLOW_OUTLOOK_ACCESS_TOKEN", "").strip()),
        }

    def connect(self, provider: str, user_email: str) -> Dict[str, Any]:
        clean_provider = provider.strip().lower()
        if clean_provider not in self.providers:
            raise ValueError("Proveedor invalido. Usa gmail u outlook.")
        cfg = self._provider_config(clean_provider)
        mode = "real" if cfg["access_token"] else "simulation"
        connection_id = (
            f"inbox_{clean_provider}_"
            f"{hashlib.md5(f'{user_email}:{clean_provider}'.encode()).hexdigest()[:12]}"
        )
        _append_event(
            "inbox_connect",
            {
                "provider": clean_provider,
                "mode": mode,
                "user_email": user_email,
                "connection_id": connection_id,
                "status": "connected",
            },
        )
        return {
            "provider": clean_provider,
            "mode": mode,
            "connection_id": connection_id,
            "status": "connected",
        }

    def _gmail_search(self, query: str, access_token: str) -> list[Dict[str, Any]]:
        encoded_q = quote(query)
        url = (
            f"{self._provider_config('gmail')['api_base_url']}?q={encoded_q}"
            "&maxResults=5&fields=messages(id,threadId)"
        )
        req = request.Request(
            url,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items = payload.get("messages", []) or []
        return [
            {
                "id": item.get("id", ""),
                "thread_id": item.get("threadId", ""),
                "subject": "Email encontrado en Gmail (metadata parcial)",
                "has_contract_attachment_hint": True,
            }
            for item in items
        ]

    def _outlook_search(self, query: str, access_token: str) -> list[Dict[str, Any]]:
        # Contiene por simplicidad: filtro aproximado por subject/body preview.
        safe_query = query.replace("'", "''")
        encoded_filter = quote(
            f"contains(subject,'{safe_query}') or contains(bodyPreview,'{safe_query}')"
        )
        url = (
            f"{self._provider_config('outlook')['api_base_url']}"
            f"?$top=5&$select=id,subject,hasAttachments,receivedDateTime"
            f"&$filter={encoded_filter}"
        )
        req = request.Request(
            url,
            method="GET",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        items = payload.get("value", []) or []
        return [
            {
                "id": item.get("id", ""),
                "thread_id": "",
                "subject": item.get("subject", "Sin asunto"),
                "has_contract_attachment_hint": bool(item.get("hasAttachments")),
                "received_at": item.get("receivedDateTime"),
            }
            for item in items
        ]

    def _simulation_search(self, provider: str, query: str) -> list[Dict[str, Any]]:
        label = "Gmail" if provider == "gmail" else "Outlook"
        base_results = [
            f"{label} · Acme -> MSA v3 - contrato_servicios_v3.docx",
            f"{label} · VendorX -> NDA mutuo - nda_vendorx.pdf",
            f"{label} · Cliente Norte -> Contrato marco - contrato_marco_2026.pdf",
        ]
        normalized = query.strip().lower()
        filtered = [x for x in base_results if not normalized or normalized in x.lower()]
        return [
            {
                "id": f"sim_{provider}_{idx}",
                "thread_id": f"sim_thread_{idx}",
                "subject": item,
                "has_contract_attachment_hint": True,
            }
            for idx, item in enumerate(filtered[:5], start=1)
        ]

    def search(self, provider: str, query: str) -> Dict[str, Any]:
        clean_provider = provider.strip().lower()
        if clean_provider not in self.providers:
            raise ValueError("Proveedor invalido. Usa gmail u outlook.")
        cfg = self._provider_config(clean_provider)
        mode = "real" if cfg["access_token"] else "simulation"
        items: list[Dict[str, Any]]
        if mode == "real":
            try:
                if clean_provider == "gmail":
                    items = self._gmail_search(query, cfg["access_token"])
                else:
                    items = self._outlook_search(query, cfg["access_token"])
            except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                mode = "simulation"
                items = self._simulation_search(clean_provider, query)
        else:
            items = self._simulation_search(clean_provider, query)
        _append_event(
            "inbox_search",
            {
                "provider": clean_provider,
                "mode": mode,
                "query": query,
                "results_count": len(items),
            },
        )
        return {
            "provider": clean_provider,
            "mode": mode,
            "query": query,
            "results": items,
            "total": len(items),
        }

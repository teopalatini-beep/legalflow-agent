from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portal_web import app


def assert_true(name: str, condition: bool) -> None:
    if not condition:
        raise AssertionError(f"FAILED: {name}")
    print(f"OK: {name}")


def run() -> None:
    os.environ["LEGALFLOW_SSO_TOKEN"] = "test-token"
    admin_headers = {
        "Authorization": "Bearer test-token",
        "X-SSO-User": "teo",
        "X-SSO-Email": "teo@example.com",
        "X-SSO-Groups": "legal_admin,legal_ops",
    }
    viewer_headers = {
        "Authorization": "Bearer test-token",
        "X-SSO-User": "viewer",
        "X-SSO-Email": "viewer@example.com",
        "X-SSO-Groups": "legal_viewer",
    }

    with app.test_client() as c:
        health = c.get("/api/health")
        assert_true("health endpoint", health.status_code == 200 and health.get_json().get("ok"))

        create = c.post(
            "/api/matters",
            json={
                "cliente_id": "default",
                "title": "Smoke Matter",
                "obligations": [{"title": "Entregar release", "due_date": "2026-07-10"}],
            },
            headers=admin_headers,
        )
        create_data = create.get_json()
        assert_true("matter create", create.status_code == 200 and create_data.get("ok"))
        matter_id = create_data["matter"]["matter_id"]

        invalid = c.post("/api/matters", json={"matter_id": "bad!"}, headers=admin_headers)
        assert_true("matter validation", invalid.status_code == 400)

        approve_forbidden = c.post(
            f"/api/matters/{matter_id}/approve", json={"notes": "x"}, headers=viewer_headers
        )
        assert_true("role authorization", approve_forbidden.status_code == 403)

        req_apr = c.post(
            f"/api/matters/{matter_id}/approvals/request",
            json={"reviewers": ["legal.lead@acme.com"], "note": "review required"},
            headers=admin_headers,
        )
        req_apr_data = req_apr.get_json()
        assert_true("approval request", req_apr.status_code == 200 and req_apr_data.get("ok"))
        approval_id = req_apr_data["approvals"]["created"][0]["approval_id"]

        decision = c.post(
            f"/api/matters/{matter_id}/approvals/{approval_id}/decision",
            json={"decision": "approved", "note": "ok"},
            headers={**admin_headers, "X-SSO-Groups": "legal_admin,approver"},
        )
        assert_true("approval decision", decision.status_code == 200 and decision.get_json().get("ok"))

        doc_version = c.post(
            f"/api/matters/{matter_id}/documents/versions",
            json={
                "filename": "msa_v1.txt",
                "content": "Version uno del contrato",
                "source": "upload",
                "metadata": {"tag": "v1"},
            },
            headers=admin_headers,
        )
        assert_true("document version add", doc_version.status_code == 200 and doc_version.get_json().get("ok"))

        list_versions = c.get(
            f"/api/matters/{matter_id}/documents/versions", headers=viewer_headers
        )
        lv_data = list_versions.get_json()
        assert_true(
            "document versions list",
            list_versions.status_code == 200 and lv_data.get("ok") and len(lv_data.get("versions", [])) >= 1,
        )

        approve = c.post(
            f"/api/matters/{matter_id}/approve",
            json={"notes": "approved"},
            headers={**admin_headers, "X-SSO-Groups": "legal_admin,approver"},
        )
        assert_true("matter approve", approve.status_code == 200 and approve.get_json().get("ok"))

        obligations = c.get(f"/api/matters/{matter_id}/obligations", headers=viewer_headers)
        assert_true("matter obligations", obligations.status_code == 200 and obligations.get_json().get("ok"))

        timeline = c.get(f"/api/matters/{matter_id}/timeline", headers=viewer_headers)
        t_data = timeline.get_json()
        assert_true("matter timeline", timeline.status_code == 200 and t_data.get("ok"))

        crm = c.post("/api/integrations/crm/sync", json={"matter_id": matter_id}, headers=admin_headers)
        assert_true("crm sync", crm.status_code == 200 and crm.get_json().get("ok"))

        dms = c.post(
            "/api/integrations/dms/upload",
            json={
                "matter_id": matter_id,
                "filename": "msa.txt",
                "content": "Contrato demo",
                "metadata": {"version": "v1"},
            },
            headers=admin_headers,
        )
        assert_true("dms upload", dms.status_code == 200 and dms.get_json().get("ok"))

        esign = c.post(
            "/api/integrations/esign/request",
            json={"matter_id": matter_id, "signer_email": "legal@acme.com"},
            headers=admin_headers,
        )
        esign_data = esign.get_json()
        assert_true("esign request", esign.status_code == 200 and esign_data.get("ok"))
        envelope_id = esign_data["integration"].get("envelope_id")
        recipient_id = esign_data["integration"].get("recipient_id")
        assert_true("esign request ids", bool(envelope_id) and bool(recipient_id))

        create_envelope = c.post(
            "/api/integrations/esign/create-envelope",
            json={
                "matter_id": matter_id,
                "signer_email": "legal+2@acme.com",
                "document_ref": "doc_v2",
            },
            headers=admin_headers,
        )
        envelope_data = create_envelope.get_json()
        assert_true(
            "esign create envelope",
            create_envelope.status_code == 200 and envelope_data.get("ok"),
        )
        assert_true(
            "esign envelope ids",
            bool(envelope_data["integration"].get("envelope_id"))
            and bool(envelope_data["integration"].get("recipient_id")),
        )

        recipient_view = c.post(
            "/api/integrations/esign/recipient-view",
            json={"matter_id": matter_id},
            headers=admin_headers,
        )
        rv_data = recipient_view.get_json()
        assert_true(
            "esign recipient view",
            recipient_view.status_code == 200
            and rv_data.get("ok")
            and bool(rv_data["integration"].get("signing_url")),
        )

        webhook = c.post(
            "/api/integrations/esign/webhook",
            json={
                "event_id": "evt_smoke_signed_001",
                "matter_id": matter_id,
                "envelope_id": envelope_data["integration"]["envelope_id"],
                "recipient_id": envelope_data["integration"]["recipient_id"],
                "status": "completed",
            },
        )
        wh_data = webhook.get_json()
        assert_true(
            "esign webhook signed",
            webhook.status_code == 200
            and wh_data.get("ok")
            and wh_data.get("status") == "signed"
            and wh_data.get("duplicate") is False,
        )

        webhook_dup = c.post(
            "/api/integrations/esign/webhook",
            json={
                "event_id": "evt_smoke_signed_001",
                "matter_id": matter_id,
                "envelope_id": envelope_data["integration"]["envelope_id"],
                "status": "completed",
            },
        )
        dup_data = webhook_dup.get_json()
        assert_true(
            "esign webhook idempotent",
            webhook_dup.status_code == 200 and dup_data.get("ok") and dup_data.get("duplicate") is True,
        )

        timeline_after_webhook = c.get(f"/api/matters/{matter_id}/timeline", headers=viewer_headers)
        tah_data = timeline_after_webhook.get_json()
        webhook_events = [e for e in tah_data.get("events", []) if e.get("type") == "esign_webhook_received"]
        assert_true(
            "esign webhook timeline state",
            timeline_after_webhook.status_code == 200
            and tah_data.get("status") == "signed"
            and len(webhook_events) == 1,
        )


if __name__ == "__main__":
    run()

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

        approve = c.post(
            f"/api/matters/{matter_id}/approve",
            json={"notes": "approved"},
            headers={**admin_headers, "X-SSO-Groups": "legal_admin,approver"},
        )
        assert_true("matter approve", approve.status_code == 200 and approve.get_json().get("ok"))

        obligations = c.get(f"/api/matters/{matter_id}/obligations", headers=viewer_headers)
        assert_true("matter obligations", obligations.status_code == 200 and obligations.get_json().get("ok"))

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
        assert_true("esign request", esign.status_code == 200 and esign.get_json().get("ok"))


if __name__ == "__main__":
    run()

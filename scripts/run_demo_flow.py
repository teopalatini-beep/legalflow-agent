from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from portal_web import app


def main() -> None:
    demo_file = ROOT / "data" / "demo" / "demo_flow.json"
    demo = json.loads(demo_file.read_text(encoding="utf-8"))

    os.environ.setdefault("LEGALFLOW_SSO_TOKEN", "demo-token")
    headers = {
        "Authorization": "Bearer demo-token",
        "X-SSO-User": "demo-user",
        "X-SSO-Email": "demo@legalflow.test",
        "X-SSO-Groups": "legal_admin,legal_ops,approver",
    }

    with app.test_client() as c:
        analyze = c.post(
            "/api/analizar",
            data={
                "modo": demo["modo"],
                "modelo": demo["modelo"],
                "cliente_id": demo["cliente_id"],
                "modo_analisis": demo["modo_analisis"],
                "contrato": demo["contract_a"],
                "contrato_b": demo["contract_b"],
                "compare": "true",
            },
        )
        a_data = analyze.get_json()
        if not a_data.get("ok"):
            raise RuntimeError(f"Analisis demo fallo: {a_data}")
        print("OK: analisis + comparacion")

        save_case = c.post(
            "/api/casos",
            json={
                "titulo": demo["matter_title"],
                "cliente_id": demo["cliente_id"],
                "contrato": demo["contract_a"],
                "resultado": a_data["resultado"],
            },
        )
        s_data = save_case.get_json()
        if not s_data.get("ok"):
            raise RuntimeError(f"Guardar caso fallo: {s_data}")
        print("OK: caso guardado", s_data["case_id"])

        create_matter = c.post(
            "/api/matters",
            json={
                "cliente_id": demo["cliente_id"],
                "case_id": s_data["case_id"],
                "title": demo["matter_title"],
                "analysis_result": a_data["resultado"],
                "obligations": demo["obligations"],
            },
            headers=headers,
        )
        m_data = create_matter.get_json()
        if not m_data.get("ok"):
            raise RuntimeError(f"Crear matter fallo: {m_data}")
        matter_id = m_data["matter"]["matter_id"]
        print("OK: matter creado", matter_id)

        request_approval = c.post(
            f"/api/matters/{matter_id}/approvals/request",
            json={"reviewers": ["legal.lead@acme.com"], "note": "demo review"},
            headers=headers,
        )
        r_data = request_approval.get_json()
        if not r_data.get("ok"):
            raise RuntimeError(f"Solicitud de aprobacion fallo: {r_data}")
        approval_id = r_data["approvals"]["created"][0]["approval_id"]
        print("OK: approval workflow iniciado", approval_id)

        approval_decision = c.post(
            f"/api/matters/{matter_id}/approvals/{approval_id}/decision",
            json={"decision": "approved", "note": "approved in demo"},
            headers=headers,
        )
        if not approval_decision.get_json().get("ok"):
            raise RuntimeError(f"Decision de aprobacion fallo: {approval_decision.get_json()}")
        print("OK: approval decision registrada")

        version = c.post(
            f"/api/matters/{matter_id}/documents/versions",
            json={
                "filename": "msa_v1.txt",
                "content": demo["contract_a"],
                "source": "demo_flow",
                "metadata": {"label": "version_a"},
            },
            headers=headers,
        )
        v_data = version.get_json()
        if not v_data.get("ok"):
            raise RuntimeError(f"Versionado documental fallo: {v_data}")
        print("OK: version documental creada", v_data["version"]["version_id"])

        approve = c.post(
            f"/api/matters/{matter_id}/approve",
            json={"notes": "approved in demo"},
            headers=headers,
        )
        if not approve.get_json().get("ok"):
            raise RuntimeError(f"Aprobar matter fallo: {approve.get_json()}")
        print("OK: matter aprobado")

        dispatch = c.post(
            "/api/routing/dispatch",
            json={
                "matter_id": matter_id,
                "approved_by": "demo@legalflow.test",
                "analysis_reviewed": {
                    "contract_type": "servicios",
                    "risk_level": "medio",
                    "key_clauses": ["confidencialidad"],
                    "summary": "aprobado para despacho",
                    "recommended_action": "seguir flujo de firma",
                    "quality_score": 90,
                    "reviewer_comment": "Aprobado para continuar.",
                    "risk_items": [],
                },
                "routing": {"suggested_destination": "legal_ops"},
            },
            headers=headers,
        )
        d_data = dispatch.get_json()
        if not d_data.get("ok"):
            raise RuntimeError(f"Routing dispatch fallo: {d_data}")
        print("OK: routing dispatch", d_data["dispatch"]["destination"])

        queue = c.get("/api/routing/queue")
        q_data = queue.get_json()
        if not q_data.get("ok"):
            raise RuntimeError(f"Routing queue fallo: {q_data}")
        print("OK: routing queue", q_data["counts"])

        create_envelope = c.post(
            "/api/integrations/esign/create-envelope",
            json={"matter_id": matter_id, "signer_email": "legal@acme.com"},
            headers=headers,
        )
        env_data = create_envelope.get_json()
        if not env_data.get("ok"):
            raise RuntimeError(f"E-sign create-envelope fallo: {env_data}")
        mode = env_data["integration"].get("mode", "simulation")
        print("OK: e-sign envelope creado en modo", mode)

        recipient_view = c.post(
            "/api/integrations/esign/recipient-view",
            json={"matter_id": matter_id},
            headers=headers,
        )
        rv_data = recipient_view.get_json()
        if not rv_data.get("ok"):
            raise RuntimeError(f"E-sign recipient-view fallo: {rv_data}")
        print("OK: recipient-view listo")

        webhook = c.post(
            "/api/integrations/esign/webhook",
            json={
                "event_id": "evt_demo_signed_001",
                "matter_id": matter_id,
                "envelope_id": env_data["integration"]["envelope_id"],
                "recipient_id": env_data["integration"]["recipient_id"],
                "status": "completed",
            },
        )
        wh_data = webhook.get_json()
        if not wh_data.get("ok") or wh_data.get("status") != "signed":
            raise RuntimeError(f"E-sign webhook fallo: {wh_data}")
        print("OK: webhook procesado (signed)")

        timeline = c.get(f"/api/matters/{matter_id}/timeline", headers=headers)
        tl_data = timeline.get_json()
        if not tl_data.get("ok"):
            raise RuntimeError(f"Timeline fallo: {tl_data}")
        if tl_data.get("status") != "signed":
            raise RuntimeError(f"Estado final inesperado: {tl_data.get('status')}")
        print("OK: timeline consultada con", len(tl_data.get("events", [])), "eventos")

        print("\nDemo flow completo.")


if __name__ == "__main__":
    main()

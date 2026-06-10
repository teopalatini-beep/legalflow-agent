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

        approve = c.post(
            f"/api/matters/{matter_id}/approve",
            json={"notes": "approved in demo"},
            headers=headers,
        )
        if not approve.get_json().get("ok"):
            raise RuntimeError(f"Aprobar matter fallo: {approve.get_json()}")
        print("OK: matter aprobado")

        esign = c.post(
            "/api/integrations/esign/request",
            json={"matter_id": matter_id, "signer_email": "legal@acme.com"},
            headers=headers,
        )
        e_data = esign.get_json()
        if not e_data.get("ok"):
            raise RuntimeError(f"E-sign request fallo: {e_data}")
        mode = e_data["integration"].get("mode", "simulation")
        print("OK: e-sign solicitado en modo", mode)

        print("\nDemo flow completo.")


if __name__ == "__main__":
    main()

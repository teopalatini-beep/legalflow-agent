from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

from agente import ErrorWorkflow, ejecutar_workflow
from enterprise_integrations import CRMConnector, DMSConnector, ESignatureConnector
from matters_store import (
    add_document_version,
    append_event,
    create_matter,
    decision_approval,
    get_matter,
    request_approvals,
    update_status,
)
from observability import CASES_DIR, audit_log, ensure_data_dirs, metric_log, redact_sensitive, retention_cleanup
from sso_auth import require_sso, sso_context

app = Flask(__name__)
crm_connector = CRMConnector()
dms_connector = DMSConnector()
esign_connector = ESignatureConnector()
MATTER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{6,80}$")


def limpiar_texto_subido(texto: str) -> str:
    return texto.strip()


def error_response(message: str, status: int = 400, code: str = "bad_request") -> Any:
    return jsonify({"ok": False, "error": message, "code": code}), status


def json_payload() -> Dict[str, Any]:
    return request.get_json(force=True, silent=True) or {}


def validar_matter_id(matter_id: str) -> bool:
    return bool(MATTER_ID_PATTERN.match(matter_id))


@app.get("/")
def home() -> str:
    return render_template("portal.html")


def _save_case(payload: Dict[str, Any]) -> str:
    ensure_data_dirs()
    case_id = payload.get("case_id") or f"case_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    target = CASES_DIR / f"{case_id}.json"
    target.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return case_id


def _compare_results(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    risk_a = len(a.get("riesgos_detectados", []))
    risk_b = len(b.get("riesgos_detectados", []))
    return {
        "riesgos_version_a": risk_a,
        "riesgos_version_b": risk_b,
        "delta_riesgos": risk_b - risk_a,
        "quality_a": a.get("quality_score", 0),
        "quality_b": b.get("quality_score", 0),
    }


@app.get("/api/health")
def health() -> Any:
    ensure_data_dirs()
    return jsonify(
        {
            "ok": True,
            "service": "legalflow-agent",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.get("/api/health/config")
def health_config() -> Any:
    return jsonify(
        {
            "ok": True,
            "config": {
                "cursor_api_key_set": bool(os.getenv("CURSOR_API_KEY")),
                "sso_token_set": bool(os.getenv("LEGALFLOW_SSO_TOKEN")),
                "esign_endpoint_set": bool(os.getenv("LEGALFLOW_ESIGN_ENDPOINT")),
                "esign_api_key_set": bool(os.getenv("LEGALFLOW_ESIGN_API_KEY")),
            },
        }
    )


@app.post("/api/analizar")
def analizar_contrato() -> Any:
    ensure_data_dirs()
    retention_cleanup(retention_days=30)

    contrato_texto = request.form.get("contrato", "")
    contrato_b = request.form.get("contrato_b", "")
    modo = request.form.get("modo", "local")
    modelo = request.form.get("modelo", "composer-2.5")
    cliente_id = request.form.get("cliente_id", "default")
    modo_analisis = request.form.get("modo_analisis", "general")
    compare = request.form.get("compare", "false").lower() == "true"

    archivo = request.files.get("archivo")
    if archivo and archivo.filename:
        contenido = archivo.read()
        try:
            contrato_texto = contenido.decode("utf-8")
        except UnicodeDecodeError:
            try:
                contrato_texto = contenido.decode("latin-1")
            except UnicodeDecodeError:
                return error_response(
                    "No pude leer el archivo. Usa .txt UTF-8 o pega el texto del contrato.",
                    status=400,
                    code="invalid_file_encoding",
                )

    contrato_texto = limpiar_texto_subido(contrato_texto)
    contrato_b = limpiar_texto_subido(contrato_b)
    if not contrato_texto:
        return error_response(
            "Debes pegar o subir un contrato.", status=400, code="missing_contract"
        )

    if modo not in {"local", "sdk"}:
        return error_response("Modo invalido.", status=400, code="invalid_mode")

    start = datetime.now(timezone.utc)
    try:
        resultado_a: Dict[str, Any] = ejecutar_workflow(
            contrato_texto,
            modo,
            modelo,
            verbose=False,
            cliente_id=cliente_id,
            modo_analisis=modo_analisis,
        )
        response: Dict[str, Any] = {"ok": True, "resultado": resultado_a}
        if compare and contrato_b:
            resultado_b: Dict[str, Any] = ejecutar_workflow(
                contrato_b,
                modo,
                modelo,
                verbose=False,
                cliente_id=cliente_id,
                modo_analisis=modo_analisis,
            )
            response["comparacion"] = _compare_results(resultado_a, resultado_b)
            response["resultado_b"] = resultado_b
    except ErrorWorkflow as err:
        audit_log("analysis_error", {"cliente_id": cliente_id, "error": str(err)})
        return error_response(str(err), status=400, code="workflow_error")
    except Exception as err:  # pragma: no cover
        audit_log("analysis_exception", {"cliente_id": cliente_id, "error": str(err)})
        return error_response(
            f"Error inesperado: {err}", status=500, code="internal_exception"
        )

    duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    metric_log(
        "workflow_duration_ms",
        duration_ms,
        {"modo": modo, "cliente_id": cliente_id, "compare": compare},
    )
    audit_log(
        "analysis_completed",
        {"cliente_id": cliente_id, "modo": modo, "duration_ms": duration_ms},
    )
    return jsonify(response)


@app.post("/api/casos")
def crear_caso() -> Any:
    payload = json_payload()
    titulo = payload.get("titulo", "").strip()
    if not titulo:
        return error_response("El caso requiere un titulo.", 400, "missing_title")

    contrato = redact_sensitive(payload.get("contrato", ""))
    resultado = payload.get("resultado", {})
    case_payload = {
        "titulo": titulo,
        "cliente_id": payload.get("cliente_id", "default"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contrato": contrato,
        "resultado": resultado,
    }
    case_id = _save_case(case_payload)
    audit_log("case_saved", {"case_id": case_id, "titulo": titulo})
    return jsonify({"ok": True, "case_id": case_id})


@app.get("/api/casos")
def listar_casos() -> Any:
    ensure_data_dirs()
    items = []
    for case_path in sorted(CASES_DIR.glob("*.json"), reverse=True):
        data = json.loads(case_path.read_text(encoding="utf-8"))
        items.append(
            {
                "case_id": case_path.stem,
                "titulo": data.get("titulo", "Sin titulo"),
                "cliente_id": data.get("cliente_id", "default"),
                "created_at": data.get("created_at"),
            }
        )
    return jsonify({"ok": True, "casos": items[:50]})


@app.get("/api/casos/<case_id>")
def obtener_caso(case_id: str) -> Any:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        return error_response("Caso no encontrado.", 404, "case_not_found")
    data = json.loads(path.read_text(encoding="utf-8"))
    return jsonify({"ok": True, "caso": data})


@app.post("/api/matters")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def crear_matter() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id") or f"matter_{uuid4().hex[:12]}"
    if not validar_matter_id(matter_id):
        return error_response(
            "matter_id invalido (usa 6-80 caracteres alfanumericos, _ o -).",
            400,
            "invalid_matter_id",
        )
    base = {
        "cliente_id": payload.get("cliente_id", "default"),
        "case_id": payload.get("case_id"),
        "title": payload.get("title", "Untitled Matter"),
        "analysis_result": payload.get("analysis_result", {}),
        "obligations": payload.get("obligations", []),
    }
    if not isinstance(base["obligations"], list):
        return error_response(
            "obligations debe ser una lista.", 400, "invalid_obligations"
        )
    matter = create_matter(matter_id, base)
    append_event(matter_id, "matter_created", {"by": sso_context(request)["email"]})
    audit_log("matter_created", {"matter_id": matter_id, "by": sso_context(request)["email"]})
    return jsonify({"ok": True, "matter": matter})


@app.post("/api/matters/<matter_id>/approve")
@require_sso(required_groups=["legal_admin", "approver"])
def aprobar_matter(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    payload = json_payload()
    update_status(matter_id, "approved")
    updated = append_event(
        matter_id,
        "approved",
        {"by": sso_context(request)["email"], "notes": payload.get("notes", "")},
    )
    audit_log("matter_approved", {"matter_id": matter_id, "by": sso_context(request)["email"]})
    return jsonify({"ok": True, "matter": updated})


@app.post("/api/matters/<matter_id>/approvals/request")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def solicitar_aprobaciones(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    payload = json_payload()
    reviewers = payload.get("reviewers", [])
    if not isinstance(reviewers, list) or not reviewers:
        return error_response(
            "reviewers debe ser una lista no vacia.", 400, "invalid_reviewers"
        )
    if not get_matter(matter_id):
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    created = request_approvals(
        matter_id,
        reviewers=[str(x).strip() for x in reviewers if str(x).strip()],
        requested_by=sso_context(request)["email"],
        note=payload.get("note", ""),
    )
    append_event(
        matter_id,
        "approvals_requested",
        {"by": sso_context(request)["email"], "reviewers": reviewers},
    )
    return jsonify({"ok": True, "approvals": created})


@app.post("/api/matters/<matter_id>/approvals/<approval_id>/decision")
@require_sso(required_groups=["legal_admin", "approver"])
def decidir_aprobacion(matter_id: str, approval_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    payload = json_payload()
    decision = str(payload.get("decision", "")).strip().lower()
    if decision not in {"approved", "rejected"}:
        return error_response(
            "decision debe ser approved o rejected.", 400, "invalid_decision"
        )
    if not get_matter(matter_id):
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    try:
        updated = decision_approval(
            matter_id,
            approval_id,
            decision=decision,
            decided_by=sso_context(request)["email"],
            note=payload.get("note", ""),
        )
    except KeyError:
        return error_response("Approval no encontrado.", 404, "approval_not_found")
    except ValueError as err:
        return error_response(str(err), 400, "invalid_decision")
    append_event(
        matter_id,
        "approval_decision",
        {"by": sso_context(request)["email"], "approval_id": approval_id, "decision": decision},
    )
    return jsonify({"ok": True, "approval": updated})


@app.post("/api/matters/<matter_id>/sign")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def firmar_matter(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    payload = json_payload()
    signer_email = payload.get("signer_email")
    if not signer_email:
        return error_response("Falta signer_email.", 400, "missing_signer_email")
    document_ref = payload.get("document_ref", matter_id)
    esign_result = esign_connector.request_signature(matter_id, signer_email, document_ref)
    update_status(matter_id, "signature_pending")
    updated = append_event(
        matter_id,
        "signature_requested",
        {"by": sso_context(request)["email"], **esign_result},
    )
    audit_log("matter_signature_requested", {"matter_id": matter_id, "by": sso_context(request)["email"]})
    return jsonify({"ok": True, "matter": updated, "esign": esign_result})


@app.post("/api/matters/<matter_id>/documents/versions")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def registrar_version_documento(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    payload = json_payload()
    filename = str(payload.get("filename", "")).strip()
    content = str(payload.get("content", "")).strip()
    if not filename or not content:
        return error_response("Faltan filename o content.", 400, "missing_fields")
    if not get_matter(matter_id):
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    doc_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    version = add_document_version(
        matter_id,
        filename=filename,
        doc_hash=doc_hash,
        source=payload.get("source", "manual"),
        metadata=payload.get("metadata", {}),
        created_by=sso_context(request)["email"],
    )
    append_event(
        matter_id,
        "document_version_added",
        {"by": sso_context(request)["email"], "version_id": version["version_id"]},
    )
    return jsonify({"ok": True, "version": version})


@app.get("/api/matters/<matter_id>/documents/versions")
@require_sso(required_groups=["legal_admin", "legal_ops", "legal_viewer"])
def listar_versiones_documento(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    return jsonify(
        {"ok": True, "matter_id": matter_id, "versions": matter.get("document_versions", [])}
    )


@app.get("/api/matters/<matter_id>/obligations")
@require_sso(required_groups=["legal_admin", "legal_ops", "legal_viewer"])
def obligaciones_matter(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    obligations = matter.get("obligations", [])
    return jsonify({"ok": True, "matter_id": matter_id, "obligations": obligations})


@app.get("/api/matters/<matter_id>/timeline")
@require_sso(required_groups=["legal_admin", "legal_ops", "legal_viewer"])
def matter_timeline(matter_id: str) -> Any:
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    return jsonify(
        {
            "ok": True,
            "matter_id": matter_id,
            "status": matter.get("status"),
            "events": matter.get("events", []),
            "approvals": matter.get("approvals", []),
            "document_versions": matter.get("document_versions", []),
        }
    )


@app.post("/api/integrations/crm/sync")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def sync_crm() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id")
    if not matter_id:
        return error_response("Falta matter_id.", 400, "missing_matter_id")
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    result = crm_connector.sync_matter(matter_id, payload.get("crm_payload", matter))
    append_event(matter_id, "crm_synced", {"by": sso_context(request)["email"], **result})
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/dms/upload")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def upload_dms() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id")
    filename = payload.get("filename", "contract.txt")
    content = payload.get("content", "")
    if not matter_id or not content:
        return error_response("Faltan matter_id o content.", 400, "missing_fields")
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    result = dms_connector.upload_document(
        matter_id,
        filename=filename,
        content=content,
        metadata=payload.get("metadata", {}),
    )
    append_event(matter_id, "dms_uploaded", {"by": sso_context(request)["email"], **result})
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/esign/request")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def request_esign() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id")
    signer_email = payload.get("signer_email")
    document_ref = payload.get("document_ref", matter_id)
    if not matter_id or not signer_email:
        return error_response(
            "Faltan matter_id o signer_email.", 400, "missing_fields"
        )
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    result = esign_connector.request_signature(matter_id, signer_email, document_ref)
    append_event(matter_id, "esign_requested", {"by": sso_context(request)["email"], **result})
    return jsonify({"ok": True, "integration": result})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)

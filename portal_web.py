from __future__ import annotations

import json
import os
import re
import hashlib
import hmac
from io import BytesIO
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

from agente import ErrorWorkflow, ejecutar_workflow
from enterprise_integrations import (
    CRMConnector,
    DMSConnector,
    ESignatureConnector,
    EmailInboxConnector,
)
from matters_store import (
    add_document_version,
    append_event,
    create_matter,
    decision_approval,
    find_matter_by_envelope_id,
    get_matter,
    has_esign_webhook_event_id,
    list_matters,
    register_esign_webhook_event_id,
    request_approvals,
    save_hitl_dispatch,
    update_esign_tracking,
    update_status,
)
from observability import CASES_DIR, audit_log, ensure_data_dirs, metric_log, redact_sensitive, retention_cleanup
from sso_auth import require_sso, sso_context

app = Flask(__name__)
crm_connector = CRMConnector()
dms_connector = DMSConnector()
esign_connector = ESignatureConnector()
inbox_connector = EmailInboxConnector()
MATTER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{6,80}$")


def limpiar_texto_subido(texto: str) -> str:
    return texto.strip()


def error_response(message: str, status: int = 400, code: str = "bad_request") -> Any:
    return jsonify({"ok": False, "error": message, "code": code}), status


def json_payload() -> Dict[str, Any]:
    return request.get_json(force=True, silent=True) or {}


def _extract_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.remote_addr or "unknown"


def _is_production_like() -> bool:
    value = os.getenv("LEGALFLOW_ENV", "").strip().lower()
    return value in {"prod", "production", "staging"}


def validar_matter_id(matter_id: str) -> bool:
    return bool(MATTER_ID_PATTERN.match(matter_id))


def _extract_txt_content(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _extract_pdf_content(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as err:  # pragma: no cover
        raise ErrorWorkflow(
            "Falta dependencia 'pypdf'. Instala requirements.txt para procesar PDF."
        ) from err
    reader = PdfReader(BytesIO(content))
    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_docx_content(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as err:  # pragma: no cover
        raise ErrorWorkflow(
            "Falta dependencia 'python-docx'. Instala requirements.txt para procesar DOCX."
        ) from err
    doc = Document(BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_contract_text_from_upload(filename: str, content: bytes) -> str:
    lower = filename.lower().strip()
    if lower.endswith(".pdf"):
        return _extract_pdf_content(content)
    if lower.endswith(".docx"):
        return _extract_docx_content(content)
    if lower.endswith(".txt"):
        return _extract_txt_content(content)
    raise ErrorWorkflow(
        "Formato no soportado. Sube PDF, DOCX o TXT."
    )


def _extract_parties(contract_text: str) -> List[str]:
    lines = [x.strip() for x in contract_text.splitlines() if x.strip()]
    if not lines:
        return []
    text = " ".join(lines[:8])
    patterns = [
        r"entre\s+(.+?)\s+y\s+(.+?)(?:\.|,|;|\n)",
        r"between\s+(.+?)\s+and\s+(.+?)(?:\.|,|;|\n)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            left = re.sub(r"\s+", " ", match.group(1)).strip(" :")
            right = re.sub(r"\s+", " ", match.group(2)).strip(" :")
            parties = [left, right]
            return [p for p in parties if p]
    return []


def _risk_level_from_items(risks: List[Dict[str, Any]]) -> str:
    rank = {"bajo": 1, "low": 1, "medio": 2, "medium": 2, "alto": 3, "high": 3}
    max_rank = 0
    max_label = "bajo"
    for item in risks:
        label = str(item.get("nivel", "")).strip().lower()
        level = rank.get(label, 1)
        if level > max_rank:
            max_rank = level
            max_label = label or "bajo"
    return max_label


def _compact_analysis_response(result: Dict[str, Any], contract_text: str) -> Dict[str, Any]:
    risks = result.get("riesgos_detectados", []) or []
    return {
        "run_id": result.get("run_id"),
        "contract_type": result.get("tipo_contrato_probable", "desconocido"),
        "parties_involved": _extract_parties(contract_text),
        "risk_level": _risk_level_from_items(risks),
        "key_clauses": result.get("clausulas_detectadas", []) or [],
        "risk_items": risks,
        "summary": result.get("resumen_final", ""),
        "recommended_action": result.get("accion_recomendada", ""),
        "quality_score": result.get("quality_score", 0),
    }


def _routing_destination_from_risk(
    suggested_destination: str, analysis_reviewed: Dict[str, Any]
) -> str:
    clean = str(suggested_destination or "").strip()
    if clean:
        return clean
    risk_level = str(analysis_reviewed.get("risk_level", "")).strip().lower()
    if risk_level in {"alto", "high"}:
        return "senior_reviewer"
    if risk_level in {"medio", "medium"}:
        return "legal_ops"
    return "client_renegotiation"


def _matter_queue_item(matter: Dict[str, Any]) -> Dict[str, Any]:
    analysis = matter.get("analysis_result", {})
    hitl = matter.get("hitl", {})
    reviewed = hitl.get("analysis_reviewed", {}) if isinstance(hitl, dict) else {}
    risk_level = (
        reviewed.get("risk_level")
        or analysis.get("risk_level")
        or analysis.get("nivel_riesgo")
        or "unknown"
    )
    contract_type = (
        reviewed.get("contract_type")
        or analysis.get("contract_type")
        or analysis.get("tipo_contrato_probable")
        or "desconocido"
    )
    routing = matter.get("routing", {}) if isinstance(matter.get("routing", {}), dict) else {}
    return {
        "matter_id": matter.get("matter_id"),
        "title": matter.get("title", "Untitled Matter"),
        "cliente_id": matter.get("cliente_id", "default"),
        "status": matter.get("status", "draft"),
        "contract_type": contract_type,
        "risk_level": str(risk_level),
        "destination": routing.get("destination"),
        "routing_status": routing.get("status"),
        "updated_at": matter.get("updated_at"),
        "created_at": matter.get("created_at"),
    }


def _is_dispatched_matter(matter: Dict[str, Any]) -> bool:
    routing = matter.get("routing", {})
    if isinstance(routing, dict) and routing.get("status") == "dispatched":
        return True
    status = str(matter.get("status", "")).strip().lower()
    return status in {"despachado / enviado", "despachado", "enviado"}


def _normalize_esign_status(raw_status: str) -> str | None:
    normalized = raw_status.strip().lower().replace(" ", "_")
    if not normalized:
        return None
    normalized = normalized.replace("-", "_")
    aliases = {
        "created": "signature_pending",
        "pending": "signature_pending",
        "sent": "signature_pending",
        "delivered": "signature_pending",
        "signature_requested": "signature_pending",
        "completed": "signed",
        "rejected": "declined",
        "canceled": "voided",
        "cancelled": "voided",
    }
    if normalized in aliases:
        normalized = aliases[normalized]
    if normalized in esign_connector.signature_statuses:
        return normalized
    return None


def _resolve_webhook_event_id(payload: Dict[str, Any]) -> str:
    event_id = (
        payload.get("event_id")
        or payload.get("eventId")
        or payload.get("id")
        or payload.get("webhook_id")
    )
    if event_id:
        return str(event_id)
    fingerprint = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    return "evt_" + hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]


def _verify_esign_webhook_signature(raw_body: bytes) -> bool:
    secret = os.getenv("LEGALFLOW_ESIGN_WEBHOOK_SECRET", "").strip()
    if not secret:
        if _is_production_like():
            return False
        return True
    provided = (
        request.headers.get("X-ESIGN-SIGNATURE", "").strip()
        or request.headers.get("X-WEBHOOK-SIGNATURE", "").strip()
        or request.headers.get("X-HUB-SIGNATURE-256", "").strip()
    )
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]
    if not provided:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(provided, expected)


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
    esign_health = esign_connector.integration_health()
    inbox_health = inbox_connector.integration_health()
    return jsonify(
        {
            "ok": True,
            "config": {
                "cursor_api_key_set": bool(os.getenv("CURSOR_API_KEY")),
                "sso_token_set": bool(os.getenv("LEGALFLOW_SSO_TOKEN")),
                "esign_endpoint_set": bool(os.getenv("LEGALFLOW_ESIGN_ENDPOINT")),
                "esign_api_key_set": bool(os.getenv("LEGALFLOW_ESIGN_API_KEY")),
                "esign_webhook_secret_set": bool(os.getenv("LEGALFLOW_ESIGN_WEBHOOK_SECRET")),
                "esign_mode": esign_health["mode"],
                "esign_missing_vars": esign_health["missing_vars"],
                "gmail_token_set": inbox_health["gmail_token_set"],
                "outlook_token_set": inbox_health["outlook_token_set"],
            },
        }
    )


@app.post("/api/analytics/track")
def analytics_track() -> Any:
    payload = json_payload()
    event = str(payload.get("event", "")).strip().lower()
    allowed_events = {
        "landing_view",
        "landing_cta_click",
        "landing_open_dashboard",
        "landing_open_demo",
    }
    if event not in allowed_events:
        return error_response("Evento no permitido.", 400, "invalid_event")
    metric_log(
        "landing_event",
        1,
        {
            "event": event,
            "source": str(payload.get("source", "landing")),
            "path": request.path,
            "ip": _extract_client_ip(),
            "user_agent": request.headers.get("User-Agent", "")[:180],
        },
    )
    audit_log(
        "landing_event",
        {
            "event": event,
            "source": str(payload.get("source", "landing")),
            "ip": _extract_client_ip(),
        },
    )
    return jsonify({"ok": True, "tracked": event})


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


@app.post("/api/analyze-contract")
def analyze_contract_upload() -> Any:
    ensure_data_dirs()
    retention_cleanup(retention_days=30)

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return error_response("Falta archivo en campo 'file'.", 400, "missing_file")

    mode = request.form.get("mode", "local")
    model = request.form.get("model", "composer-2.5")
    client_id = request.form.get("client_id", "default")
    analysis_mode = request.form.get("analysis_mode", "general")

    if mode not in {"local", "sdk"}:
        return error_response("Mode invalido.", 400, "invalid_mode")

    content = uploaded.read()
    if not content:
        return error_response("Archivo vacio.", 400, "empty_file")

    try:
        contract_text = limpiar_texto_subido(
            _extract_contract_text_from_upload(uploaded.filename, content)
        )
    except ErrorWorkflow as err:
        return error_response(str(err), 400, "unsupported_file")
    except UnicodeDecodeError:
        return error_response(
            "No pude leer el archivo. Verifica encoding/contenido.",
            400,
            "invalid_file_encoding",
        )
    except Exception as err:  # pragma: no cover
        return error_response(
            f"Error leyendo archivo: {err}", 500, "file_read_error"
        )

    if not contract_text:
        return error_response("No se extrajo texto del archivo.", 400, "empty_extraction")

    start = datetime.now(timezone.utc)
    try:
        result: Dict[str, Any] = ejecutar_workflow(
            contract_text,
            mode,
            model,
            verbose=False,
            cliente_id=client_id,
            modo_analisis=analysis_mode,
        )
    except ErrorWorkflow as err:
        audit_log("analyze_contract_error", {"client_id": client_id, "error": str(err)})
        return error_response(str(err), 400, "workflow_error")
    except Exception as err:  # pragma: no cover
        audit_log("analyze_contract_exception", {"client_id": client_id, "error": str(err)})
        return error_response(
            f"Error inesperado: {err}", 500, "internal_exception"
        )

    duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    compact = _compact_analysis_response(result, contract_text)
    metric_log(
        "analyze_contract_duration_ms",
        duration_ms,
        {"mode": mode, "client_id": client_id, "filename": uploaded.filename},
    )
    audit_log(
        "analyze_contract_completed",
        {
            "client_id": client_id,
            "mode": mode,
            "filename": uploaded.filename,
            "duration_ms": duration_ms,
            "run_id": compact.get("run_id"),
        },
    )
    return jsonify(
        {
            "ok": True,
            "analysis": compact,
            "metadata": {
                "filename": uploaded.filename,
                "mode": mode,
                "analysis_mode": analysis_mode,
                "duration_ms": duration_ms,
            },
        }
    )


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
    signer_name = payload.get("signer_name", "")
    esign_result = esign_connector.create_envelope(
        matter_id=matter_id,
        signer_email=signer_email,
        document_ref=document_ref,
        signer_name=signer_name,
    )
    update_status(matter_id, "signature_pending")
    update_esign_tracking(
        matter_id,
        {
            "provider": esign_result.get("provider"),
            "mode": esign_result.get("mode"),
            "status": esign_result.get("status", "signature_pending"),
            "envelope_id": esign_result.get("envelope_id"),
            "recipient_id": esign_result.get("recipient_id"),
            "signer_email": signer_email,
            "document_ref": document_ref,
        },
    )
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


@app.post("/api/routing/dispatch")
@require_sso(required_groups=["legal_admin", "legal_ops", "approver"])
def dispatch_routing() -> Any:
    payload = json_payload()
    matter_id = str(payload.get("matter_id", "")).strip()
    if not matter_id:
        return error_response("Falta matter_id.", 400, "missing_matter_id")
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")

    analysis_reviewed = payload.get("analysis_reviewed")
    if not isinstance(analysis_reviewed, dict):
        return error_response(
            "analysis_reviewed debe ser un objeto.", 400, "invalid_analysis_reviewed"
        )
    routing = payload.get("routing", {})
    if routing and not isinstance(routing, dict):
        return error_response("routing debe ser un objeto.", 400, "invalid_routing")
    approved_at = str(payload.get("approved_at") or datetime.now(timezone.utc).isoformat())
    approved_by = str(payload.get("approved_by") or sso_context(request)["email"])
    destination = _routing_destination_from_risk(
        str((routing or {}).get("suggested_destination", "")),
        analysis_reviewed,
    )

    updated = save_hitl_dispatch(
        matter_id,
        approved_by=approved_by,
        approved_at=approved_at,
        analysis_reviewed=analysis_reviewed,
        destination=destination,
        routing_status="dispatched",
    )
    append_event(
        matter_id,
        "routing_dispatched",
        {
            "by": sso_context(request)["email"],
            "approved_by": approved_by,
            "approved_at": approved_at,
            "destination": destination,
            "status": "Despachado / Enviado",
        },
    )
    audit_log(
        "routing_dispatched",
        {
            "matter_id": matter_id,
            "approved_by": approved_by,
            "destination": destination,
        },
    )
    return jsonify(
        {
            "ok": True,
            "dispatch": {
                "matter_id": matter_id,
                "destination": destination,
                "approved_by": approved_by,
                "approved_at": approved_at,
                "status": updated.get("status"),
            },
            "matter": updated,
        }
    )


@app.get("/api/routing/queue")
def routing_queue() -> Any:
    items = list_matters(limit=500)
    pending: List[Dict[str, Any]] = []
    dispatched: List[Dict[str, Any]] = []
    for matter in items:
        item = _matter_queue_item(matter)
        if _is_dispatched_matter(matter):
            dispatched.append(item)
        else:
            pending.append(item)
    return jsonify(
        {
            "ok": True,
            "pending_review": pending,
            "dispatched_history": dispatched,
            "counts": {
                "pending_review": len(pending),
                "dispatched_history": len(dispatched),
                "total": len(items),
            },
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
    update_status(matter_id, "signature_pending")
    update_esign_tracking(
        matter_id,
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "status": result.get("status", "signature_pending"),
            "envelope_id": result.get("envelope_id"),
            "recipient_id": result.get("recipient_id"),
            "signer_email": signer_email,
            "document_ref": document_ref,
        },
    )
    append_event(matter_id, "esign_requested", {"by": sso_context(request)["email"], **result})
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/esign/create-envelope")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def create_esign_envelope() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id")
    signer_email = payload.get("signer_email")
    signer_name = payload.get("signer_name", "")
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
    result = esign_connector.create_envelope(
        matter_id=matter_id,
        signer_email=signer_email,
        document_ref=document_ref,
        signer_name=signer_name,
    )
    update_status(matter_id, "signature_pending")
    update_esign_tracking(
        matter_id,
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "status": result.get("status", "signature_pending"),
            "envelope_id": result.get("envelope_id"),
            "recipient_id": result.get("recipient_id"),
            "signer_email": signer_email,
            "document_ref": document_ref,
        },
    )
    append_event(
        matter_id,
        "esign_envelope_created",
        {"by": sso_context(request)["email"], **result},
    )
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/esign/recipient-view")
@require_sso(required_groups=["legal_admin", "legal_ops"])
def create_esign_recipient_view() -> Any:
    payload = json_payload()
    matter_id = payload.get("matter_id")
    if not matter_id:
        return error_response("Falta matter_id.", 400, "missing_matter_id")
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    esign_tracking = matter.get("esign", {})
    envelope_id = payload.get("envelope_id") or esign_tracking.get("envelope_id")
    recipient_id = payload.get("recipient_id") or esign_tracking.get("recipient_id")
    return_url = payload.get("return_url")
    if not envelope_id or not recipient_id:
        return error_response(
            "Faltan envelope_id o recipient_id.", 400, "missing_envelope_or_recipient"
        )
    result = esign_connector.recipient_view(
        envelope_id=envelope_id,
        recipient_id=recipient_id,
        return_url=return_url,
    )
    update_esign_tracking(
        matter_id,
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "status": result.get("status", "signature_pending"),
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "signing_url": result.get("signing_url"),
        },
    )
    append_event(
        matter_id,
        "esign_recipient_view_created",
        {"by": sso_context(request)["email"], **result},
    )
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/esign/webhook")
def esign_webhook() -> Any:
    raw_body = request.get_data(cache=True) or b""
    if not _verify_esign_webhook_signature(raw_body):
        audit_log(
            "esign_webhook_invalid_signature",
            {"reason": "signature_mismatch", "path": request.path},
        )
        return error_response(
            "Firma de webhook invalida.", 401, "invalid_webhook_signature"
        )

    payload = json_payload()
    envelope_id = str(payload.get("envelope_id") or payload.get("envelopeId") or "").strip()
    matter_id = str(payload.get("matter_id") or payload.get("matterId") or "").strip()
    raw_status = str(payload.get("status") or payload.get("event") or "").strip()
    status = _normalize_esign_status(raw_status)
    if not status:
        return error_response(
            "status invalido para webhook e-sign.", 400, "invalid_esign_status"
        )
    if not matter_id:
        if not envelope_id:
            return error_response(
                "Falta matter_id o envelope_id.", 400, "missing_fields"
            )
        matter = find_matter_by_envelope_id(envelope_id)
        if not matter:
            return error_response(
                "Matter no encontrado para envelope_id.", 404, "matter_not_found"
            )
        matter_id = matter.get("matter_id", "")
    if not validar_matter_id(matter_id):
        return error_response("matter_id invalido.", 400, "invalid_matter_id")
    matter = get_matter(matter_id)
    if not matter:
        return error_response("Matter no encontrado.", 404, "matter_not_found")
    if not envelope_id:
        envelope_id = str(matter.get("esign", {}).get("envelope_id") or "").strip()
    if not envelope_id:
        return error_response(
            "No se encontro envelope_id asociado al matter.", 400, "missing_envelope_id"
        )
    recipient_id = str(
        payload.get("recipient_id")
        or payload.get("recipientId")
        or matter.get("esign", {}).get("recipient_id")
        or ""
    ).strip()
    event_id = _resolve_webhook_event_id(payload)
    if has_esign_webhook_event_id(matter_id, event_id):
        current = get_matter(matter_id) or matter
        return jsonify(
            {
                "ok": True,
                "duplicate": True,
                "matter_id": matter_id,
                "event_id": event_id,
                "status": current.get("status"),
            }
        )

    update_status(matter_id, status)
    update_esign_tracking(
        matter_id,
        {
            "status": status,
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "last_webhook_event_id": event_id,
            "last_webhook_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    append_event(
        matter_id,
        "esign_webhook_received",
        {
            "event_id": event_id,
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "status": status,
            "raw_status": raw_status,
            "source": "esign_webhook",
        },
    )
    register_esign_webhook_event_id(matter_id, event_id)
    audit_log(
        "esign_webhook_processed",
        {
            "matter_id": matter_id,
            "event_id": event_id,
            "status": status,
        },
    )
    return jsonify(
        {
            "ok": True,
            "duplicate": False,
            "matter_id": matter_id,
            "event_id": event_id,
            "status": status,
        }
    )


@app.post("/api/integrations/inbox/connect")
@require_sso(required_groups=["legal_admin", "legal_ops", "legal_viewer", "approver"])
def inbox_connect() -> Any:
    payload = json_payload()
    provider = str(payload.get("provider", "")).strip().lower()
    if not provider:
        return error_response("Falta provider.", 400, "missing_provider")
    try:
        result = inbox_connector.connect(provider, sso_context(request)["email"])
    except ValueError as err:
        return error_response(str(err), 400, "invalid_provider")
    audit_log(
        "inbox_connected",
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "by": sso_context(request)["email"],
        },
    )
    return jsonify({"ok": True, "integration": result})


@app.post("/api/integrations/inbox/search")
@require_sso(required_groups=["legal_admin", "legal_ops", "legal_viewer", "approver"])
def inbox_search() -> Any:
    payload = json_payload()
    provider = str(payload.get("provider", "")).strip().lower()
    query = str(payload.get("query", "")).strip()
    if not provider:
        return error_response("Falta provider.", 400, "missing_provider")
    if len(query) < 2:
        return error_response("query debe tener al menos 2 caracteres.", 400, "invalid_query")
    try:
        result = inbox_connector.search(provider, query)
    except ValueError as err:
        return error_response(str(err), 400, "invalid_provider")
    metric_log(
        "inbox_search_count",
        result.get("total", 0),
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "query_len": len(query),
            "user": sso_context(request)["email"],
        },
    )
    audit_log(
        "inbox_search_executed",
        {
            "provider": result.get("provider"),
            "mode": result.get("mode"),
            "results": result.get("total", 0),
            "by": sso_context(request)["email"],
        },
    )
    return jsonify({"ok": True, "integration": result})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from agente import ErrorWorkflow, ejecutar_workflow
from observability import CASES_DIR, audit_log, ensure_data_dirs, metric_log, redact_sensitive, retention_cleanup

app = Flask(__name__)


def limpiar_texto_subido(texto: str) -> str:
    return texto.strip()


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
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "No pude leer el archivo. Usa .txt UTF-8 o pega el texto del contrato.",
                        }
                    ),
                    400,
                )

    contrato_texto = limpiar_texto_subido(contrato_texto)
    contrato_b = limpiar_texto_subido(contrato_b)
    if not contrato_texto:
        return jsonify({"ok": False, "error": "Debes pegar o subir un contrato."}), 400

    if modo not in {"local", "sdk"}:
        return jsonify({"ok": False, "error": "Modo invalido."}), 400

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
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception as err:  # pragma: no cover
        audit_log("analysis_exception", {"cliente_id": cliente_id, "error": str(err)})
        return jsonify({"ok": False, "error": f"Error inesperado: {err}"}), 500

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
    payload = request.get_json(force=True, silent=True) or {}
    titulo = payload.get("titulo", "").strip()
    if not titulo:
        return jsonify({"ok": False, "error": "El caso requiere un titulo."}), 400

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
        return jsonify({"ok": False, "error": "Caso no encontrado."}), 404
    data = json.loads(path.read_text(encoding="utf-8"))
    return jsonify({"ok": True, "caso": data})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)

from __future__ import annotations

from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

from agente import ErrorWorkflow, ejecutar_workflow

app = Flask(__name__)


def limpiar_texto_subido(texto: str) -> str:
    return texto.strip()


@app.get("/")
def home() -> str:
    return render_template("portal.html")


@app.post("/api/analizar")
def analizar_contrato() -> Any:
    contrato_texto = request.form.get("contrato", "")
    modo = request.form.get("modo", "local")
    modelo = request.form.get("modelo", "composer-2.5")

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
    if not contrato_texto:
        return jsonify({"ok": False, "error": "Debes pegar o subir un contrato."}), 400

    if modo not in {"local", "sdk"}:
        return jsonify({"ok": False, "error": "Modo invalido."}), 400

    try:
        resultado: Dict[str, Any] = ejecutar_workflow(
            contrato_texto, modo, modelo, verbose=False
        )
    except ErrorWorkflow as err:
        return jsonify({"ok": False, "error": str(err)}), 400
    except Exception as err:  # pragma: no cover
        return jsonify({"ok": False, "error": f"Error inesperado: {err}"}), 500

    return jsonify({"ok": True, "resultado": resultado})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)

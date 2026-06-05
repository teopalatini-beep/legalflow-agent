"""
Pipeline unificado de LegalFlow.

Objetivo:
- Ejecutar el flujo completo en una sola corrida no interactiva.
- Unificar: emails -> contrato borrador -> analisis -> comparacion opcional.

Uso rapido:
  python3 pipeline_unificado.py
  python3 pipeline_unificado.py --emails-file emails_extraidos.txt
  python3 pipeline_unificado.py --emails-file emails_extraidos.txt --contrato-v1-file contrato_v1.txt
  python3 pipeline_unificado.py --output-dir salida_pipeline
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import gmail_agente
import legalflow


def _leer_texto(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _guardar_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _construir_contrato_texto(resultado_gmail: Dict[str, Any]) -> str:
    contrato = resultado_gmail.get("contrato", {})
    titulo = contrato.get("titulo", "CONTRATO")
    preambulo = contrato.get("preambulo", "")
    clausulas = contrato.get("clausulas", [])

    bloques = [titulo.strip(), "", preambulo.strip(), ""]
    for clausula in sorted(clausulas, key=lambda x: x.get("numero", 0)):
        numero = clausula.get("numero", "?")
        titulo_cl = clausula.get("titulo", "SIN TITULO")
        texto_cl = clausula.get("texto", "").strip()
        bloques.append(f"CLAUSULA {numero} - {titulo_cl}")
        bloques.append(texto_cl)
        bloques.append("")

    sugeridas = resultado_gmail.get("clausulas_sugeridas", [])
    if sugeridas:
        bloques.append("--- CLAUSULAS SUGERIDAS (REVISAR ANTES DE INCLUIR) ---")
        bloques.append("")
        for sugerida in sugeridas:
            bloques.append(sugerida.get("titulo", "SIN TITULO"))
            bloques.append(sugerida.get("texto", "").strip())
            justificacion = sugerida.get("justificacion", "").strip()
            if justificacion:
                bloques.append(f"Justificacion: {justificacion}")
            bloques.append("")

    return "\n".join(bloques).strip() + "\n"


def _obtener_borrador_desde_emails(emails_text: Optional[str]) -> Dict[str, Any]:
    if not emails_text:
        return gmail_agente.demo_resultado()

    resultado = gmail_agente.analizar_con_claude(emails_text)
    if resultado:
        return resultado
    return gmail_agente.demo_resultado()


def ejecutar_pipeline(
    emails_text: Optional[str],
    contrato_v1: Optional[str],
) -> Dict[str, Any]:
    borrador = _obtener_borrador_desde_emails(emails_text)
    contrato_actual = _construir_contrato_texto(borrador)

    analisis_negociacion = legalflow.capa_2_negociacion(contrato_actual, verbose=False)

    comparacion = None
    if contrato_v1:
        comparacion = legalflow.capa_3_comparacion(contrato_v1, contrato_actual, verbose=False)

    salida: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "fuente_emails": "archivo/API" if emails_text else "demo",
        "pipeline": {
            "borrador_contrato": borrador,
            "analisis_negociacion": analisis_negociacion,
            "comparacion": comparacion,
        },
    }
    return salida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline unificado de LegalFlow (no interactivo)."
    )
    parser.add_argument(
        "--emails-file",
        help="Ruta a archivo de emails para extraer negociacion.",
    )
    parser.add_argument(
        "--contrato-v1-file",
        help="Ruta a contrato version anterior para comparar contra borrador actual.",
    )
    parser.add_argument(
        "--output-dir",
        default="pipeline_output",
        help="Directorio donde se guardan artefactos JSON/TXT.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    emails_text = _leer_texto(args.emails_file) if args.emails_file else None
    contrato_v1 = _leer_texto(args.contrato_v1_file) if args.contrato_v1_file else None

    resultado = ejecutar_pipeline(emails_text=emails_text, contrato_v1=contrato_v1)

    os.makedirs(args.output_dir, exist_ok=True)

    borrador = resultado["pipeline"]["borrador_contrato"]
    contrato_actual = _construir_contrato_texto(borrador)
    analisis = resultado["pipeline"]["analisis_negociacion"]
    comparacion = resultado["pipeline"]["comparacion"]

    _guardar_json(os.path.join(args.output_dir, "gmail_contrato.json"), borrador)
    with open(
        os.path.join(args.output_dir, "contrato_borrador.txt"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write(contrato_actual)
    _guardar_json(os.path.join(args.output_dir, "analisis_negociacion.json"), analisis)
    if comparacion is not None:
        _guardar_json(os.path.join(args.output_dir, "comparacion_v1_vs_actual.json"), comparacion)
    _guardar_json(os.path.join(args.output_dir, "pipeline_resumen.json"), resultado)

    print("\n=== PIPELINE UNIFICADO COMPLETADO ===")
    print(f"Salida: {args.output_dir}")
    print(f"- Riesgo actual: {analisis.get('nivel')} (score {analisis.get('score')}/100)")
    print(f"- Recomendacion: {analisis.get('recomendacion')}")
    if comparacion is not None:
        print(f"- Mejora de score vs V1: {comparacion.get('mejora_score')}")
    print("- Artefactos: gmail_contrato.json, contrato_borrador.txt, analisis_negociacion.json, pipeline_resumen.json")
    if comparacion is not None:
        print("- Artefacto adicional: comparacion_v1_vs_actual.json")
    print()


if __name__ == "__main__":
    main()

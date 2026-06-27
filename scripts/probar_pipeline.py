"""Runner manual para inspeccionar el output crudo del pipeline (Paso 3).

Uso:
    # Con Claude real (recomendado):
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 scripts/probar_pipeline.py

    # Sin key: corre en MODO DEMO (keywords), marcado como tal.

Corre 4 contratos de complejidad creciente y muestra el JSON crudo de cada
paso (Ingesta -> Extracción -> Riesgos -> Redline -> Resumen -> Verifier).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agente import ejecutar_workflow  # noqa: E402

CONTRATOS = {
    "1. Servicios (conocido, riesgo bajo-medio)": (
        "Contrato de prestación de servicios entre ACME SA y Proveedor SRL. "
        "El proveedor entrega el software en 45 días. Confidencialidad por 5 años. "
        "En caso de incumplimiento se aplica multa del 10%. "
        "Jurisdicción: tribunales ordinarios de la Ciudad Autónoma de Buenos Aires."
    ),
    "2. Servicios ABUSIVO (debería dar riesgo ALTO)": (
        "Contrato de servicios entre MegaCorp Inc. (Cliente) y DevShop SRL (Proveedor). "
        "El Proveedor cede a MegaCorp la totalidad de la propiedad intelectual, "
        "incluyendo metodologías y conocimientos previos. "
        "En caso de cualquier incumplimiento del Proveedor se aplica una multa del 30% "
        "del valor total, sin necesidad de intimación previa. "
        "MegaCorp puede rescindir el contrato en cualquier momento sin causa ni preaviso; "
        "el Proveedor no puede rescindir bajo ninguna circunstancia. "
        "La responsabilidad de MegaCorp queda limitada a cero. "
        "Jurisdicción exclusiva: tribunales del Estado de Florida, Estados Unidos, "
        "con renuncia expresa a cualquier otro fuero."
    ),
    "3. NDA bilateral simple": (
        "Acuerdo de confidencialidad mutuo entre Empresa A SA y Empresa B SA. "
        "Ambas partes se obligan a no divulgar información confidencial recibida "
        "durante la negociación, por un plazo de 3 años desde la firma. "
        "Se exceptúa la información de dominio público. "
        "Jurisdicción: tribunales de la Provincia de Buenos Aires."
    ),
    "4. Locación comercial": (
        "Contrato de locación comercial entre Locador Juan Pérez y Locataria Tienda XYZ SRL. "
        "Plazo: 36 meses. Canon mensual de $500.000 con ajuste trimestral por índice. "
        "Depósito en garantía equivalente a 2 meses. "
        "El locatario no puede ceder ni subarrendar sin consentimiento escrito. "
        "Rescisión anticipada por el locatario con preaviso de 60 días y multa de 1 mes. "
        "Jurisdicción: tribunales ordinarios de CABA."
    ),
}


def main() -> None:
    modo = "sdk"  # intenta Claude; cae a demo si no hay ANTHROPIC_API_KEY
    tiene_key = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    print("=" * 70)
    print(f"ANTHROPIC_API_KEY presente: {tiene_key}")
    print(f"Engine esperado: {'claude-sonnet-4-6' if tiene_key else 'MODO DEMO (keywords)'}")
    print("=" * 70)

    for titulo, contrato in CONTRATOS.items():
        print("\n\n" + "#" * 70)
        print(f"# {titulo}")
        print("#" * 70)
        resultado = ejecutar_workflow(
            contrato, modo=modo, model="claude-sonnet-4-6", verbose=False
        )
        print(f"\n[engine: {resultado['engine']}  |  is_demo: {resultado['is_demo']}]")
        if resultado.get("demo_fallback"):
            print(f"[AVISO] {resultado['demo_fallback']}")
        vista = {
            "tipo_contrato_probable": resultado.get("tipo_contrato_probable"),
            "clausulas_detectadas": resultado.get("clausulas_detectadas"),
            "obligaciones_principales": resultado.get("obligaciones_principales"),
            "clausula_evidencias": resultado.get("clausula_evidencias"),
            "riesgos_detectados": resultado.get("riesgos_detectados"),
            "redlines_sugeridos": resultado.get("redlines_sugeridos"),
            "resumen_final": resultado.get("resumen_final"),
            "accion_recomendada": resultado.get("accion_recomendada"),
            "quality_warnings": resultado.get("quality_warnings"),
            "quality_score": resultado.get("quality_score"),
        }
        print(json.dumps(vista, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

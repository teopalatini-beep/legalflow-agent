# LegalFlow Agent - Workflow por etapas con Cursor SDK

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict

try:
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

    CURSOR_SDK_DISPONIBLE = True
except ImportError:
    CURSOR_SDK_DISPONIBLE = False


Contexto = Dict[str, Any]


@dataclass
class PasoAgente:
    nombre: str
    accion: Callable[[Contexto], Contexto]


class ErrorWorkflow(RuntimeError):
    """Error de negocio del pipeline."""


def modelo_efectivo(model: str) -> str:
    # Algunos entornos no aceptan "auto" para local runtime.
    return "composer-2.5" if model.strip().lower() == "auto" else model


def extraer_json(texto: str) -> Dict[str, Any]:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ErrorWorkflow("El agente no devolvio JSON valido.")


def invocar_agente_sdk(nombre_paso: str, prompt: str, model: str) -> Dict[str, Any]:
    if not CURSOR_SDK_DISPONIBLE:
        raise ErrorWorkflow(
            "cursor_sdk no esta instalado. Instala con: pip install cursor-sdk"
        )

    api_key = os.getenv("CURSOR_API_KEY")
    if not api_key:
        raise ErrorWorkflow(
            "Falta CURSOR_API_KEY. Exporta la variable antes de ejecutar."
        )

    model = modelo_efectivo(model)

    try:
        resultado = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=api_key,
                model=model,
                local=LocalAgentOptions(cwd=os.getcwd()),
            ),
        )
    except CursorAgentError as err:
        raise ErrorWorkflow(
            f"Fallo al iniciar el agente en '{nombre_paso}': {err.message}"
        ) from err

    if resultado.status == "error":
        raise ErrorWorkflow(
            f"El agente reporto error en '{nombre_paso}'. run_id={resultado.id}"
        )

    return extraer_json(resultado.result)


def agente_ingesta_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
Eres un analista legal. Limpia y normaliza este contrato.
Devuelve SOLO JSON valido con este schema exacto:
{{
  "texto_limpio": "string",
  "cantidad_palabras": 0,
  "tipo_contrato_probable": "string"
}}

Contrato:
{contexto["contrato"]}
"""
    return invocar_agente_sdk("Ingesta", prompt, model)


def agente_extraccion_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
Eres un extractor de clausulas.
Devuelve SOLO JSON valido con este schema exacto:
{{
  "clausulas_detectadas": ["string"],
  "obligaciones_principales": ["string"]
}}

Texto de contrato:
{contexto["texto_limpio"]}
"""
    return invocar_agente_sdk("Extraccion de clausulas", prompt, model)


def agente_riesgos_sdk(contexto: Contexto, model: str) -> Contexto:
    clausulas = json.dumps(contexto["clausulas_detectadas"], ensure_ascii=True)
    obligaciones = json.dumps(contexto["obligaciones_principales"], ensure_ascii=True)
    prompt = f"""
Eres un abogado de riesgos contractuales.
Devuelve SOLO JSON valido con este schema exacto:
{{
  "riesgos_detectados": [
    {{
      "riesgo": "string",
      "nivel": "bajo|medio|alto",
      "recomendacion": "string"
    }}
  ]
}}

Clausulas detectadas: {clausulas}
Obligaciones principales: {obligaciones}
"""
    return invocar_agente_sdk("Analisis de riesgos", prompt, model)


def agente_resumen_sdk(contexto: Contexto, model: str) -> Contexto:
    riesgos = json.dumps(contexto["riesgos_detectados"], ensure_ascii=True)
    prompt = f"""
Eres un asistente de reportes ejecutivos.
Devuelve SOLO JSON valido con este schema exacto:
{{
  "resumen_final": "string",
  "accion_recomendada": "string"
}}

Datos:
- Tipo de contrato: {contexto["tipo_contrato_probable"]}
- Cantidad de palabras: {contexto["cantidad_palabras"]}
- Clausulas: {json.dumps(contexto["clausulas_detectadas"], ensure_ascii=True)}
- Riesgos: {riesgos}
"""
    return invocar_agente_sdk("Resumen final", prompt, model)


def agente_ingesta_local(contexto: Contexto) -> Contexto:
    texto_limpio = " ".join(contexto["contrato"].split())
    return {
        "texto_limpio": texto_limpio,
        "cantidad_palabras": len(texto_limpio.split()),
        "tipo_contrato_probable": "servicios (estimado)",
    }


def agente_extraccion_local(contexto: Contexto) -> Contexto:
    texto = contexto["texto_limpio"].lower()
    clausulas = []
    if "confidencialidad" in texto:
        clausulas.append("confidencialidad")
    if "multa" in texto or "penalidad" in texto:
        clausulas.append("penalidad")
    if "jurisdiccion" in texto or "tribunal" in texto:
        clausulas.append("jurisdiccion")
    if not clausulas:
        clausulas.append("sin coincidencias automaticas")
    return {
        "clausulas_detectadas": clausulas,
        "obligaciones_principales": [
            "Cumplir entregables en plazo",
            "Respetar condiciones economicas pactadas",
        ],
    }


def agente_riesgos_local(contexto: Contexto) -> Contexto:
    riesgos = []
    clausulas = ",".join(contexto["clausulas_detectadas"])
    if "penalidad" in clausulas:
        riesgos.append(
            {
                "riesgo": "Clausula penal potencialmente onerosa",
                "nivel": "medio",
                "recomendacion": "Negociar tope de penalidad y supuestos de aplicacion",
            }
        )
    if "jurisdiccion" in clausulas:
        riesgos.append(
            {
                "riesgo": "Jurisdiccion posiblemente desfavorable",
                "nivel": "medio",
                "recomendacion": "Alinear tribunal con domicilio o sede operativa",
            }
        )
    if not riesgos:
        riesgos.append(
            {
                "riesgo": "Sin riesgos evidentes por heuristica",
                "nivel": "bajo",
                "recomendacion": "Hacer revision legal completa",
            }
        )
    return {"riesgos_detectados": riesgos}


def agente_resumen_local(contexto: Contexto) -> Contexto:
    resumen = (
        f"Tipo probable: {contexto['tipo_contrato_probable']}\n"
        f"Palabras: {contexto['cantidad_palabras']}\n"
        f"Clausulas: {', '.join(contexto['clausulas_detectadas'])}\n"
        f"Riesgos: {len(contexto['riesgos_detectados'])} item(s)"
    )
    return {
        "resumen_final": resumen,
        "accion_recomendada": "Revisar puntos de riesgo con asesor legal antes de firmar.",
    }


def construir_flujo(modo: str, model: str) -> list[PasoAgente]:
    if modo == "sdk":
        return [
            PasoAgente("Ingesta", lambda c: agente_ingesta_sdk(c, model)),
            PasoAgente("Extraccion de clausulas", lambda c: agente_extraccion_sdk(c, model)),
            PasoAgente("Analisis de riesgos", lambda c: agente_riesgos_sdk(c, model)),
            PasoAgente("Resumen final", lambda c: agente_resumen_sdk(c, model)),
        ]

    return [
        PasoAgente("Ingesta", agente_ingesta_local),
        PasoAgente("Extraccion de clausulas", agente_extraccion_local),
        PasoAgente("Analisis de riesgos", agente_riesgos_local),
        PasoAgente("Resumen final", agente_resumen_local),
    ]


def ejecutar_workflow(
    contrato: str, modo: str, model: str, verbose: bool = True
) -> Contexto:
    contexto: Contexto = {"contrato": contrato}
    flujo = construir_flujo(modo, model)

    if verbose:
        print("\n=== LEGALFLOW WORKFLOW ===")
        print(f"Modo: {modo}")
        if modo == "sdk":
            print(f"Modelo: {model}")

    for paso in flujo:
        if verbose:
            print(f"\n[Ejecutando] Agente: {paso.nombre}")
        salida = paso.accion(contexto)
        contexto.update(salida)
        if verbose:
            print(f"[OK] Output {paso.nombre}: {json.dumps(salida, ensure_ascii=True)}")

    return contexto


def contrato_demo() -> str:
    return (
        "Contrato de prestacion de servicios entre ACME SA y Proveedor SRL. "
        "El proveedor se compromete a entregar el software en 45 dias. "
        "Incluye clausula de confidencialidad por 5 anos. "
        "En caso de incumplimiento se aplica multa del 10%. "
        "La jurisdiccion sera en tribunales de Ciudad Autonoma de Buenos Aires."
    )


def leer_contrato_stdin() -> str:
    print("Pega el contrato y presiona Enter dos veces:")
    lineas = []
    while True:
        linea = input()
        if linea == "":
            break
        lineas.append(linea)
    return "\n".join(lineas)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LegalFlow workflow multi-agente")
    parser.add_argument(
        "--modo",
        choices=["sdk", "local"],
        default="local",
        help="sdk usa Cursor SDK; local usa heuristicas sin API.",
    )
    parser.add_argument(
        "--model",
        default="composer-2.5",
        help="Modelo de Cursor SDK (solo aplica en --modo sdk).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ejecuta un contrato de ejemplo embebido.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Bienvenido al Agente LegalFlow")
    print("--------------------------------")

    contrato = contrato_demo() if args.demo else leer_contrato_stdin()

    try:
        resultado = ejecutar_workflow(contrato, args.modo, args.model, verbose=True)
    except ErrorWorkflow as err:
        print(f"\n[ERROR] {err}")
        return

    print("\n=== RESULTADO FINAL ===")
    print(resultado["resumen_final"])
    print("\nAccion recomendada:")
    print(resultado["accion_recomendada"])


if __name__ == "__main__":
    main()

# LegalFlow Agent - Orquestador multiagente con playbooks y memoria

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List
from uuid import uuid4

try:
    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

    CURSOR_SDK_DISPONIBLE = True
except ImportError:
    CURSOR_SDK_DISPONIBLE = False


Contexto = Dict[str, Any]
BASE_PATH = Path(__file__).parent
PLAYBOOK_DIR = BASE_PATH / "data" / "playbooks"
MEMORY_DIR = BASE_PATH / "data" / "memory"
RUNS_DIR = BASE_PATH / "data" / "runs"

DEFAULT_PLAYBOOK = {
    "cliente": "default",
    "clausulas_preferidas": [
        "confidencialidad",
        "responsabilidad",
        "jurisdiccion",
        "rescision",
    ],
    "red_flags_criticos": [
        "jurisdiccion extranjera",
        "multa sin intimacion",
        "rescision unilateral asimetrica",
    ],
    "jurisdicciones_permitidas": ["caba", "provincia de buenos aires"],
    "tono_negociacion": "firme y colaborativo",
}


@dataclass
class PasoAgente:
    nombre: str
    rol: str
    accion: Callable[[Contexto, str], Contexto]
    schema: Dict[str, type]


class ErrorWorkflow(RuntimeError):
    """Error de negocio del pipeline."""


def modelo_efectivo(model: str) -> str:
    return "composer-2.5" if model.strip().lower() == "auto" else model


def modelos_fallback(modelo_solicitado: str) -> List[str]:
    base = [modelo_efectivo(modelo_solicitado), "composer-2.5", "gpt-5.5"]
    salida: List[str] = []
    for item in base:
        if item not in salida:
            salida.append(item)
    return salida


def asegurar_directorios() -> None:
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def cargar_playbook(cliente_id: str) -> Dict[str, Any]:
    asegurar_directorios()
    ruta = PLAYBOOK_DIR / f"{cliente_id}.json"
    if not ruta.exists():
        return dict(DEFAULT_PLAYBOOK)
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ErrorWorkflow(f"Playbook invalido para cliente '{cliente_id}'.")


def extraer_json(texto: str) -> Dict[str, Any]:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ErrorWorkflow("El agente no devolvio JSON valido.")


def validar_schema(salida: Dict[str, Any], schema: Dict[str, type], paso: str) -> None:
    for key, expected_type in schema.items():
        if key not in salida:
            raise ErrorWorkflow(f"Falta '{key}' en salida de '{paso}'.")
        if not isinstance(salida[key], expected_type):
            raise ErrorWorkflow(
                f"Campo '{key}' invalido en '{paso}'. Esperado {expected_type.__name__}."
            )


def invocar_agente_sdk(prompt: str, model: str) -> Dict[str, Any]:
    if not CURSOR_SDK_DISPONIBLE:
        raise ErrorWorkflow(
            "cursor_sdk no esta instalado. Instala con: pip install cursor-sdk"
        )
    api_key = os.getenv("CURSOR_API_KEY")
    if not api_key:
        raise ErrorWorkflow("Falta CURSOR_API_KEY. Exporta la variable antes de ejecutar.")

    resultado = Agent.prompt(
        prompt,
        AgentOptions(
            api_key=api_key,
            model=model,
            local=LocalAgentOptions(cwd=os.getcwd()),
        ),
    )
    if resultado.status == "error":
        raise ErrorWorkflow(f"Run con error en SDK. run_id={resultado.id}")
    return extraer_json(resultado.result)


def ejecutar_con_retry(
    paso: PasoAgente, contexto: Contexto, modo: str, model: str, max_retries: int = 2
) -> Dict[str, Any]:
    errores: List[str] = []
    intentos_totales = 0
    for candidate_model in modelos_fallback(model):
        for _ in range(max_retries):
            intentos_totales += 1
            try:
                salida = paso.accion(contexto, candidate_model if modo == "sdk" else model)
                validar_schema(salida, paso.schema, paso.nombre)
                salida["_meta"] = {
                    "attempts": intentos_totales,
                    "model_used": candidate_model if modo == "sdk" else "local-heuristic",
                }
                return salida
            except (ErrorWorkflow, CursorAgentError) as err:
                errores.append(str(err))
            except Exception as err:
                errores.append(f"Error inesperado: {err}")
    raise ErrorWorkflow(
        f"No se pudo completar '{paso.nombre}' luego de reintentos/fallback. "
        f"Ultimo error: {errores[-1] if errores else 'desconocido'}"
    )


def construir_prompt_base(contexto: Contexto) -> str:
    pb = contexto["playbook"]
    modo_analisis = contexto["modo_analisis"]
    return (
        f"Cliente: {pb.get('cliente', 'default')}\n"
        f"Modo analisis: {modo_analisis}\n"
        f"Clausulas preferidas: {json.dumps(pb.get('clausulas_preferidas', []), ensure_ascii=True)}\n"
        f"Red flags criticos: {json.dumps(pb.get('red_flags_criticos', []), ensure_ascii=True)}\n"
        f"Jurisdicciones permitidas: {json.dumps(pb.get('jurisdicciones_permitidas', []), ensure_ascii=True)}\n"
        f"Tono negociacion: {pb.get('tono_negociacion', 'colaborativo')}\n"
    )


def agente_ingesta_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
{construir_prompt_base(contexto)}
Eres un analista legal. Limpia y normaliza este contrato.
Devuelve SOLO JSON valido:
{{
  "texto_limpio": "string",
  "cantidad_palabras": 0,
  "tipo_contrato_probable": "string"
}}
Contrato:
{contexto["contrato"]}
"""
    return invocar_agente_sdk(prompt, model)


def agente_extraccion_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
{construir_prompt_base(contexto)}
Eres un extractor de clausulas.
Devuelve SOLO JSON valido:
{{
  "clausulas_detectadas": ["string"],
  "obligaciones_principales": ["string"],
  "clausula_evidencias": {{"nombre_clausula": "fragmento_de_texto"}}
}}
Texto:
{contexto["texto_limpio"]}
"""
    return invocar_agente_sdk(prompt, model)


def agente_riesgos_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
{construir_prompt_base(contexto)}
Eres un abogado de riesgos contractuales.
Devuelve SOLO JSON valido:
{{
  "riesgos_detectados": [
    {{
      "riesgo": "string",
      "nivel": "bajo|medio|alto",
      "recomendacion": "string",
      "confianza": 0.0,
      "clausula_relacionada": "string"
    }}
  ]
}}
Clausulas: {json.dumps(contexto["clausulas_detectadas"], ensure_ascii=True)}
Obligaciones: {json.dumps(contexto["obligaciones_principales"], ensure_ascii=True)}
"""
    return invocar_agente_sdk(prompt, model)


def agente_redline_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
{construir_prompt_base(contexto)}
Genera redlines sugeridos.
Devuelve SOLO JSON valido:
{{
  "redlines_sugeridos": [
    {{
      "clausula": "string",
      "texto_sugerido": "string",
      "motivo": "string"
    }}
  ]
}}
Riesgos: {json.dumps(contexto["riesgos_detectados"], ensure_ascii=True)}
"""
    return invocar_agente_sdk(prompt, model)


def agente_resumen_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
{construir_prompt_base(contexto)}
Resume el analisis en tono ejecutivo.
Devuelve SOLO JSON valido:
{{
  "resumen_final": "string",
  "accion_recomendada": "string"
}}
Riesgos: {json.dumps(contexto["riesgos_detectados"], ensure_ascii=True)}
Redlines: {json.dumps(contexto["redlines_sugeridos"], ensure_ascii=True)}
"""
    return invocar_agente_sdk(prompt, model)


def agente_verifier_sdk(contexto: Contexto, model: str) -> Contexto:
    prompt = f"""
Eres QA legal. Verifica consistencia entre clausulas, riesgos y redlines.
Devuelve SOLO JSON valido:
{{
  "quality_warnings": ["string"],
  "quality_score": 0
}}
Clausulas: {json.dumps(contexto["clausulas_detectadas"], ensure_ascii=True)}
Riesgos: {json.dumps(contexto["riesgos_detectados"], ensure_ascii=True)}
Redlines: {json.dumps(contexto["redlines_sugeridos"], ensure_ascii=True)}
"""
    return invocar_agente_sdk(prompt, model)


def agente_ingesta_local(contexto: Contexto, _: str) -> Contexto:
    texto_limpio = " ".join(contexto["contrato"].split())
    return {
        "texto_limpio": texto_limpio,
        "cantidad_palabras": len(texto_limpio.split()),
        "tipo_contrato_probable": "servicios (estimado)",
    }


def agente_extraccion_local(contexto: Contexto, _: str) -> Contexto:
    texto = contexto["texto_limpio"].lower()
    clausulas = []
    evidencias: Dict[str, str] = {}
    for key, keyword in {
        "confidencialidad": "confidencial",
        "penalidad": "multa",
        "jurisdiccion": "jurisdic",
        "rescision": "rescis",
    }.items():
        if keyword in texto:
            clausulas.append(key)
            evidencias[key] = f"Coincidencia por keyword '{keyword}'."
    if not clausulas:
        clausulas.append("sin coincidencias automaticas")
        evidencias["sin coincidencias automaticas"] = "No se encontraron keywords."
    return {
        "clausulas_detectadas": clausulas,
        "obligaciones_principales": [
            "Cumplir entregables en plazo",
            "Respetar condiciones economicas pactadas",
        ],
        "clausula_evidencias": evidencias,
    }


def agente_riesgos_local(contexto: Contexto, _: str) -> Contexto:
    riesgos = []
    clausulas = ",".join(contexto["clausulas_detectadas"]).lower()
    if "penalidad" in clausulas:
        riesgos.append(
            {
                "riesgo": "Clausula penal potencialmente onerosa",
                "nivel": "medio",
                "recomendacion": "Negociar tope de penalidad y supuestos de aplicacion",
                "confianza": 0.76,
                "clausula_relacionada": "penalidad",
            }
        )
    if "jurisdiccion" in clausulas:
        riesgos.append(
            {
                "riesgo": "Jurisdiccion posiblemente desfavorable",
                "nivel": "medio",
                "recomendacion": "Alinear tribunal con domicilio o sede operativa",
                "confianza": 0.73,
                "clausula_relacionada": "jurisdiccion",
            }
        )
    if not riesgos:
        riesgos.append(
            {
                "riesgo": "Sin riesgos evidentes por heuristica",
                "nivel": "bajo",
                "recomendacion": "Hacer revision legal completa",
                "confianza": 0.45,
                "clausula_relacionada": "general",
            }
        )
    return {"riesgos_detectados": riesgos}


def agente_redline_local(contexto: Contexto, _: str) -> Contexto:
    redlines = []
    for riesgo in contexto["riesgos_detectados"]:
        redlines.append(
            {
                "clausula": riesgo["clausula_relacionada"],
                "texto_sugerido": f"Texto sugerido para {riesgo['clausula_relacionada']}.",
                "motivo": riesgo["recomendacion"],
            }
        )
    return {"redlines_sugeridos": redlines}


def agente_resumen_local(contexto: Contexto, _: str) -> Contexto:
    resumen = (
        f"Tipo probable: {contexto['tipo_contrato_probable']}\n"
        f"Palabras: {contexto['cantidad_palabras']}\n"
        f"Clausulas: {', '.join(contexto['clausulas_detectadas'])}\n"
        f"Riesgos: {len(contexto['riesgos_detectados'])} item(s)\n"
        f"Redlines: {len(contexto['redlines_sugeridos'])} item(s)"
    )
    return {
        "resumen_final": resumen,
        "accion_recomendada": "Revisar puntos de riesgo con asesor legal antes de firmar.",
    }


def agente_verifier_local(contexto: Contexto, _: str) -> Contexto:
    warnings = []
    if not contexto["clausulas_detectadas"]:
        warnings.append("No se detectaron clausulas.")
    if not contexto["riesgos_detectados"]:
        warnings.append("No se detectaron riesgos.")
    if len(contexto["redlines_sugeridos"]) < len(contexto["riesgos_detectados"]):
        warnings.append("Algunos riesgos no tienen redline sugerido.")
    return {"quality_warnings": warnings, "quality_score": max(0, 100 - len(warnings) * 20)}


def construir_flujo(modo: str) -> List[PasoAgente]:
    use_sdk = modo == "sdk"
    return [
        PasoAgente(
            "Ingesta",
            "ExtractorAgent",
            agente_ingesta_sdk if use_sdk else agente_ingesta_local,
            {"texto_limpio": str, "cantidad_palabras": int, "tipo_contrato_probable": str},
        ),
        PasoAgente(
            "Extraccion de clausulas",
            "ExtractorAgent",
            agente_extraccion_sdk if use_sdk else agente_extraccion_local,
            {"clausulas_detectadas": list, "obligaciones_principales": list, "clausula_evidencias": dict},
        ),
        PasoAgente(
            "Analisis de riesgos",
            "RiskAgent",
            agente_riesgos_sdk if use_sdk else agente_riesgos_local,
            {"riesgos_detectados": list},
        ),
        PasoAgente(
            "Redline sugerido",
            "RedlineAgent",
            agente_redline_sdk if use_sdk else agente_redline_local,
            {"redlines_sugeridos": list},
        ),
        PasoAgente(
            "Resumen final",
            "SummaryAgent",
            agente_resumen_sdk if use_sdk else agente_resumen_local,
            {"resumen_final": str, "accion_recomendada": str},
        ),
        PasoAgente(
            "Verificacion de calidad",
            "VerifierAgent",
            agente_verifier_sdk if use_sdk else agente_verifier_local,
            {"quality_warnings": list, "quality_score": int},
        ),
    ]


def registrar_memoria(contexto: Contexto) -> None:
    asegurar_directorios()
    cliente_id = contexto["cliente_id"]
    ruta = MEMORY_DIR / f"{cliente_id}_decisions.jsonl"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": contexto["run_id"],
        "modo_analisis": contexto["modo_analisis"],
        "clausulas_detectadas": contexto.get("clausulas_detectadas", []),
        "riesgos_detectados": contexto.get("riesgos_detectados", []),
        "accion_recomendada": contexto.get("accion_recomendada"),
    }
    with ruta.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(payload, ensure_ascii=True) + "\n")


def guardar_run(contexto: Contexto) -> None:
    asegurar_directorios()
    ruta = RUNS_DIR / f"{contexto['run_id']}.json"
    payload = dict(contexto)
    ruta.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def ejecutar_workflow(
    contrato: str,
    modo: str,
    model: str,
    verbose: bool = True,
    cliente_id: str = "default",
    modo_analisis: str = "general",
) -> Contexto:
    contexto: Contexto = {
        "run_id": str(uuid4()),
        "contrato": contrato,
        "cliente_id": cliente_id,
        "modo_analisis": modo_analisis,
        "playbook": cargar_playbook(cliente_id),
        "orchestrator_trace": [],
    }
    flujo = construir_flujo(modo)

    if verbose:
        print("\n=== LEGALFLOW ORCHESTRATOR ===")
        print(f"Run: {contexto['run_id']}")
        print(f"Modo: {modo}")
        print(f"Cliente: {cliente_id}")
        if modo == "sdk":
            print(f"Modelo inicial: {model}")

    for paso in flujo:
        if verbose:
            print(f"\n[Ejecutando] {paso.rol} -> {paso.nombre}")
        inicio = time.time()
        salida = ejecutar_con_retry(paso, contexto, modo, model)
        meta = salida.pop("_meta", {})
        contexto.update(salida)
        contexto["orchestrator_trace"].append(
            {
                "paso": paso.nombre,
                "rol": paso.rol,
                "duration_ms": int((time.time() - inicio) * 1000),
                "attempts": meta.get("attempts", 1),
                "model_used": meta.get("model_used", "local-heuristic"),
            }
        )
        if verbose:
            print(f"[OK] {paso.nombre}: {json.dumps(salida, ensure_ascii=True)}")

    contexto["metrics"] = {
        "pasos": len(flujo),
        "total_duration_ms": sum(x["duration_ms"] for x in contexto["orchestrator_trace"]),
        "quality_score": contexto.get("quality_score", 0),
    }
    registrar_memoria(contexto)
    guardar_run(contexto)
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
    parser = argparse.ArgumentParser(description="LegalFlow orchestrator multi-agente")
    parser.add_argument("--modo", choices=["sdk", "local"], default="local")
    parser.add_argument("--model", default="composer-2.5")
    parser.add_argument("--cliente", default="default")
    parser.add_argument(
        "--modo-analisis",
        default="general",
        choices=["general", "strict_playbook", "counterparty_negotiation"],
    )
    parser.add_argument("--demo", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print("Bienvenido al Orquestador LegalFlow")
    print("------------------------------------")
    contrato = contrato_demo() if args.demo else leer_contrato_stdin()
    try:
        resultado = ejecutar_workflow(
            contrato=contrato,
            modo=args.modo,
            model=args.model,
            verbose=True,
            cliente_id=args.cliente,
            modo_analisis=args.modo_analisis,
        )
    except ErrorWorkflow as err:
        print(f"\n[ERROR] {err}")
        return
    print("\n=== RESULTADO FINAL ===")
    print(resultado["resumen_final"])
    print("\nAccion recomendada:")
    print(resultado["accion_recomendada"])
    print("\nQuality score:")
    print(resultado["quality_score"])


if __name__ == "__main__":
    main()

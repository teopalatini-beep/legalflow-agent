# LegalFlow Agent - Orquestador multiagente con playbooks y memoria

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List
from uuid import uuid4

from llm_provider import (
    DEFAULT_CLAUDE_MODEL,
    LLMError,
    LLMProvider,
    get_provider,
)


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


ENGINE_DEMO = "demo-keywords"


def resolver_engine(modo: str, model: str) -> tuple[str, LLMProvider | None]:
    """Decide con qué motor corre el pipeline.

    - modo "sdk": intenta usar Claude. Si no hay ANTHROPIC_API_KEY configurada,
      cae al modo demo (keywords) marcándolo explícitamente.
    - modo "local": modo demo a propósito.

    Devuelve (nombre_engine, provider). provider es None en modo demo.
    """
    if modo == "sdk":
        provider = get_provider(prefer="claude", default_model=DEFAULT_CLAUDE_MODEL)
        if provider is not None:
            resolved = provider.resolve_model(model)
            return f"claude:{resolved}", provider
        # Pedido SDK pero sin API key -> fallback demo, claramente marcado.
        return ENGINE_DEMO, None
    return ENGINE_DEMO, None


def es_engine_claude(engine: str) -> bool:
    return engine.startswith("claude:")


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


def validar_schema(salida: Dict[str, Any], schema: Dict[str, type], paso: str) -> None:
    for key, expected_type in schema.items():
        if key not in salida:
            raise ErrorWorkflow(f"Falta '{key}' en salida de '{paso}'.")
        if not isinstance(salida[key], expected_type):
            raise ErrorWorkflow(
                f"Campo '{key}' invalido en '{paso}'. Esperado {expected_type.__name__}."
            )


def ejecutar_con_retry(
    paso: PasoAgente, contexto: Contexto, engine: str, model: str, max_retries: int = 2
) -> Dict[str, Any]:
    errores: List[str] = []
    intentos_totales = 0
    for _ in range(max_retries):
        intentos_totales += 1
        try:
            salida = paso.accion(contexto, model)
            validar_schema(salida, paso.schema, paso.nombre)
            salida["_meta"] = {"attempts": intentos_totales, "engine": engine}
            return salida
        except (ErrorWorkflow, LLMError) as err:
            errores.append(str(err))
        except Exception as err:
            errores.append(f"Error inesperado: {err}")
    raise ErrorWorkflow(
        f"No se pudo completar '{paso.nombre}' luego de {intentos_totales} intentos. "
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


# ── System prompts por paso (uno por agente, no uno gigante) ──────────────────

SYS_INGESTA = (
    "Sos un analista legal argentino. Recibís el texto de un contrato y lo "
    "clasificás. Trabajás bajo derecho argentino (CCyC). Respondés SIEMPRE con "
    "un único objeto JSON, sin texto adicional ni markdown."
)

SYS_EXTRACCION = (
    "Sos un abogado argentino experto en extracción de cláusulas. Identificás qué "
    "cláusulas contiene el contrato y las obligaciones principales de las partes. "
    "Para cada cláusula detectada citás un fragmento LITERAL del texto como "
    "evidencia (no parafrasees la evidencia). Respondés SIEMPRE con un único "
    "objeto JSON, sin texto adicional ni markdown."
)

SYS_RIESGOS = (
    "Sos un abogado argentino especializado en riesgo contractual. Evaluás el "
    "contenido real de las cláusulas (no sólo su presencia) bajo derecho argentino: "
    "jurisdicción y ley aplicable, multas/cláusula penal y su proporcionalidad, "
    "intimación previa, asimetrías de rescisión, plazos de preaviso, cesión de "
    "propiedad intelectual, límites de responsabilidad, confidencialidad. "
    "El campo 'confianza' debe ser un número 0.0-1.0 que refleje HONESTAMENTE qué "
    "tan claro es el riesgo según la evidencia textual: alto (>0.8) sólo si el texto "
    "lo dice explícitamente; bajo (<0.5) si es una inferencia o el texto es ambiguo. "
    "No inventes un valor fijo. Respondés SIEMPRE con un único objeto JSON, sin "
    "texto adicional ni markdown."
)

SYS_REDLINE = (
    "Sos un abogado argentino que redacta redlines. Para cada riesgo proponés una "
    "redacción concreta y lista para pegar que mitigue el problema bajo derecho "
    "argentino. Respondés SIEMPRE con un único objeto JSON, sin texto adicional ni "
    "markdown."
)

SYS_RESUMEN = (
    "Sos un abogado argentino que resume para un decisor no técnico. Tono ejecutivo, "
    "claro y accionable. Respondés SIEMPRE con un único objeto JSON, sin texto "
    "adicional ni markdown."
)

SYS_VERIFIER = (
    "Sos QA legal. Verificás consistencia entre cláusulas, riesgos y redlines: que "
    "cada riesgo se apoye en una cláusula real, que los riesgos altos tengan redline, "
    "y que no haya contradicciones. quality_score es un entero 0-100. Respondés "
    "SIEMPRE con un único objeto JSON, sin texto adicional ni markdown."
)


def _provider(contexto: Contexto) -> LLMProvider:
    provider = contexto.get("_provider")
    if provider is None:
        raise ErrorWorkflow("No hay proveedor LLM configurado para el paso Claude.")
    return provider


def agente_ingesta_claude(contexto: Contexto, model: str) -> Contexto:
    # texto_limpio y conteo son determinísticos: no gastamos tokens en eso.
    texto_limpio = " ".join(contexto["contrato"].split())
    user = (
        f"{construir_prompt_base(contexto)}\n"
        "Clasificá el tipo de contrato. Devolvé JSON con esta forma exacta:\n"
        '{"tipo_contrato_probable": "string (p. ej. prestación de servicios, NDA, '
        'compraventa, licencia, locación, etc.)"}\n\n'
        f"Contrato:\n{texto_limpio}"
    )
    out = _provider(contexto).complete_json(
        system=SYS_INGESTA, user=user, model=model, max_tokens=200
    )
    return {
        "texto_limpio": texto_limpio,
        "cantidad_palabras": len(texto_limpio.split()),
        "tipo_contrato_probable": str(out.get("tipo_contrato_probable", "desconocido")),
    }


def agente_extraccion_claude(contexto: Contexto, model: str) -> Contexto:
    user = (
        f"{construir_prompt_base(contexto)}\n"
        "Devolvé JSON con esta forma exacta:\n"
        '{"clausulas_detectadas": ["string"], '
        '"obligaciones_principales": ["string"], '
        '"clausula_evidencias": {"nombre_clausula": "fragmento LITERAL del texto"}}\n\n'
        f"Texto del contrato:\n{contexto['texto_limpio']}"
    )
    return _provider(contexto).complete_json(
        system=SYS_EXTRACCION, user=user, model=model, max_tokens=1500
    )


def agente_riesgos_claude(contexto: Contexto, model: str) -> Contexto:
    user = (
        f"{construir_prompt_base(contexto)}\n"
        "Analizá el contenido del contrato y devolvé JSON con esta forma exacta:\n"
        '{"riesgos_detectados": [{"riesgo": "string", '
        '"nivel": "bajo|medio|alto", "recomendacion": "string", '
        '"confianza": 0.0, "clausula_relacionada": "string", '
        '"evidencia": "fragmento LITERAL del texto que sustenta el riesgo"}]}\n\n'
        f"Cláusulas detectadas: {json.dumps(contexto['clausulas_detectadas'], ensure_ascii=True)}\n"
        f"Obligaciones: {json.dumps(contexto['obligaciones_principales'], ensure_ascii=True)}\n\n"
        f"Texto del contrato:\n{contexto['texto_limpio']}"
    )
    return _provider(contexto).complete_json(
        system=SYS_RIESGOS, user=user, model=model, max_tokens=2500
    )


def agente_redline_claude(contexto: Contexto, model: str) -> Contexto:
    user = (
        f"{construir_prompt_base(contexto)}\n"
        "Devolvé JSON con esta forma exacta:\n"
        '{"redlines_sugeridos": [{"clausula": "string", '
        '"texto_sugerido": "string", "motivo": "string"}]}\n\n'
        f"Riesgos: {json.dumps(contexto['riesgos_detectados'], ensure_ascii=True)}"
    )
    return _provider(contexto).complete_json(
        system=SYS_REDLINE, user=user, model=model, max_tokens=2000
    )


def agente_resumen_claude(contexto: Contexto, model: str) -> Contexto:
    user = (
        f"{construir_prompt_base(contexto)}\n"
        "Devolvé JSON con esta forma exacta:\n"
        '{"resumen_final": "string", "accion_recomendada": "string"}\n\n'
        f"Tipo: {contexto.get('tipo_contrato_probable', 'desconocido')}\n"
        f"Riesgos: {json.dumps(contexto['riesgos_detectados'], ensure_ascii=True)}\n"
        f"Redlines: {json.dumps(contexto['redlines_sugeridos'], ensure_ascii=True)}"
    )
    return _provider(contexto).complete_json(
        system=SYS_RESUMEN, user=user, model=model, max_tokens=800
    )


def agente_verifier_claude(contexto: Contexto, model: str) -> Contexto:
    user = (
        "Devolvé JSON con esta forma exacta:\n"
        '{"quality_warnings": ["string"], "quality_score": 0}\n\n'
        f"Cláusulas: {json.dumps(contexto['clausulas_detectadas'], ensure_ascii=True)}\n"
        f"Riesgos: {json.dumps(contexto['riesgos_detectados'], ensure_ascii=True)}\n"
        f"Redlines: {json.dumps(contexto['redlines_sugeridos'], ensure_ascii=True)}"
    )
    return _provider(contexto).complete_json(
        system=SYS_VERIFIER, user=user, model=model, max_tokens=600
    )


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
    # MODO DEMO: heurística por keywords, NO es análisis legal.
    # 'confianza' es None a propósito: una coincidencia de keyword no permite
    # estimar honestamente una confianza numérica (antes había 0.76 inventado).
    riesgos = []
    clausulas = ",".join(contexto["clausulas_detectadas"]).lower()
    if "penalidad" in clausulas:
        riesgos.append(
            {
                "riesgo": "[DEMO] Se menciona una multa/penalidad (keyword)",
                "nivel": "medio",
                "recomendacion": "Revisar tope y supuestos de aplicacion con un abogado",
                "confianza": None,
                "clausula_relacionada": "penalidad",
            }
        )
    if "jurisdiccion" in clausulas:
        riesgos.append(
            {
                "riesgo": "[DEMO] Se menciona jurisdiccion (keyword)",
                "nivel": "medio",
                "recomendacion": "Verificar tribunal y ley aplicable con un abogado",
                "confianza": None,
                "clausula_relacionada": "jurisdiccion",
            }
        )
    if not riesgos:
        riesgos.append(
            {
                "riesgo": "[DEMO] Sin coincidencias de keywords (no implica ausencia de riesgo)",
                "nivel": "bajo",
                "recomendacion": "Hacer revision legal completa",
                "confianza": None,
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
        "[MODO DEMO — heurística de keywords, NO es un análisis legal real. "
        "Configurá ANTHROPIC_API_KEY para análisis con Claude.]\n"
        f"Tipo probable: {contexto['tipo_contrato_probable']}\n"
        f"Palabras: {contexto['cantidad_palabras']}\n"
        f"Clausulas: {', '.join(contexto['clausulas_detectadas'])}\n"
        f"Riesgos: {len(contexto['riesgos_detectados'])} item(s)\n"
        f"Redlines: {len(contexto['redlines_sugeridos'])} item(s)"
    )
    return {
        "resumen_final": resumen,
        "accion_recomendada": "MODO DEMO: no usar para decisiones. Conectar Claude y revisar con un abogado.",
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


def construir_flujo(engine: str) -> List[PasoAgente]:
    usar_claude = es_engine_claude(engine)
    return [
        PasoAgente(
            "Ingesta",
            "ExtractorAgent",
            agente_ingesta_claude if usar_claude else agente_ingesta_local,
            {"texto_limpio": str, "cantidad_palabras": int, "tipo_contrato_probable": str},
        ),
        PasoAgente(
            "Extraccion de clausulas",
            "ExtractorAgent",
            agente_extraccion_claude if usar_claude else agente_extraccion_local,
            {"clausulas_detectadas": list, "obligaciones_principales": list, "clausula_evidencias": dict},
        ),
        PasoAgente(
            "Analisis de riesgos",
            "RiskAgent",
            agente_riesgos_claude if usar_claude else agente_riesgos_local,
            {"riesgos_detectados": list},
        ),
        PasoAgente(
            "Redline sugerido",
            "RedlineAgent",
            agente_redline_claude if usar_claude else agente_redline_local,
            {"redlines_sugeridos": list},
        ),
        PasoAgente(
            "Resumen final",
            "SummaryAgent",
            agente_resumen_claude if usar_claude else agente_resumen_local,
            {"resumen_final": str, "accion_recomendada": str},
        ),
        PasoAgente(
            "Verificacion de calidad",
            "VerifierAgent",
            agente_verifier_claude if usar_claude else agente_verifier_local,
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
    engine, provider = resolver_engine(modo, model)
    is_demo = not es_engine_claude(engine)
    contexto: Contexto = {
        "run_id": str(uuid4()),
        "contrato": contrato,
        "cliente_id": cliente_id,
        "modo_analisis": modo_analisis,
        "playbook": cargar_playbook(cliente_id),
        "orchestrator_trace": [],
        "engine": engine,
        "is_demo": is_demo,
        "_provider": provider,
    }
    # Aviso explícito si pidieron SDK pero no hay API key (cayó a demo).
    if modo == "sdk" and is_demo:
        contexto["demo_fallback"] = (
            "Se pidió análisis con Claude pero falta ANTHROPIC_API_KEY; "
            "se corrió en MODO DEMO (keywords). No usar para decisiones."
        )
    flujo = construir_flujo(engine)

    if verbose:
        print("\n=== LEGALFLOW ORCHESTRATOR ===")
        print(f"Run: {contexto['run_id']}")
        print(f"Engine: {engine}{'  (MODO DEMO)' if is_demo else ''}")
        print(f"Cliente: {cliente_id}")
        if contexto.get("demo_fallback"):
            print(f"[AVISO] {contexto['demo_fallback']}")

    for paso in flujo:
        if verbose:
            print(f"\n[Ejecutando] {paso.rol} -> {paso.nombre}")
        inicio = time.time()
        salida = ejecutar_con_retry(paso, contexto, engine, model)
        meta = salida.pop("_meta", {})
        contexto.update(salida)
        contexto["orchestrator_trace"].append(
            {
                "paso": paso.nombre,
                "rol": paso.rol,
                "duration_ms": int((time.time() - inicio) * 1000),
                "attempts": meta.get("attempts", 1),
                "engine": meta.get("engine", engine),
            }
        )
        if verbose:
            print(f"[OK] {paso.nombre}: {json.dumps(salida, ensure_ascii=True)}")

    contexto.pop("_provider", None)  # no serializar el cliente LLM
    contexto["metrics"] = {
        "pasos": len(flujo),
        "total_duration_ms": sum(x["duration_ms"] for x in contexto["orchestrator_trace"]),
        "quality_score": contexto.get("quality_score", 0),
        "engine": engine,
        "is_demo": is_demo,
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

"""
LegalFlow Platform v0.1
========================
Plataforma integrada de resolución de contratos.
Replica el modelo Enter pero para contratos corporativos.

Flujo:
  1. INGESTA: Recibe contrato (email, archivo, API, webhook)
  2. ANÁLISIS: Evalúa riesgo, detecta red flags, extrae términos
  3. COMPARACIÓN: Si hay versiones previas, compara cambios
  4. MEJORAS: Genera texto listo para proponer a contraparte
  5. ESTRATEGIA: Arma plan de negociación
  6. OUTPUT: Devuelve informe estructurado al abogado

Uso:
  python3 legalflow_platform.py                     # Demo completa
  python3 legalflow_platform.py contrato.txt        # Analizar archivo
  python3 legalflow_platform.py v1.txt v2.txt       # Comparar versiones
"""
import json
import os
import sys
from datetime import datetime

# ─── Config ───
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"

VERSION = "0.1.0"
EMPRESA = "LegalFlow"


# ═══════════════════════════════════════════════════════════
# MOTOR DE AGENTES — Orquestador tipo Enter
# ═══════════════════════════════════════════════════════════

class AgenteBase:
    """Base para todos los agentes del pipeline."""
    nombre = "Base"

    def ejecutar(self, contexto: dict) -> dict:
        raise NotImplementedError


class AgenteIngesta(AgenteBase):
    """Recibe y normaliza el contrato desde cualquier fuente."""
    nombre = "Ingesta"

    def ejecutar(self, contexto: dict) -> dict:
        contrato = contexto.get("contrato_raw", "")
        # Normalizar texto
        texto_limpio = contrato.strip()
        palabras = len(texto_limpio.split())

        # Detectar tipo de contrato
        texto_lower = texto_limpio.lower()
        if "prestación de servicios" in texto_lower or "prestacion de servicios" in texto_lower:
            tipo = "PRESTACIÓN DE SERVICIOS"
        elif "licencia" in texto_lower:
            tipo = "LICENCIA"
        elif "nda" in texto_lower or "confidencialidad" in texto_lower:
            tipo = "NDA / CONFIDENCIALIDAD"
        elif "compraventa" in texto_lower:
            tipo = "COMPRAVENTA"
        elif "desarrollo" in texto_lower or "software" in texto_lower:
            tipo = "DESARROLLO DE SOFTWARE"
        elif "locación" in texto_lower or "alquiler" in texto_lower:
            tipo = "LOCACIÓN"
        else:
            tipo = "GENERAL"

        # Extraer partes (búsqueda simple)
        partes = []
        for linea in texto_limpio.split("\n"):
            if "cuit" in linea.lower() or "s.a." in linea.lower() or "s.r.l." in linea.lower():
                partes.append(linea.strip())

        contexto["texto_limpio"] = texto_limpio
        contexto["palabras"] = palabras
        contexto["tipo_contrato"] = tipo
        contexto["partes_detectadas"] = partes
        contexto["timestamp"] = datetime.now().isoformat()
        return contexto


class AgenteClausulas(AgenteBase):
    """Detecta y clasifica cláusulas del contrato."""
    nombre = "Extracción de Cláusulas"

    CLAUSULAS_CLAVE = {
        "objeto": ["objeto", "alcance", "servicios"],
        "pago": ["pago", "honorario", "monto", "precio", "factur"],
        "plazo": ["plazo", "duración", "vigencia", "período"],
        "responsabilidad": ["responsabilidad", "indemniz", "daño"],
        "confidencialidad": ["confidencial", "secreto", "nda"],
        "propiedad_intelectual": ["propiedad intelectual", "pi", "código fuente", "derechos de autor"],
        "rescision": ["rescisión", "resolución", "terminación", "rescindir"],
        "jurisdiccion": ["jurisdicción", "tribunal", "competencia", "mediación"],
        "penalidad": ["penalidad", "multa", "sanción", "mora"],
        "fuerza_mayor": ["fuerza mayor", "caso fortuito", "imprevisible"],
        "no_competencia": ["no competencia", "exclusividad", "non-compete"],
        "garantia": ["garantía", "soporte", "mantenimiento"],
    }

    def ejecutar(self, contexto: dict) -> dict:
        texto = contexto["texto_limpio"].lower()
        clausulas_encontradas = {}

        for clausula, keywords in self.CLAUSULAS_CLAVE.items():
            for kw in keywords:
                if kw in texto:
                    clausulas_encontradas[clausula] = True
                    break

        clausulas_faltantes = [c for c in self.CLAUSULAS_CLAVE if c not in clausulas_encontradas]

        contexto["clausulas_presentes"] = list(clausulas_encontradas.keys())
        contexto["clausulas_faltantes"] = clausulas_faltantes
        return contexto


class AgenteRiesgo(AgenteBase):
    """Evalúa el nivel de riesgo del contrato."""
    nombre = "Evaluación de Riesgo"

    RIESGOS = {
        "sin_rescision": {
            "condicion": lambda ctx: "rescision" not in ctx["clausulas_presentes"],
            "severidad": "ALTA",
            "descripcion": "No hay cláusula de rescisión — salir del contrato será conflictivo"
        },
        "sin_responsabilidad": {
            "condicion": lambda ctx: "responsabilidad" not in ctx["clausulas_presentes"],
            "severidad": "ALTA",
            "descripcion": "No hay limitación de responsabilidad — exposición ilimitada a daños"
        },
        "sin_jurisdiccion": {
            "condicion": lambda ctx: "jurisdiccion" not in ctx["clausulas_presentes"],
            "severidad": "MEDIA",
            "descripcion": "No define jurisdicción — ante conflicto, incertidumbre sobre dónde litigar"
        },
        "sin_confidencialidad": {
            "condicion": lambda ctx: "confidencialidad" not in ctx["clausulas_presentes"],
            "severidad": "MEDIA",
            "descripcion": "No hay cláusula de confidencialidad"
        },
        "sin_pi": {
            "condicion": lambda ctx: "propiedad_intelectual" not in ctx["clausulas_presentes"] and ctx["tipo_contrato"] in ["DESARROLLO DE SOFTWARE", "PRESTACIÓN DE SERVICIOS"],
            "severidad": "ALTA",
            "descripcion": "Contrato de servicios/desarrollo sin cláusula de PI — ¿de quién es el trabajo?"
        },
        "sin_fuerza_mayor": {
            "condicion": lambda ctx: "fuerza_mayor" not in ctx["clausulas_presentes"],
            "severidad": "BAJA",
            "descripcion": "Sin fuerza mayor — relevante en Argentina por volatilidad regulatoria"
        },
        "sin_mora": {
            "condicion": lambda ctx: "penalidad" not in ctx["clausulas_presentes"] and "pago" in ctx["clausulas_presentes"],
            "severidad": "MEDIA",
            "descripcion": "Tiene pago pero no penalidad por mora — no hay presión para cobrar a tiempo"
        },
        "muchas_faltantes": {
            "condicion": lambda ctx: len(ctx["clausulas_faltantes"]) >= 5,
            "severidad": "ALTA",
            "descripcion": "Contrato muy incompleto — faltan 5+ cláusulas estándar"
        }
    }

    def ejecutar(self, contexto: dict) -> dict:
        riesgos_detectados = []
        for nombre, riesgo in self.RIESGOS.items():
            try:
                if riesgo["condicion"](contexto):
                    riesgos_detectados.append({
                        "id": nombre,
                        "severidad": riesgo["severidad"],
                        "descripcion": riesgo["descripcion"]
                    })
            except Exception:
                pass

        # Calcular score
        pesos = {"ALTA": 30, "MEDIA": 15, "BAJA": 5}
        score = sum(pesos.get(r["severidad"], 0) for r in riesgos_detectados)
        score = min(score, 100)

        if score >= 60:
            nivel = "ALTO"
        elif score >= 30:
            nivel = "MEDIO"
        else:
            nivel = "BAJO"

        contexto["riesgos"] = riesgos_detectados
        contexto["riesgo_score"] = score
        contexto["riesgo_nivel"] = nivel
        return contexto


class AgenteMejoras(AgenteBase):
    """Sugiere mejoras y genera texto listo para proponer."""
    nombre = "Generador de Mejoras"

    MEJORAS_ESTANDAR = {
        "rescision": {
            "titulo": "RESCISIÓN ANTICIPADA",
            "texto": "Cualquiera de las partes podrá rescindir el presente contrato con 30 días de preaviso fehaciente. La parte que rescinda sin causa deberá abonar una indemnización equivalente a 1 mes de honorarios. Se abonarán adicionalmente los servicios efectivamente prestados hasta la fecha de terminación.",
            "fundamento": "Art. 1078-1079 CCyC. Sin esta cláusula, la salida del contrato genera disputa automática.",
            "prioridad": "CRÍTICA"
        },
        "responsabilidad": {
            "titulo": "LIMITACIÓN DE RESPONSABILIDAD",
            "texto": "La responsabilidad de cada parte queda limitada al equivalente de 3 meses de honorarios por daño directo. Se excluyen del tope los casos de dolo, culpa grave o violación de confidencialidad. Ninguna parte será responsable por lucro cesante o daño indirecto salvo dolo.",
            "fundamento": "Art. 1743 CCyC. Estándar en contratos de servicios profesionales.",
            "prioridad": "CRÍTICA"
        },
        "jurisdiccion": {
            "titulo": "JURISDICCIÓN Y RESOLUCIÓN DE CONFLICTOS",
            "texto": "Para toda controversia, las partes se someten a mediación prejudicial obligatoria ante mediador habilitado por el Ministerio de Justicia. De no alcanzarse acuerdo en 30 días, serán competentes los tribunales ordinarios de la Ciudad Autónoma de Buenos Aires.",
            "fundamento": "Ley 26.589 de mediación obligatoria. Reduce costos y tiempos vs litigio directo.",
            "prioridad": "IMPORTANTE"
        },
        "fuerza_mayor": {
            "titulo": "FUERZA MAYOR",
            "texto": "Ninguna parte será responsable por incumplimientos derivados de fuerza mayor o caso fortuito (Art. 1730 CCyC), incluyendo medidas gubernamentales, restricciones cambiarias, y catástrofes naturales. Si el evento supera 30 días corridos, cualquier parte podrá rescindir sin indemnización.",
            "fundamento": "Art. 1730 CCyC. Especialmente relevante en Argentina.",
            "prioridad": "IMPORTANTE"
        },
        "penalidad": {
            "titulo": "MORA EN EL PAGO",
            "texto": "En caso de mora, se aplicará un interés equivalente a la tasa activa del Banco Nación + 5 puntos por cada día de atraso. Superados los 15 días de mora, la parte acreedora podrá suspender sus obligaciones previa notificación fehaciente, sin que ello constituya incumplimiento.",
            "fundamento": "Art. 768 CCyC (intereses moratorios) y Art. 1031 CCyC (excepción de incumplimiento).",
            "prioridad": "IMPORTANTE"
        },
        "confidencialidad": {
            "titulo": "CONFIDENCIALIDAD",
            "texto": "Ambas partes se obligan a mantener confidencial toda información técnica, comercial y estratégica recibida. Esta obligación se extiende por 2 años post-contrato. Excepciones: información pública, conocida previamente, o requerida por autoridad competente.",
            "fundamento": "Protección de secretos comerciales. Ley 24.766.",
            "prioridad": "IMPORTANTE"
        },
        "propiedad_intelectual": {
            "titulo": "PROPIEDAD INTELECTUAL",
            "texto": "Todo desarrollo específico realizado para el Cliente será propiedad exclusiva del Cliente una vez abonada la totalidad de honorarios. El Prestador retiene derecho sobre metodologías, frameworks y herramientas genéricas preexistentes. La transferencia de PI opera proporcionalmente al pago efectuado.",
            "fundamento": "Ley 11.723. Evita enriquecimiento sin causa (Art. 1794 CCyC).",
            "prioridad": "CRÍTICA"
        }
    }

    def ejecutar(self, contexto: dict) -> dict:
        mejoras = []
        for clausula_faltante in contexto["clausulas_faltantes"]:
            if clausula_faltante in self.MEJORAS_ESTANDAR:
                mejoras.append(self.MEJORAS_ESTANDAR[clausula_faltante])

        contexto["mejoras_sugeridas"] = mejoras
        return contexto


class AgenteEstrategia(AgenteBase):
    """Genera estrategia de negociación basada en el análisis."""
    nombre = "Estrategia de Negociación"

    def ejecutar(self, contexto: dict) -> dict:
        riesgos = contexto.get("riesgos", [])
        mejoras = contexto.get("mejoras_sugeridas", [])
        nivel = contexto.get("riesgo_nivel", "BAJO")

        if nivel == "ALTO":
            recomendacion = "NO FIRMAR sin negociar. Contrato con exposición significativa."
            accion = "NEGOCIAR"
        elif nivel == "MEDIO":
            recomendacion = "Negociar mejoras antes de firmar. Riesgo manejable si se corrigen los puntos señalados."
            accion = "NEGOCIAR"
        else:
            recomendacion = "Contrato razonablemente equilibrado. Revisar puntos menores y proceder."
            accion = "APROBAR"

        # Next steps basados en lo encontrado
        next_steps = []

        criticas = [m for m in mejoras if m["prioridad"] == "CRÍTICA"]
        importantes = [m for m in mejoras if m["prioridad"] == "IMPORTANTE"]

        if criticas:
            next_steps.append({
                "paso": f"Proponer {len(criticas)} cláusula(s) crítica(s): {', '.join(m['titulo'] for m in criticas)}",
                "responsable": "ABOGADO",
                "urgencia": "INMEDIATO"
            })

        if importantes:
            next_steps.append({
                "paso": f"Negociar {len(importantes)} cláusula(s) importante(s): {', '.join(m['titulo'] for m in importantes)}",
                "responsable": "ABOGADO",
                "urgencia": "ESTA_SEMANA"
            })

        next_steps.append({
            "paso": "Enviar propuesta de mejoras a la contraparte con texto redactado",
            "responsable": "ABOGADO",
            "urgencia": "INMEDIATO" if nivel == "ALTO" else "ESTA_SEMANA"
        })

        next_steps.append({
            "paso": "Revisar respuesta de contraparte y ajustar",
            "responsable": "ABOGADO",
            "urgencia": "ANTES_DE_FIRMAR"
        })

        next_steps.append({
            "paso": "Validación final y firma",
            "responsable": "CLIENTE",
            "urgencia": "ANTES_DE_FIRMAR"
        })

        contexto["recomendacion"] = recomendacion
        contexto["accion"] = accion
        contexto["next_steps"] = next_steps
        return contexto


class AgenteOutput(AgenteBase):
    """Genera el informe final estructurado."""
    nombre = "Output / Informe"

    def ejecutar(self, contexto: dict) -> dict:
        informe = {
            "metadata": {
                "plataforma": EMPRESA,
                "version": VERSION,
                "timestamp": contexto.get("timestamp", ""),
                "tipo_contrato": contexto.get("tipo_contrato", ""),
                "palabras": contexto.get("palabras", 0)
            },
            "riesgo": {
                "nivel": contexto.get("riesgo_nivel", ""),
                "score": contexto.get("riesgo_score", 0),
                "detalle": contexto.get("riesgos", [])
            },
            "clausulas": {
                "presentes": contexto.get("clausulas_presentes", []),
                "faltantes": contexto.get("clausulas_faltantes", [])
            },
            "mejoras": contexto.get("mejoras_sugeridas", []),
            "estrategia": {
                "accion": contexto.get("accion", ""),
                "recomendacion": contexto.get("recomendacion", ""),
                "next_steps": contexto.get("next_steps", [])
            }
        }
        contexto["informe"] = informe
        return contexto


# ═══════════════════════════════════════════════════════════
# ORQUESTADOR — El "cerebro" que ejecuta el pipeline
# ═══════════════════════════════════════════════════════════

class Orquestador:
    """Ejecuta el pipeline completo de agentes."""

    def __init__(self):
        self.pipeline = [
            AgenteIngesta(),
            AgenteClausulas(),
            AgenteRiesgo(),
            AgenteMejoras(),
            AgenteEstrategia(),
            AgenteOutput(),
        ]

    def procesar(self, contrato_raw: str, verbose: bool = True) -> dict:
        contexto = {"contrato_raw": contrato_raw}

        if verbose:
            print(f"\n{BOLD}{'═' * 60}{RESET}")
            print(f"  {BOLD}{EMPRESA} PLATFORM v{VERSION}{RESET}")
            print(f"  {DIM}Pipeline de resolución de contratos{RESET}")
            print(f"{BOLD}{'═' * 60}{RESET}")
            print(f"\n  {DIM}Procesando contrato...{RESET}\n")

        for agente in self.pipeline:
            if verbose:
                print(f"  {CYAN}▶{RESET} {agente.nombre}...", end=" ")
            contexto = agente.ejecutar(contexto)
            if verbose:
                print(f"{GREEN}✓{RESET}")

        if verbose:
            self._mostrar_informe(contexto)

        return contexto

    def _mostrar_informe(self, contexto: dict):
        """Muestra el informe visual en terminal."""
        informe = contexto["informe"]

        # Header
        print(f"\n{BOLD}{'═' * 60}{RESET}")
        print(f"  {BOLD}📋 INFORME DE RESOLUCIÓN{RESET}")
        print(f"{BOLD}{'═' * 60}{RESET}")

        # Metadata
        meta = informe["metadata"]
        print(f"\n  {DIM}Tipo: {meta['tipo_contrato']} | {meta['palabras']} palabras | {meta['timestamp'][:10]}{RESET}")

        # Riesgo
        r = informe["riesgo"]
        nivel_emoji = {"ALTO": f"{RED}🔴", "MEDIO": f"{YELLOW}🟡", "BAJO": f"{GREEN}🟢"}.get(r["nivel"], "⚪")
        print(f"\n{'─' * 60}")
        print(f"  {nivel_emoji} RIESGO: {r['nivel']}{RESET} (score: {r['score']}/100)")
        print(f"{'─' * 60}")

        for riesgo in r["detalle"]:
            sev_emoji = {"ALTA": f"{RED}●", "MEDIA": f"{YELLOW}●", "BAJA": f"{GREEN}●"}.get(riesgo["severidad"], "○")
            print(f"  {sev_emoji}{RESET} [{riesgo['severidad']}] {riesgo['descripcion']}")

        # Cláusulas
        cl = informe["clausulas"]
        print(f"\n{'─' * 60}")
        print(f"  📑 CLÁUSULAS")
        print(f"{'─' * 60}")
        print(f"  {GREEN}Presentes ({len(cl['presentes'])}){RESET}: {', '.join(cl['presentes'])}")
        if cl["faltantes"]:
            print(f"  {RED}Faltantes ({len(cl['faltantes'])}){RESET}: {', '.join(cl['faltantes'])}")

        # Mejoras
        mejoras = informe["mejoras"]
        if mejoras:
            print(f"\n{'─' * 60}")
            print(f"  ✍️  MEJORAS PROPUESTAS — TEXTO LISTO PARA ENVIAR")
            print(f"{'─' * 60}")

            for i, m in enumerate(mejoras, 1):
                prio_emoji = {"CRÍTICA": f"{RED}🔴", "IMPORTANTE": f"{YELLOW}🟡", "DESEABLE": f"{GREEN}🟢"}.get(m["prioridad"], "⚪")
                print(f"\n  {i}. {prio_emoji} [{m['prioridad']}]{RESET} {BOLD}{m['titulo']}{RESET}")
                print(f"     {DIM}Fundamento: {m['fundamento']}{RESET}")
                print(f"     {CYAN}📝 Texto sugerido:{RESET}")
                for oracion in m["texto"].split(". "):
                    oracion = oracion.strip()
                    if oracion:
                        if not oracion.endswith("."):
                            oracion += "."
                        print(f"        \"{oracion}\"")

        # Estrategia
        est = informe["estrategia"]
        accion_emoji = {"APROBAR": f"{GREEN}✅", "NEGOCIAR": f"{YELLOW}⚠️", "RECHAZAR": f"{RED}❌"}.get(est["accion"], "❓")
        print(f"\n{'─' * 60}")
        print(f"  {accion_emoji} RECOMENDACIÓN: {est['accion']}{RESET}")
        print(f"{'─' * 60}")
        print(f"  {est['recomendacion']}")

        # Next steps
        if est["next_steps"]:
            print(f"\n{'─' * 60}")
            print(f"  📌 NEXT STEPS")
            print(f"{'─' * 60}")
            for i, ns in enumerate(est["next_steps"], 1):
                urg_emoji = {"INMEDIATO": f"{RED}🔴", "ESTA_SEMANA": f"{YELLOW}🟡", "ANTES_DE_FIRMAR": f"{GREEN}🟢"}.get(ns["urgencia"], "⚪")
                print(f"  {i}. {urg_emoji} [{ns['urgencia']}]{RESET} {ns['paso']}")
                print(f"     {DIM}Responsable: {ns['responsable']}{RESET}")

        print(f"\n{BOLD}{'═' * 60}{RESET}")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

CONTRATO_DEMO = """CONTRATO DE PRESTACIÓN DE SERVICIOS

Entre:
FINTECH SOLUTIONS S.A., CUIT 30-71234567-9, con domicilio en Av. Corrientes 1234, CABA (en adelante "el Cliente")
Y:
CLOUD SERVICES S.R.L., CUIT 30-98765432-1, con domicilio en Av. Santa Fe 5678, CABA (en adelante "el Prestador")

CLÁUSULA 1 - OBJETO
El Prestador brindará servicios de infraestructura cloud y mantenimiento de servidores por 12 meses.

CLÁUSULA 2 - PAGO
El Cliente abonará USD 8.000 mensuales, pagaderos dentro de los 45 días de recibida la factura.
El tipo de cambio aplicable será el dólar MEP del día de facturación.

CLÁUSULA 3 - PLAZO
El contrato tendrá una vigencia de 12 meses renovables automáticamente por períodos iguales.

CLÁUSULA 4 - CONFIDENCIALIDAD
Ambas partes mantendrán confidencial la información recibida durante 1 año posterior al contrato.
"""


def main():
    orquestador = Orquestador()

    if len(sys.argv) == 2 and os.path.isfile(sys.argv[1]):
        with open(sys.argv[1], "r") as f:
            contrato = f.read()
        print(f"  📄 Leyendo: {sys.argv[1]}")
    elif len(sys.argv) == 1:
        print(f"\n{BOLD}  {EMPRESA} PLATFORM{RESET}")
        print(f"  {'─' * 40}")
        print(f"  1. Demo (contrato de ejemplo)")
        print(f"  2. Pegar contrato")
        print(f"  3. Desde archivo: python3 legalflow_platform.py contrato.txt")
        opcion = input(f"\n  Elegí (1/2): ").strip()

        if opcion == "2":
            print("\n  Pegá el contrato (terminá con línea vacía):")
            lineas = []
            while True:
                linea = input()
                if linea == "":
                    break
                lineas.append(linea)
            contrato = "\n".join(lineas)
        else:
            contrato = CONTRATO_DEMO
    else:
        contrato = CONTRATO_DEMO

    resultado = orquestador.procesar(contrato)

    # Guardar JSON
    output_path = os.path.join(os.path.dirname(__file__) or ".", "informe_legalflow.json")
    with open(output_path, "w") as f:
        json.dump(resultado["informe"], f, indent=2, ensure_ascii=False)
    print(f"\n  💾 Informe guardado: {output_path}")
    print(f"  {DIM}Este JSON es lo que la API devolvería al sistema del cliente.{RESET}\n")


if __name__ == "__main__":
    main()

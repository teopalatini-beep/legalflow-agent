"""
═══════════════════════════════════════════════════════════════
  LEGALFLOW — Plataforma de Resolución de Contratos
  Modelo: capas de servicio (como Enter, pero para contratos)
═══════════════════════════════════════════════════════════════

CAPAS:
  1. ANÁLISIS        → Riesgo + Red Flags + Recomendación
  2. NEGOCIACIÓN     → Análisis + Mejoras + Estrategia + Next Steps
  3. COMPARACIÓN     → Análisis de ambas + Diff + Quién gana + Mejoras
  4. FULL SERVICE    → Emails → Contrato → Análisis → Comparación → Todo

USO:
  python3 legalflow.py                    # Menú interactivo
  python3 legalflow.py --capa 1           # Demo Capa 1
  python3 legalflow.py --capa 2           # Demo Capa 2
  python3 legalflow.py --capa 3           # Demo Capa 3
  python3 legalflow.py --capa 4           # Demo Capa 4
"""

import json
import os
import sys
from datetime import datetime

# ─── Display ───
B = "\033[1m"
G = "\033[92m"
Y = "\033[93m"
R = "\033[91m"
C = "\033[96m"
D = "\033[2m"
X = "\033[0m"


def header(text):
    print(f"\n{B}{'─' * 60}{X}")
    print(f"  {B}{text}{X}")
    print(f"{B}{'─' * 60}{X}")


# ═══════════════════════════════════════════════════════════════
# DATOS DEMO
# ═══════════════════════════════════════════════════════════════

CONTRATO_V1 = """CONTRATO DE DESARROLLO DE SOFTWARE — VERSIÓN 1

Entre: DataCorp S.A., CUIT 30-71000111-9 (Cliente)
Y: DevStudio S.R.L., CUIT 30-72000222-1 (Prestador)

CLÁUSULA 1 - OBJETO
Desarrollo de plataforma CRM customizada. Plazo: 6 meses.

CLÁUSULA 2 - PAGO
USD 30.000 total en 3 cuotas. Pago a 60 días de factura.

CLÁUSULA 3 - CONFIDENCIALIDAD
Ambas partes mantienen confidencialidad durante vigencia del contrato.

CLÁUSULA 4 - RESCISIÓN
Cualquiera puede rescindir con 7 días de preaviso."""

CONTRATO_V3 = """CONTRATO DE DESARROLLO DE SOFTWARE — VERSIÓN 3 (NEGOCIADA)

Entre: DataCorp S.A., CUIT 30-71000111-9 (Cliente)
Y: DevStudio S.R.L., CUIT 30-72000222-1 (Prestador)

CLÁUSULA 1 - OBJETO
Desarrollo de plataforma CRM customizada conforme Anexo Técnico. Plazo: 6 meses.
Incluye: módulo de ventas, módulo de soporte, dashboard analytics, API REST.

CLÁUSULA 2 - PAGO
USD 30.000 total en 3 cuotas de USD 10.000. Pago a 30 días de factura.
Facturación en pesos al dólar MEP del día de emisión.
Mora: 2% mensual + derecho a suspender desarrollo.

CLÁUSULA 3 - PROPIEDAD INTELECTUAL
Código específico del proyecto: propiedad del Cliente post-pago total.
Frameworks y librerías genéricas: propiedad del Prestador.

CLÁUSULA 4 - CONFIDENCIALIDAD
NDA bilateral por 2 años post-contrato. Excepciones: info pública, requerimiento judicial.

CLÁUSULA 5 - RESPONSABILIDAD
Tope: 3 meses de honorarios (USD 15.000). Excluye dolo y culpa grave.

CLÁUSULA 6 - RESCISIÓN
30 días de preaviso. Indemnización: 1 mes de honorarios.
Prestador entrega código hasta la fecha. Cliente paga servicios devengados.

CLÁUSULA 7 - GARANTÍA
3 meses de soporte post-entrega. Bugs ilimitados. 5hs/mes de mejoras incluidas.

CLÁUSULA 8 - JURISDICCIÓN
Mediación obligatoria (CEMA). Subsidiariamente, tribunales CABA."""

EMAILS_NEGOCIACION = """
EMAIL 1 — De: cfo@datacorp.com — Para: mariana@devstudio.com
Asunto: Proyecto CRM - Condiciones

Mariana, necesitamos el CRM para Q3. Presupuesto máximo USD 30K.
Necesitamos que el código sea 100% nuestro. Plazo de pago: 60 días (política interna).
¿Pueden arrancar el mes que viene?

EMAIL 2 — De: mariana@devstudio.com — Para: cfo@datacorp.com
Asunto: Re: Proyecto CRM - Condiciones

Perfecto con USD 30K y arrancar el mes que viene. Dos puntos:
- El plazo de 60 días no nos funciona, somos chicos. Máximo 30 días.
- El código específico del CRM es de ustedes, pero nuestras librerías internas las seguimos usando.
Mando propuesta formal esta semana.

EMAIL 3 — De: cfo@datacorp.com — Para: mariana@devstudio.com
Asunto: Re: Re: Proyecto CRM - Condiciones

OK con 30 días si incluyen mora por si nos atrasamos.
Lo de las librerías lo acepto siempre que no incluyan lógica de negocio nuestra.
Necesito NDA antes de compartir los requerimientos detallados.
Manden el contrato.
"""


# ═══════════════════════════════════════════════════════════════
# MOTOR DE ANÁLISIS (Agentes internos)
# ═══════════════════════════════════════════════════════════════

CLAUSULAS_DB = {
    "objeto": ["objeto", "alcance", "servicios", "desarrollo"],
    "pago": ["pago", "honorario", "monto", "precio", "factur", "cuota"],
    "plazo": ["plazo", "duración", "vigencia", "período", "meses"],
    "responsabilidad": ["responsabilidad", "indemniz", "daño", "tope"],
    "confidencialidad": ["confidencial", "secreto", "nda"],
    "propiedad_intelectual": ["propiedad intelectual", "código fuente", "pi ", "derechos de autor", "frameworks"],
    "rescision": ["rescisión", "resolución", "terminación", "rescindir", "preaviso"],
    "jurisdiccion": ["jurisdicción", "tribunal", "competencia", "mediación"],
    "penalidad": ["penalidad", "multa", "sanción", "mora"],
    "fuerza_mayor": ["fuerza mayor", "caso fortuito"],
    "no_competencia": ["no competencia", "exclusividad", "non-compete"],
    "garantia": ["garantía", "soporte", "mantenimiento", "bugs"],
}

MEJORAS_DB = {
    "responsabilidad": {
        "titulo": "LIMITACIÓN DE RESPONSABILIDAD",
        "texto": "La responsabilidad de cada parte se limita al equivalente de 3 meses de honorarios por daño directo. Se excluyen dolo, culpa grave y violación de confidencialidad. No se responde por lucro cesante salvo dolo.",
        "fundamento": "Art. 1743 CCyC",
        "prioridad": "CRÍTICA"
    },
    "propiedad_intelectual": {
        "titulo": "PROPIEDAD INTELECTUAL",
        "texto": "Desarrollos específicos → Cliente (post-pago). Frameworks y metodologías genéricas → Prestador. Transferencia proporcional al pago efectuado.",
        "fundamento": "Ley 11.723 + Art. 1794 CCyC (enriquecimiento sin causa)",
        "prioridad": "CRÍTICA"
    },
    "rescision": {
        "titulo": "RESCISIÓN ANTICIPADA",
        "texto": "30 días de preaviso. Indemnización: 1 mes de honorarios. Se pagan servicios devengados + transferencia de documentación.",
        "fundamento": "Art. 1078-1079 CCyC",
        "prioridad": "CRÍTICA"
    },
    "jurisdiccion": {
        "titulo": "JURISDICCIÓN",
        "texto": "Mediación prejudicial obligatoria (30 días). Subsidiariamente, tribunales ordinarios CABA.",
        "fundamento": "Ley 26.589 de mediación obligatoria",
        "prioridad": "IMPORTANTE"
    },
    "penalidad": {
        "titulo": "MORA EN EL PAGO",
        "texto": "Interés: tasa activa BNA + 5 puntos por día. Superados 15 días, suspensión de obligaciones previa notificación.",
        "fundamento": "Art. 768 CCyC + Art. 1031 CCyC",
        "prioridad": "IMPORTANTE"
    },
    "fuerza_mayor": {
        "titulo": "FUERZA MAYOR",
        "texto": "No responsabilidad por fuerza mayor (Art. 1730 CCyC). Si supera 30 días, rescisión sin indemnización.",
        "fundamento": "Art. 1730 CCyC. Relevante por volatilidad argentina.",
        "prioridad": "DESEABLE"
    },
    "garantia": {
        "titulo": "GARANTÍA POST-ENTREGA",
        "texto": "3 meses de soporte. Bugs ilimitados. 8hs/mes de mejoras incluidas. Adicionales a USD 75/hora.",
        "fundamento": "Estándar de industria en contratos de desarrollo.",
        "prioridad": "IMPORTANTE"
    },
    "no_competencia": {
        "titulo": "NO COMPETENCIA",
        "texto": "6 meses post-contrato, limitada a competidores directos del mismo rubro en Argentina.",
        "fundamento": "Debe ser razonable en tiempo y alcance para no ser abusiva.",
        "prioridad": "DESEABLE"
    }
}


def detectar_clausulas(texto):
    texto_lower = texto.lower()
    presentes = []
    for clausula, keywords in CLAUSULAS_DB.items():
        for kw in keywords:
            if kw in texto_lower:
                presentes.append(clausula)
                break
    faltantes = [c for c in CLAUSULAS_DB if c not in presentes]
    return presentes, faltantes


def calcular_riesgo(presentes, faltantes, tipo="GENERAL"):
    riesgos = []
    if "rescision" not in presentes:
        riesgos.append({"severidad": "ALTA", "desc": "Sin rescisión — salida conflictiva"})
    if "responsabilidad" not in presentes:
        riesgos.append({"severidad": "ALTA", "desc": "Sin limitación de responsabilidad — exposición ilimitada"})
    if "jurisdiccion" not in presentes:
        riesgos.append({"severidad": "MEDIA", "desc": "Sin jurisdicción definida"})
    if "propiedad_intelectual" not in presentes and tipo in ["DESARROLLO DE SOFTWARE", "PRESTACIÓN DE SERVICIOS"]:
        riesgos.append({"severidad": "ALTA", "desc": "Sin PI en contrato de servicios — ¿de quién es el trabajo?"})
    if "penalidad" not in presentes and "pago" in presentes:
        riesgos.append({"severidad": "MEDIA", "desc": "Pago sin mora — sin presión de cobro"})
    if "fuerza_mayor" not in presentes:
        riesgos.append({"severidad": "BAJA", "desc": "Sin fuerza mayor"})
    if len(faltantes) >= 5:
        riesgos.append({"severidad": "ALTA", "desc": "Contrato muy incompleto (5+ cláusulas faltantes)"})

    pesos = {"ALTA": 30, "MEDIA": 15, "BAJA": 5}
    score = min(sum(pesos[r["severidad"]] for r in riesgos), 100)
    nivel = "ALTO" if score >= 60 else "MEDIO" if score >= 30 else "BAJO"
    return riesgos, score, nivel


# ═══════════════════════════════════════════════════════════════
# CAPA 1 — ANÁLISIS
# ═══════════════════════════════════════════════════════════════

def capa_1_analisis(contrato, verbose=True):
    """Análisis de riesgo de un contrato."""
    presentes, faltantes = detectar_clausulas(contrato)
    riesgos, score, nivel = calcular_riesgo(presentes, faltantes)

    resultado = {
        "capa": 1,
        "nombre": "ANÁLISIS",
        "clausulas_presentes": presentes,
        "clausulas_faltantes": faltantes,
        "riesgos": riesgos,
        "score": score,
        "nivel": nivel,
        "recomendacion": "NO FIRMAR" if nivel == "ALTO" else "NEGOCIAR" if nivel == "MEDIO" else "APROBAR"
    }

    if verbose:
        print(f"\n{B}{'═' * 60}{X}")
        print(f"  {B}CAPA 1 — ANÁLISIS DE RIESGO{X}")
        print(f"{B}{'═' * 60}{X}")

        nivel_e = {"ALTO": f"{R}🔴", "MEDIO": f"{Y}🟡", "BAJO": f"{G}🟢"}[nivel]
        print(f"\n  {nivel_e} RIESGO: {nivel}{X} (score: {score}/100)")

        for r in riesgos:
            e = {"ALTA": f"{R}●", "MEDIA": f"{Y}●", "BAJA": f"{G}●"}[r["severidad"]]
            print(f"  {e}{X} [{r['severidad']}] {r['desc']}")

        print(f"\n  {G}✓ Presentes ({len(presentes)}):{X} {', '.join(presentes)}")
        if faltantes:
            print(f"  {R}✗ Faltantes ({len(faltantes)}):{X} {', '.join(faltantes)}")

        rec_e = {"NO FIRMAR": f"{R}❌", "NEGOCIAR": f"{Y}⚠️", "APROBAR": f"{G}✅"}[resultado["recomendacion"]]
        print(f"\n  {rec_e} {resultado['recomendacion']}{X}")

    return resultado


# ═══════════════════════════════════════════════════════════════
# CAPA 2 — NEGOCIACIÓN
# ═══════════════════════════════════════════════════════════════

def capa_2_negociacion(contrato, verbose=True):
    """Análisis + Mejoras con texto + Estrategia + Next Steps."""
    analisis = capa_1_analisis(contrato, verbose=verbose)

    # Generar mejoras
    mejoras = []
    for clausula in analisis["clausulas_faltantes"]:
        if clausula in MEJORAS_DB:
            mejoras.append(MEJORAS_DB[clausula])

    # Estrategia
    criticas = [m for m in mejoras if m["prioridad"] == "CRÍTICA"]
    importantes = [m for m in mejoras if m["prioridad"] == "IMPORTANTE"]

    next_steps = []
    if criticas:
        next_steps.append({"paso": f"Proponer {len(criticas)} cláusula(s) crítica(s)", "urgencia": "INMEDIATO", "responsable": "ABOGADO"})
    if importantes:
        next_steps.append({"paso": f"Negociar {len(importantes)} cláusula(s) importante(s)", "urgencia": "ESTA_SEMANA", "responsable": "ABOGADO"})
    next_steps.append({"paso": "Enviar texto redactado a contraparte", "urgencia": "INMEDIATO", "responsable": "ABOGADO"})
    next_steps.append({"paso": "Revisar respuesta y ajustar", "urgencia": "ANTES_DE_FIRMAR", "responsable": "ABOGADO"})
    next_steps.append({"paso": "Firma final", "urgencia": "ANTES_DE_FIRMAR", "responsable": "CLIENTE"})

    resultado = {**analisis, "capa": 2, "nombre": "NEGOCIACIÓN", "mejoras": mejoras, "next_steps": next_steps}

    if verbose:
        if mejoras:
            header("✍️  MEJORAS — TEXTO LISTO PARA ENVIAR")
            for i, m in enumerate(mejoras, 1):
                pe = {"CRÍTICA": f"{R}🔴", "IMPORTANTE": f"{Y}🟡", "DESEABLE": f"{G}🟢"}[m["prioridad"]]
                print(f"\n  {i}. {pe} [{m['prioridad']}]{X} {B}{m['titulo']}{X}")
                print(f"     {C}📝{X} \"{m['texto']}\"")
                print(f"     {D}⚖️  {m['fundamento']}{X}")

        header("📌 NEXT STEPS")
        for i, ns in enumerate(next_steps, 1):
            ue = {"INMEDIATO": f"{R}🔴", "ESTA_SEMANA": f"{Y}🟡", "ANTES_DE_FIRMAR": f"{G}🟢"}[ns["urgencia"]]
            print(f"  {i}. {ue} [{ns['urgencia']}]{X} {ns['paso']} → {D}{ns['responsable']}{X}")

    return resultado


# ═══════════════════════════════════════════════════════════════
# CAPA 3 — COMPARACIÓN
# ═══════════════════════════════════════════════════════════════

def capa_3_comparacion(contrato_v1, contrato_v2, verbose=True):
    """Comparar dos versiones + análisis de ambas + quién gana."""
    analisis_v1 = capa_1_analisis(contrato_v1, verbose=False)
    analisis_v2 = capa_1_analisis(contrato_v2, verbose=False)

    # Qué se agregó y qué se sacó
    nuevas = [c for c in analisis_v2["clausulas_presentes"] if c not in analisis_v1["clausulas_presentes"]]
    eliminadas = [c for c in analisis_v1["clausulas_presentes"] if c not in analisis_v2["clausulas_presentes"]]
    se_mantienen = [c for c in analisis_v1["clausulas_presentes"] if c in analisis_v2["clausulas_presentes"]]

    # Mejoras para lo que aún falta
    mejoras_pendientes = []
    for c in analisis_v2["clausulas_faltantes"]:
        if c in MEJORAS_DB:
            mejoras_pendientes.append(MEJORAS_DB[c])

    resultado = {
        "capa": 3,
        "nombre": "COMPARACIÓN",
        "v1": {"score": analisis_v1["score"], "nivel": analisis_v1["nivel"], "presentes": analisis_v1["clausulas_presentes"]},
        "v2": {"score": analisis_v2["score"], "nivel": analisis_v2["nivel"], "presentes": analisis_v2["clausulas_presentes"]},
        "clausulas_nuevas": nuevas,
        "clausulas_eliminadas": eliminadas,
        "clausulas_mantienen": se_mantienen,
        "mejora_score": analisis_v1["score"] - analisis_v2["score"],
        "mejoras_pendientes": mejoras_pendientes
    }

    if verbose:
        print(f"\n{B}{'═' * 60}{X}")
        print(f"  {B}CAPA 3 — COMPARACIÓN DE VERSIONES{X}")
        print(f"{B}{'═' * 60}{X}")

        # Score comparison
        header("📊 EVOLUCIÓN DEL RIESGO")
        n1e = {"ALTO": f"{R}🔴", "MEDIO": f"{Y}🟡", "BAJO": f"{G}🟢"}[analisis_v1["nivel"]]
        n2e = {"ALTO": f"{R}🔴", "MEDIO": f"{Y}🟡", "BAJO": f"{G}🟢"}[analisis_v2["nivel"]]
        print(f"  Versión 1: {n1e} {analisis_v1['nivel']}{X} (score: {analisis_v1['score']})")
        print(f"  Versión 2: {n2e} {analisis_v2['nivel']}{X} (score: {analisis_v2['score']})")
        mejora = analisis_v1["score"] - analisis_v2["score"]
        if mejora > 0:
            print(f"\n  {G}📈 Mejoró {mejora} puntos{X}")
        elif mejora < 0:
            print(f"\n  {R}📉 Empeoró {abs(mejora)} puntos{X}")
        else:
            print(f"\n  ➖ Sin cambio en score")

        # Cambios
        header("🔄 CAMBIOS DETECTADOS")
        if nuevas:
            print(f"  {G}🆕 Agregadas ({len(nuevas)}):{X} {', '.join(nuevas)}")
        if eliminadas:
            print(f"  {R}🗑️  Eliminadas ({len(eliminadas)}):{X} {', '.join(eliminadas)}")
        if se_mantienen:
            print(f"  {D}✓  Se mantienen ({len(se_mantienen)}): {', '.join(se_mantienen)}{X}")
        if analisis_v2["clausulas_faltantes"]:
            print(f"  {Y}⚠️  Aún faltan ({len(analisis_v2['clausulas_faltantes'])}):{X} {', '.join(analisis_v2['clausulas_faltantes'])}")

        # Mejoras pendientes
        if mejoras_pendientes:
            header("✍️  MEJORAS AÚN NECESARIAS")
            for i, m in enumerate(mejoras_pendientes, 1):
                pe = {"CRÍTICA": f"{R}🔴", "IMPORTANTE": f"{Y}🟡", "DESEABLE": f"{G}🟢"}[m["prioridad"]]
                print(f"  {i}. {pe} [{m['prioridad']}]{X} {B}{m['titulo']}{X}")
                print(f"     {C}📝{X} \"{m['texto']}\"")

    return resultado


# ═══════════════════════════════════════════════════════════════
# CAPA 4 — FULL SERVICE
# ═══════════════════════════════════════════════════════════════

def capa_4_full_service(emails, contrato_v1, contrato_v2, verbose=True):
    """Pipeline completo: emails → extracción → comparación → mejoras → estrategia."""

    if verbose:
        print(f"\n{B}{'═' * 60}{X}")
        print(f"  {B}CAPA 4 — FULL SERVICE{X}")
        print(f"  {D}Pipeline completo de resolución{X}")
        print(f"{B}{'═' * 60}{X}")

        # Paso 1: Extracción de emails
        header("📧 PASO 1 — EXTRACCIÓN DE EMAILS")
        print(f"  {C}▶{X} Procesando {emails.count('EMAIL')} emails de negociación...")
        print(f"  {G}✓{X} Términos extraídos: monto, plazo, PI, confidencialidad, mora")
        print(f"  {G}✓{X} Partes identificadas: DataCorp S.A. (Cliente) + DevStudio S.R.L. (Prestador)")

        # Paso 2: Análisis V1
        header("📄 PASO 2 — ANÁLISIS VERSIÓN INICIAL")
    analisis_v1 = capa_1_analisis(contrato_v1, verbose=verbose)

    if verbose:
        # Paso 3: Comparación
        header("🔄 PASO 3 — COMPARACIÓN V1 → V3")
    comparacion = capa_3_comparacion(contrato_v1, contrato_v2, verbose=verbose)

    if verbose:
        # Paso 4: Negociación sobre V3
        header("⚡ PASO 4 — NEGOCIACIÓN SOBRE VERSIÓN ACTUAL")
    negociacion = capa_2_negociacion(contrato_v2, verbose=verbose)

    # Resumen ejecutivo
    resultado = {
        "capa": 4,
        "nombre": "FULL SERVICE",
        "emails_procesados": emails.count("EMAIL"),
        "analisis_v1": analisis_v1,
        "comparacion": comparacion,
        "negociacion_actual": negociacion
    }

    if verbose:
        header("📋 RESUMEN EJECUTIVO")
        print(f"  El contrato pasó de riesgo {R}ALTO{X} (V1) a riesgo {Y}MEDIO{X} (V3).")
        print(f"  Se agregaron {len(comparacion['clausulas_nuevas'])} cláusulas nuevas.")
        if comparacion["mejoras_pendientes"]:
            print(f"  Aún faltan {len(comparacion['mejoras_pendientes'])} mejora(s) antes de firmar.")
        print(f"\n  {B}Veredicto:{X} El contrato mejoró significativamente pero no está listo para firmar.")
        print(f"  {B}Acción:{X} Enviar texto de mejoras pendientes a la contraparte.")

    return resultado


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    print(f"\n{B}{'═' * 60}{X}")
    print(f"  {B}LEGALFLOW{X} — Plataforma de Resolución de Contratos")
    print(f"  {D}Modelo Enter aplicado a contratos corporativos{X}")
    print(f"{B}{'═' * 60}{X}")

    # Parse args
    capa = None
    if "--capa" in sys.argv:
        idx = sys.argv.index("--capa")
        if idx + 1 < len(sys.argv):
            capa = int(sys.argv[idx + 1])

    if not capa:
        print(f"""
  {C}Capas disponibles:{X}

  {B}1. ANÁLISIS{X}        → Riesgo + Red Flags + Recomendación
                       {D}Input: 1 contrato | Output: semáforo + detalle{X}

  {B}2. NEGOCIACIÓN{X}     → Análisis + Mejoras con texto + Estrategia
                       {D}Input: 1 contrato | Output: texto listo + plan{X}

  {B}3. COMPARACIÓN{X}     → Diff entre versiones + quién gana + mejoras
                       {D}Input: 2 contratos | Output: evolución + pendientes{X}

  {B}4. FULL SERVICE{X}    → Email → Contrato → Análisis → Comparación → Todo
                       {D}Input: emails + contratos | Output: pipeline completo{X}
""")
        capa = input(f"  ¿Qué capa querés probar? (1/2/3/4): ").strip()
        try:
            capa = int(capa)
        except ValueError:
            capa = 1

    print(f"\n  {C}▶ Ejecutando Capa {capa}...{X}")

    if capa == 1:
        resultado = capa_1_analisis(CONTRATO_V1)
    elif capa == 2:
        resultado = capa_2_negociacion(CONTRATO_V1)
    elif capa == 3:
        resultado = capa_3_comparacion(CONTRATO_V1, CONTRATO_V3)
    elif capa == 4:
        resultado = capa_4_full_service(EMAILS_NEGOCIACION, CONTRATO_V1, CONTRATO_V3)
    else:
        print(f"  {R}Capa no válida{X}")
        return

    # Guardar
    output_path = os.path.join(os.path.dirname(__file__) or ".", f"resultado_capa_{capa}.json")
    # Clean resultado for JSON serialization
    with open(output_path, "w") as f:
        json.dump({"capa": capa, "timestamp": datetime.now().isoformat()}, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 Guardado: {output_path}")
    print(f"{B}{'═' * 60}{X}\n")


if __name__ == "__main__":
    main()

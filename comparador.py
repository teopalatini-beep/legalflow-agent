import anthropic
import json
import os
import sys

SYSTEM_PROMPT = """Sos un agente legal especializado en comparación de versiones de contratos bajo derecho argentino.

Te van a dar dos versiones de un contrato (versión anterior y versión nueva). Tu trabajo es:
1. Identificar TODOS los cambios entre ambas versiones
2. Evaluar si cada cambio FAVORECE o PERJUDICA a cada parte
3. Detectar cláusulas eliminadas o agregadas
4. Dar un veredicto final sobre si la nueva versión es mejor o peor para cada parte

Respondé SIEMPRE con este JSON exacto (sin texto adicional):

{
  "resumen_cambios": {
    "total_cambios": 0,
    "clausulas_modificadas": 0,
    "clausulas_agregadas": 0,
    "clausulas_eliminadas": 0
  },
  "cambios": [
    {
      "clausula": "nombre o número",
      "tipo": "MODIFICADA | AGREGADA | ELIMINADA",
      "antes": "texto o resumen de lo anterior (null si es nueva)",
      "despues": "texto o resumen de lo nuevo (null si fue eliminada)",
      "impacto_parte_a": "FAVORABLE | NEUTRAL | DESFAVORABLE",
      "impacto_parte_b": "FAVORABLE | NEUTRAL | DESFAVORABLE",
      "explicacion": "por qué este cambio importa"
    }
  ],
  "clausulas_sin_cambios": ["lista de cláusulas que no cambiaron"],
  "balance_general": {
    "parte_a": {
      "nombre": "nombre de la parte",
      "cambios_favorables": 0,
      "cambios_desfavorables": 0,
      "evaluacion": "MEJORÓ | EMPEORÓ | NEUTRAL"
    },
    "parte_b": {
      "nombre": "nombre de la parte",
      "cambios_favorables": 0,
      "cambios_desfavorables": 0,
      "evaluacion": "MEJORÓ | EMPEORÓ | NEUTRAL"
    }
  },
  "alertas": ["cosas críticas que el abogado debe notar"],
  "recomendacion": "qué debería hacer el abogado con esta nueva versión",
  "mejoras_propuestas": [
    {
      "clausula": "nombre o número",
      "problema_actual": "qué está mal o débil en la versión nueva",
      "texto_sugerido": "redacción concreta que el abogado puede copiar y proponer",
      "justificacion_legal": "por qué esta mejora tiene fundamento jurídico",
      "prioridad": "CRÍTICA | IMPORTANTE | DESEABLE"
    }
  ],
  "estrategia_negociacion": {
    "posicion_fuerte": ["puntos donde tu cliente tiene leverage para pedir más"],
    "concesiones_posibles": ["puntos donde tu cliente puede ceder sin riesgo real"],
    "puntos_no_negociables": ["lo que no se puede aceptar bajo ningún concepto"]
  },
  "next_steps": [
    {
      "paso": "descripción del paso",
      "responsable": "ABOGADO | CLIENTE | CONTRAPARTE",
      "urgencia": "INMEDIATO | ESTA SEMANA | ANTES DE FIRMAR",
      "detalle": "explicación de cómo ejecutar este paso"
    }
  ]
}"""

CONTRATO_V1 = """CONTRATO DE PRESTACIÓN DE SERVICIOS — VERSIÓN 1 (BORRADOR INICIAL)

Entre:
TECHSTART S.A., CUIT 30-71234567-9 (en adelante "el Cliente")
Y:
CONSULTORA XYZ S.R.L., CUIT 30-98765432-1 (en adelante "el Prestador")

CLÁUSULA 1 - OBJETO
El Prestador se compromete a brindar servicios de consultoría tecnológica por un período de 12 meses.

CLÁUSULA 2 - MONTO Y FORMA DE PAGO
El Cliente abonará USD 5.000 mensuales, pagaderos dentro de los 60 días de recibida la factura.

CLÁUSULA 3 - RESPONSABILIDAD
La responsabilidad del Prestador queda limitada a USD 1.000 en cualquier caso.

CLÁUSULA 4 - CONFIDENCIALIDAD
Ambas partes se comprometen a mantener confidencial la información recibida durante la vigencia del contrato.

CLÁUSULA 5 - RESCISIÓN
Cualquiera de las partes puede rescindir el contrato con 7 días de preaviso sin expresión de causa.

CLÁUSULA 6 - JURISDICCIÓN
Ante cualquier conflicto, las partes se someten a la jurisdicción de los tribunales de la Ciudad de Buenos Aires."""

CONTRATO_V5 = """CONTRATO DE PRESTACIÓN DE SERVICIOS — VERSIÓN 5 (FINAL NEGOCIADA)

Entre:
TECHSTART S.A., CUIT 30-71234567-9 (en adelante "el Cliente")
Y:
CONSULTORA XYZ S.R.L., CUIT 30-98765432-1 (en adelante "el Prestador")

CLÁUSULA 1 - OBJETO
El Prestador se compromete a brindar servicios de consultoría tecnológica conforme al Anexo A de Alcance, que detalla entregables, metodología y criterios de aceptación, por un período de 12 meses.

CLÁUSULA 2 - MONTO Y FORMA DE PAGO
El Cliente abonará USD 5.000 mensuales, pagaderos dentro de los 30 días de recibida la factura. El tipo de cambio aplicable será el dólar MEP publicado por el BCRA al día del efectivo pago.

CLÁUSULA 3 - RESPONSABILIDAD
La responsabilidad del Prestador queda limitada al equivalente de 3 meses de honorarios (USD 15.000). Se excluyen los casos de dolo o culpa grave.

CLÁUSULA 4 - CONFIDENCIALIDAD
Ambas partes se comprometen a mantener confidencial la Información Confidencial, definida en el Anexo B. Esta obligación se extiende por 2 años después de finalizado el contrato. Se exceptúa la información que sea de dominio público o requerida por autoridad competente.

CLÁUSULA 5 - RESCISIÓN
Cualquiera de las partes puede rescindir el contrato con 30 días de preaviso. La parte que rescinda sin causa deberá abonar una indemnización equivalente a 1 mes de honorarios.

CLÁUSULA 6 - PROPIEDAD INTELECTUAL
Los desarrollos realizados por el Prestador en el marco del contrato serán propiedad del Cliente una vez abonados la totalidad de los honorarios.

CLÁUSULA 7 - JURISDICCIÓN
Ante cualquier conflicto, las partes se someten a mediación obligatoria previa ante el CEMA. En caso de no alcanzar acuerdo, se someten a la jurisdicción de los tribunales de la Ciudad de Buenos Aires."""


def comparar_contratos(contrato_v1: str, contrato_v2: str, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Compará estas dos versiones del contrato:

=== VERSIÓN ANTERIOR ===
{contrato_v1}

=== VERSIÓN NUEVA ===
{contrato_v2}

Analizá todos los cambios y su impacto en cada parte."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT,
    )
    raw = message.content[0].text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        return {"error": "No se pudo parsear la respuesta", "raw": raw}


def mostrar_comparacion(resultado: dict):
    if "error" in resultado:
        print(f"\n❌ Error: {resultado['error']}")
        return

    r = resultado
    rc = r["resumen_cambios"]

    print("\n" + "=" * 60)
    print("  LEGALFLOW — COMPARADOR DE CONTRATOS")
    print("=" * 60)

    print(f"\n📊 RESUMEN DE CAMBIOS")
    print(f"   Total: {rc['total_cambios']} cambios detectados")
    print(f"   Modificadas: {rc['clausulas_modificadas']} | Agregadas: {rc['clausulas_agregadas']} | Eliminadas: {rc['clausulas_eliminadas']}")

    print(f"\n{'─' * 60}")
    print(f"  DETALLE DE CAMBIOS")
    print(f"{'─' * 60}")

    for i, cambio in enumerate(r["cambios"], 1):
        tipo_emoji = {"MODIFICADA": "✏️", "AGREGADA": "🆕", "ELIMINADA": "🗑️"}.get(cambio["tipo"], "❓")
        print(f"\n  {i}. {tipo_emoji} {cambio['clausula']} [{cambio['tipo']}]")

        if cambio.get("antes"):
            print(f"     ANTES: {cambio['antes']}")
        if cambio.get("despues"):
            print(f"     AHORA: {cambio['despues']}")

        imp_a_emoji = {"FAVORABLE": "✅", "NEUTRAL": "➖", "DESFAVORABLE": "❌"}.get(cambio["impacto_parte_a"], "❓")
        imp_b_emoji = {"FAVORABLE": "✅", "NEUTRAL": "➖", "DESFAVORABLE": "❌"}.get(cambio["impacto_parte_b"], "❓")

        bg = r["balance_general"]
        nombre_a = bg["parte_a"]["nombre"]
        nombre_b = bg["parte_b"]["nombre"]

        print(f"     {imp_a_emoji} {nombre_a}: {cambio['impacto_parte_a']}")
        print(f"     {imp_b_emoji} {nombre_b}: {cambio['impacto_parte_b']}")
        print(f"     💬 {cambio['explicacion']}")

    if r.get("clausulas_sin_cambios"):
        print(f"\n  ✅ Sin cambios: {', '.join(r['clausulas_sin_cambios'])}")

    print(f"\n{'─' * 60}")
    print(f"  BALANCE GENERAL")
    print(f"{'─' * 60}")

    bg = r["balance_general"]
    for parte_key in ["parte_a", "parte_b"]:
        p = bg[parte_key]
        eval_emoji = {"MEJORÓ": "📈", "EMPEORÓ": "📉", "NEUTRAL": "➖"}.get(p["evaluacion"], "❓")
        print(f"\n  {eval_emoji} {p['nombre']}: {p['evaluacion']}")
        print(f"     ✅ Favorables: {p['cambios_favorables']} | ❌ Desfavorables: {p['cambios_desfavorables']}")

    if r.get("alertas"):
        print(f"\n  🚨 ALERTAS")
        for alerta in r["alertas"]:
            print(f"     ⚠️  {alerta}")

    print(f"\n  📋 RECOMENDACIÓN")
    print(f"     {r['recomendacion']}")

    if r.get("mejoras_propuestas"):
        print(f"\n{'─' * 60}")
        print(f"  ✍️  MEJORAS PROPUESTAS — TEXTO LISTO PARA USAR")
        print(f"{'─' * 60}")
        for i, m in enumerate(r["mejoras_propuestas"], 1):
            prio_emoji = {"CRÍTICA": "🔴", "IMPORTANTE": "🟡", "DESEABLE": "🟢"}.get(m["prioridad"], "⚪")
            print(f"\n  {i}. {prio_emoji} [{m['prioridad']}] {m['clausula']}")
            print(f"     Problema: {m['problema_actual']}")
            print(f"     📝 Redacción sugerida:")
            for linea in m["texto_sugerido"].split(". "):
                linea = linea.strip()
                if linea and not linea.endswith("."):
                    linea += "."
                if linea:
                    print(f"        \"{linea}\"")
            print(f"     ⚖️  Fundamento: {m['justificacion_legal']}")

    if r.get("estrategia_negociacion"):
        en = r["estrategia_negociacion"]
        print(f"\n{'─' * 60}")
        print(f"  🎯 ESTRATEGIA DE NEGOCIACIÓN")
        print(f"{'─' * 60}")

        print(f"\n  💪 POSICIÓN FUERTE (usá esto como leverage)")
        for p in en["posicion_fuerte"]:
            print(f"     • {p}")

        print(f"\n  🤝 CONCESIONES POSIBLES (podés ceder sin riesgo)")
        for c in en["concesiones_posibles"]:
            print(f"     • {c}")

        print(f"\n  🚫 NO NEGOCIABLES (no ceder bajo ningún concepto)")
        for n in en["puntos_no_negociables"]:
            print(f"     • {n}")

    if r.get("next_steps"):
        print(f"\n{'─' * 60}")
        print(f"  📌 NEXT STEPS — PLAN DE ACCIÓN")
        print(f"{'─' * 60}")
        for i, ns in enumerate(r["next_steps"], 1):
            urg_emoji = {"INMEDIATO": "🔴", "ESTA SEMANA": "🟡", "ANTES DE FIRMAR": "🟢"}.get(ns["urgencia"], "⚪")
            print(f"\n  {i}. {urg_emoji} [{ns['urgencia']}] {ns['paso']}")
            print(f"     Responsable: {ns['responsable']}")
            print(f"     {ns['detalle']}")

    print("\n" + "=" * 60)


def main():
    print("\n🔄 LEGALFLOW — COMPARADOR DE CONTRATOS v0.1")
    print("   Compará versiones y detectá qué cambió y quién gana\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("⚠️  No se encontró ANTHROPIC_API_KEY.")
        api_key = input("Pegá tu API key (o Enter para demo): ").strip()

    if not api_key:
        print("\n📎 Modo demo — comparando Versión 1 vs Versión 5\n")
        print("   Versión 1: Borrador inicial del Cliente")
        print("   Versión 5: Versión final negociada")

        resultado_demo = {
            "resumen_cambios": {
                "total_cambios": 7,
                "clausulas_modificadas": 4,
                "clausulas_agregadas": 2,
                "clausulas_eliminadas": 0
            },
            "cambios": [
                {
                    "clausula": "Cláusula 1 - Objeto",
                    "tipo": "MODIFICADA",
                    "antes": "Consultoría tecnológica sin especificación de alcance",
                    "despues": "Consultoría conforme Anexo A con entregables, metodología y criterios de aceptación",
                    "impacto_parte_a": "FAVORABLE",
                    "impacto_parte_b": "FAVORABLE",
                    "explicacion": "Ambas partes se benefician: el Cliente sabe qué esperar y el Prestador tiene límites claros de su obligación"
                },
                {
                    "clausula": "Cláusula 2 - Plazo de pago",
                    "tipo": "MODIFICADA",
                    "antes": "60 días para pagar la factura",
                    "despues": "30 días para pagar. Tipo de cambio: dólar MEP del BCRA al día del pago",
                    "impacto_parte_a": "DESFAVORABLE",
                    "impacto_parte_b": "FAVORABLE",
                    "explicacion": "El Prestador logró reducir el plazo a la mitad y fijar un tipo de cambio. Mejora crítica de flujo de caja"
                },
                {
                    "clausula": "Cláusula 3 - Responsabilidad",
                    "tipo": "MODIFICADA",
                    "antes": "Tope de USD 1.000 en cualquier caso",
                    "despues": "Tope de USD 15.000 (3 meses). Se excluyen dolo y culpa grave",
                    "impacto_parte_a": "FAVORABLE",
                    "impacto_parte_b": "DESFAVORABLE",
                    "explicacion": "El Cliente tiene mayor cobertura ante incumplimiento. El Prestador asume más riesgo pero con exclusión de dolo"
                },
                {
                    "clausula": "Cláusula 4 - Confidencialidad",
                    "tipo": "MODIFICADA",
                    "antes": "Obligación genérica sin definiciones ni plazo post-contrato",
                    "despues": "Información definida en Anexo B, vigencia de 2 años post-contrato, excepciones estándar",
                    "impacto_parte_a": "FAVORABLE",
                    "impacto_parte_b": "NEUTRAL",
                    "explicacion": "Cláusula ahora ejecutable. Antes era decorativa. El Cliente gana protección real"
                },
                {
                    "clausula": "Cláusula 5 - Rescisión",
                    "tipo": "MODIFICADA",
                    "antes": "7 días de preaviso sin causa, sin indemnización",
                    "despues": "30 días de preaviso + indemnización de 1 mes de honorarios",
                    "impacto_parte_a": "DESFAVORABLE",
                    "impacto_parte_b": "FAVORABLE",
                    "explicacion": "Costo de salida más alto para ambas partes. Protege especialmente al Prestador de rescisiones abruptas"
                },
                {
                    "clausula": "Cláusula 6 - Propiedad Intelectual",
                    "tipo": "AGREGADA",
                    "antes": None,
                    "despues": "PI es del Cliente una vez pagados todos los honorarios",
                    "impacto_parte_a": "FAVORABLE",
                    "impacto_parte_b": "NEUTRAL",
                    "explicacion": "El Cliente asegura la PI pero condicionada al pago total. El Prestador retiene PI si no le pagan — protección inteligente"
                },
                {
                    "clausula": "Cláusula 7 - Jurisdicción (antes Cláusula 6)",
                    "tipo": "MODIFICADA",
                    "antes": "Tribunales de CABA directamente",
                    "despues": "Mediación obligatoria previa (CEMA), luego tribunales de CABA",
                    "impacto_parte_a": "NEUTRAL",
                    "impacto_parte_b": "FAVORABLE",
                    "explicacion": "Mediación previa reduce costos y tiempos. Generalmente favorece a la parte más chica (Prestador)"
                }
            ],
            "clausulas_sin_cambios": [],
            "balance_general": {
                "parte_a": {
                    "nombre": "TECHSTART S.A. (Cliente)",
                    "cambios_favorables": 4,
                    "cambios_desfavorables": 2,
                    "evaluacion": "MEJORÓ"
                },
                "parte_b": {
                    "nombre": "CONSULTORA XYZ S.R.L. (Prestador)",
                    "cambios_favorables": 4,
                    "cambios_desfavorables": 1,
                    "evaluacion": "MEJORÓ"
                }
            },
            "alertas": [
                "La cláusula de PI condiciona la transferencia al pago total — si el Cliente deja de pagar en el mes 10, la PI de 10 meses de trabajo queda en disputa",
                "No se agregó cláusula de penalidad por mora en el pago — los 30 días sin consecuencia por incumplimiento siguen siendo un riesgo",
                "El Anexo A y Anexo B son referenciados pero no incluidos — el contrato es incompleto sin ellos"
            ],
            "recomendacion": "La V5 es sustancialmente mejor que la V1 para ambas partes. El contrato pasó de ser riesgoso a razonablemente equilibrado. Antes de firmar: (1) completar Anexos A y B, (2) agregar cláusula de mora, (3) definir qué pasa con la PI si hay pago parcial.",
            "mejoras_propuestas": [
                {
                    "clausula": "Cláusula 2 - Mora por pago tardío (NUEVA)",
                    "problema_actual": "No hay consecuencia si el Cliente paga después de los 30 días. El Prestador no tiene herramienta para presionar el cobro.",
                    "texto_sugerido": "En caso de mora en el pago, el Cliente abonará un interés equivalente a la tasa activa del Banco Nación + 5 puntos porcentuales, calculado por cada día de atraso. Si la mora supera los 15 días, el Prestador podrá suspender la prestación del servicio sin que ello constituya incumplimiento contractual.",
                    "justificacion_legal": "Art. 768 CCyC — intereses moratorios. La suspensión de prestación ante mora es una excepción de incumplimiento (Art. 1031 CCyC).",
                    "prioridad": "CRÍTICA"
                },
                {
                    "clausula": "Cláusula 6 - Propiedad Intelectual",
                    "problema_actual": "La PI se transfiere solo si se pagan TODOS los honorarios. No define qué pasa con pago parcial (ej: pagó 10 de 12 meses).",
                    "texto_sugerido": "La PI de los entregables será transferida proporcionalmente al pago efectuado. Los entregables correspondientes a períodos impagos permanecerán bajo titularidad del Prestador hasta la cancelación total. En caso de rescisión anticipada, la PI de los entregables pagados se transfiere al Cliente dentro de los 10 días hábiles.",
                    "justificacion_legal": "Principio de proporcionalidad contractual. Evita enriquecimiento sin causa (Art. 1794 CCyC) de cualquiera de las partes.",
                    "prioridad": "CRÍTICA"
                },
                {
                    "clausula": "Cláusula 3 - Responsabilidad",
                    "problema_actual": "El tope de USD 15.000 no distingue entre tipos de daño. Un error menor tiene el mismo tope que una falla grave.",
                    "texto_sugerido": "La responsabilidad del Prestador queda limitada a: (a) por daño directo: hasta el equivalente a 3 meses de honorarios; (b) por lucro cesante: hasta 1 mes de honorarios. Quedan excluidas de todo límite las situaciones de dolo, culpa grave, o violación de la cláusula de confidencialidad.",
                    "justificacion_legal": "La distinción entre daño directo y lucro cesante es estándar en contratos de servicios profesionales y tiene fundamento en Art. 1738 CCyC.",
                    "prioridad": "IMPORTANTE"
                },
                {
                    "clausula": "Cláusula 5 - Rescisión",
                    "problema_actual": "La indemnización de 1 mes es fija sin importar cuándo se rescinde. Rescindir en el mes 2 cuesta lo mismo que en el mes 11.",
                    "texto_sugerido": "En caso de rescisión sin causa durante los primeros 6 meses de vigencia, la indemnización será equivalente a 2 meses de honorarios. A partir del mes 7, será de 1 mes de honorarios. La parte que rescinda deberá abonar adicionalmente los honorarios devengados hasta la fecha efectiva de terminación.",
                    "justificacion_legal": "Protege la inversión inicial del Prestador en onboarding y setup. Fundamento en Art. 1078-1079 CCyC sobre resolución de contratos.",
                    "prioridad": "IMPORTANTE"
                },
                {
                    "clausula": "Cláusula de Fuerza Mayor (NUEVA)",
                    "problema_actual": "No existe cláusula de fuerza mayor. Ante eventos extraordinarios (crisis cambiaria, pandemia, regulación nueva), no hay mecanismo de ajuste.",
                    "texto_sugerido": "Ninguna de las partes será responsable por incumplimientos derivados de eventos de fuerza mayor o caso fortuito conforme Art. 1730 CCyC. Ante eventos que impidan la prestación por más de 30 días corridos, cualquiera de las partes podrá rescindir sin indemnización, abonándose únicamente los servicios efectivamente prestados.",
                    "justificacion_legal": "Art. 1730 CCyC. Especialmente relevante en Argentina por volatilidad cambiaria y regulatoria.",
                    "prioridad": "DESEABLE"
                }
            ],
            "estrategia_negociacion": {
                "posicion_fuerte": [
                    "El Prestador ya concedió aumento del tope de responsabilidad de USD 1.000 a USD 15.000 — puede usar esto como leverage para pedir la cláusula de mora",
                    "La cláusula de PI favorece al Cliente — el Prestador puede pedir proporcionalidad a cambio",
                    "La mediación obligatoria fue una concesión del Cliente — muestra voluntad de negociar"
                ],
                "concesiones_posibles": [
                    "Aceptar que la confidencialidad se extienda a 3 años (en vez de 2) a cambio de la cláusula de mora",
                    "Reducir la indemnización por rescisión temprana si el Cliente acepta fuerza mayor",
                    "Aceptar auditoría trimestral del servicio a cambio de pago a 15 días"
                ],
                "puntos_no_negociables": [
                    "Tipo de cambio MEP — volver a dejarlo indefinido sería repetir el error de la V1",
                    "Plazo de pago no mayor a 30 días — el flujo de caja del Prestador no resiste más",
                    "Exclusión de dolo y culpa grave del tope de responsabilidad — es estándar legal y no negociable"
                ]
            },
            "next_steps": [
                {
                    "paso": "Redactar Anexo A (Alcance de Servicios) y Anexo B (Información Confidencial)",
                    "responsable": "ABOGADO",
                    "urgencia": "INMEDIATO",
                    "detalle": "El contrato referencia ambos anexos pero no existen. Sin ellos, las cláusulas 1 y 4 son inaplicables. Usar los entregables del presupuesto original como base para el Anexo A."
                },
                {
                    "paso": "Proponer cláusula de mora y fuerza mayor a la contraparte",
                    "responsable": "ABOGADO",
                    "urgencia": "INMEDIATO",
                    "detalle": "Enviar las redacciones sugeridas arriba como propuesta de V6. Presentarlas como protección para ambas partes, no como demanda unilateral."
                },
                {
                    "paso": "Validar el tipo de cambio MEP con el área financiera del Cliente",
                    "responsable": "CLIENTE",
                    "urgencia": "ESTA SEMANA",
                    "detalle": "Confirmar que el Cliente puede operativamente pagar al tipo MEP del día de pago. Si usa otro mecanismo, ajustar la cláusula antes de firmar."
                },
                {
                    "paso": "Revisar implicaciones fiscales de la facturación en USD",
                    "responsable": "ABOGADO",
                    "urgencia": "ESTA SEMANA",
                    "detalle": "Consultar con contador sobre facturación en moneda extranjera, retenciones aplicables, y si conviene facturar en pesos con cláusula de ajuste en vez de USD directo."
                },
                {
                    "paso": "Definir mecanismo de resolución para PI en caso de pago parcial",
                    "responsable": "ABOGADO",
                    "urgencia": "ANTES DE FIRMAR",
                    "detalle": "Negociar con contraparte la transferencia proporcional de PI. Esto evita un escenario de disputa costoso si el contrato termina antes de los 12 meses."
                },
                {
                    "paso": "Firmar contrato final (V6 o V7)",
                    "responsable": "CLIENTE",
                    "urgencia": "ANTES DE FIRMAR",
                    "detalle": "Solo firmar cuando: Anexos A y B estén completos, cláusula de mora incluida, y mecanismo de PI parcial definido. Hacer firmar ambas partes con certificación de firma si el monto lo justifica."
                }
            ]
        }

        mostrar_comparacion(resultado_demo)
        output_path = "ultima_comparacion.json"
        with open(output_path, "w") as f:
            json.dump(resultado_demo, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Resultado guardado en: {output_path}")
        return

    if len(sys.argv) == 3:
        with open(sys.argv[1], "r") as f:
            v1 = f.read()
        with open(sys.argv[2], "r") as f:
            v2 = f.read()
        print(f"📄 Comparando: {sys.argv[1]} vs {sys.argv[2]}")
    else:
        print("Opciones:")
        print("  1. Usar contratos de ejemplo (V1 vs V5)")
        print("  2. Pegar dos contratos")
        print("  3. Desde archivos: python3 comparador.py v1.txt v5.txt")
        opcion = input("\nElegí (1/2): ").strip()

        if opcion == "2":
            print("\nPegá la VERSIÓN ANTERIOR (terminá con línea vacía):")
            lineas = []
            while True:
                linea = input()
                if linea == "":
                    break
                lineas.append(linea)
            v1 = "\n".join(lineas)

            print("\nPegá la VERSIÓN NUEVA (terminá con línea vacía):")
            lineas = []
            while True:
                linea = input()
                if linea == "":
                    break
                lineas.append(linea)
            v2 = "\n".join(lineas)
        else:
            v1 = CONTRATO_V1
            v2 = CONTRATO_V5
            print("\n📎 Usando contratos de ejemplo...")

    print("\n⏳ Comparando versiones con Claude...")
    resultado = comparar_contratos(v1, v2, api_key)
    mostrar_comparacion(resultado)

    output_path = "ultima_comparacion.json"
    with open(output_path, "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Resultado guardado en: {output_path}")


if __name__ == "__main__":
    main()

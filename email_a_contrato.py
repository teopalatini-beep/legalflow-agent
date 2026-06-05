import anthropic
import json
import os
import sys

SYSTEM_PROMPT_EXTRACTOR = """Sos un agente legal que extrae datos contractuales de emails de negociación.

Te van a dar uno o más emails de una negociación comercial. Tu trabajo es extraer TODOS los términos comerciales y legales mencionados, incluso si están implícitos o son informales.

Respondé SIEMPRE con este JSON exacto (sin texto adicional):

{
  "datos_extraidos": {
    "partes": [
      {
        "nombre": "nombre de la empresa o persona",
        "rol": "CLIENTE | PRESTADOR | COMPRADOR | VENDEDOR | LICENCIANTE | LICENCIATARIO",
        "contacto": "email o nombre del contacto",
        "datos_fiscales": "CUIT/RFC/RUT si se mencionan, sino null"
      }
    ],
    "objeto": "descripción del servicio o producto negociado",
    "tipo_contrato_sugerido": "PRESTACIÓN DE SERVICIOS | LICENCIA | COMPRAVENTA | NDA | CONSULTORÍA | DESARROLLO DE SOFTWARE | OTRO",
    "terminos_comerciales": {
      "monto": "monto mencionado o null",
      "moneda": "USD | ARS | otra o null",
      "forma_pago": "mensual, por hito, adelanto, etc. o null",
      "plazo_pago": "días para pagar o null",
      "duracion": "duración mencionada o null"
    },
    "condiciones_mencionadas": [
      {
        "tema": "confidencialidad, exclusividad, PI, garantía, etc.",
        "detalle": "qué se dijo exactamente",
        "origen": "quién lo propuso (parte A o parte B)"
      }
    ],
    "puntos_pendientes": ["temas que se mencionaron pero no se cerraron"],
    "tono_negociacion": "AMIGABLE | FORMAL | TENSO | URGENTE"
  },
  "contrato_borrador": {
    "titulo": "CONTRATO DE [TIPO]",
    "preambulo": "texto del preámbulo con las partes",
    "clausulas": [
      {
        "numero": 1,
        "titulo": "OBJETO",
        "texto": "redacción completa de la cláusula",
        "origen": "EXTRAÍDO DEL EMAIL | SUGERIDO POR EL AGENTE | ESTÁNDAR LEGAL",
        "nota": "explicación de por qué se incluyó o redactó así"
      }
    ],
    "clausulas_sugeridas_no_mencionadas": [
      {
        "titulo": "nombre de la cláusula",
        "texto": "redacción sugerida",
        "justificacion": "por qué es importante incluirla aunque no se haya mencionado en los emails"
      }
    ]
  }
}"""

EMAIL_DEMO = """
=== EMAIL 1 — De: Laura Méndez <laura@techstart.com.ar> — Para: Carlos Ruiz <cruiz@dataflow.com.ar> ===
Asunto: Propuesta de servicios de migración cloud
Fecha: 15 de mayo 2026

Hola Carlos,

Como conversamos la semana pasada, te paso la propuesta formal para el proyecto de migración a AWS.

El alcance sería:
- Migración de 3 servidores on-premise a AWS (EC2 + RDS)
- Setup de CI/CD con GitHub Actions
- Capacitación al equipo de IT (2 sesiones de 4 horas)
- Soporte post-migración por 3 meses

Nuestra tarifa para este proyecto sería de USD 18.000 total, pagadero en 3 cuotas:
- 30% al inicio (USD 5.400)
- 40% al completar la migración (USD 7.200)
- 30% al finalizar el soporte (USD 5.400)

El proyecto lo estimamos en 8 semanas para la migración + 3 meses de soporte.

Necesitaríamos un NDA antes de arrancar porque vamos a tener acceso a sus bases de datos de producción.

¿Les funciona? Quedo atenta.
Laura

=== EMAIL 2 — De: Carlos Ruiz <cruiz@dataflow.com.ar> — Para: Laura Méndez <laura@techstart.com.ar> ===
Asunto: Re: Propuesta de servicios de migración cloud
Fecha: 18 de mayo 2026

Laura,

Gracias por la propuesta. La revisamos internamente y en general nos parece bien. Tenemos algunos puntos:

1. El monto está dentro de nuestro presupuesto, pero necesitamos facturación en pesos al tipo de cambio oficial del día de facturación. ¿Es posible?

2. El plazo de pago para nosotros es a 45 días de recibida la factura (política interna). ¿Pueden acomodar eso?

3. Queremos una cláusula de confidencialidad mutua, no solo NDA de un lado. Ustedes también van a ver información nuestra sensible.

4. ¿Qué pasa si la migración se demora más de las 8 semanas? ¿Hay penalidad o costo adicional?

5. Necesitamos que toda la documentación técnica y scripts que generen sean de nuestra propiedad.

Esperamos tu respuesta para avanzar con el contrato.

Saludos,
Carlos Ruiz
CTO - DataFlow S.R.L.

=== EMAIL 3 — De: Laura Méndez <laura@techstart.com.ar> — Para: Carlos Ruiz <cruiz@dataflow.com.ar> ===
Asunto: Re: Re: Propuesta de servicios de migración cloud
Fecha: 20 de mayo 2026

Carlos,

Gracias por el feedback. Respondo punto por punto:

1. Facturación en pesos: OK, podemos facturar en pesos al TC oficial. Pero necesitamos que el pago se haga dentro de los 30 días, no 45. Con la inflación actual 45 días nos complica mucho.

2. Intentemos 30 días. Si no es posible, podríamos aceptar 45 pero con un ajuste por IPC entre fecha de factura y fecha de pago.

3. Confidencialidad mutua: totalmente de acuerdo. Mandamos NDA bilateral.

4. Si la demora es por causa nuestra, las horas adicionales no tienen costo. Si es por demoras del lado de ustedes (accesos, aprobaciones, etc.), las horas extra se cobran a USD 85/hora.

5. La PI de scripts y documentación: OK que sea de ustedes, pero necesitamos poder reutilizar las metodologías y frameworks genéricos (no el código específico de su empresa). ¿Les parece razonable?

Creo que estamos cerca. ¿Armamos el contrato?

Laura
"""


def extraer_y_generar(emails: str, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[
            {"role": "user", "content": f"Extraé los datos contractuales de estos emails y generá un borrador de contrato:\n\n{emails}"}
        ],
        system=SYSTEM_PROMPT_EXTRACTOR,
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


def mostrar_resultado(resultado: dict):
    if "error" in resultado:
        print(f"\n❌ Error: {resultado['error']}")
        return

    datos = resultado["datos_extraidos"]
    contrato = resultado["contrato_borrador"]

    print("\n" + "=" * 60)
    print("  LEGALFLOW — EMAIL → CONTRATO")
    print("=" * 60)

    print(f"\n{'─' * 60}")
    print(f"  📧 DATOS EXTRAÍDOS DE LOS EMAILS")
    print(f"{'─' * 60}")

    print(f"\n  👥 PARTES IDENTIFICADAS")
    for p in datos["partes"]:
        print(f"     • {p['nombre']} — {p['rol']}")
        print(f"       Contacto: {p['contacto']}")
        if p.get("datos_fiscales"):
            print(f"       Fiscal: {p['datos_fiscales']}")

    print(f"\n  📋 OBJETO: {datos['objeto']}")
    print(f"  📑 TIPO: {datos['tipo_contrato_sugerido']}")

    tc = datos["terminos_comerciales"]
    print(f"\n  💰 TÉRMINOS COMERCIALES")
    print(f"     Monto: {tc.get('monto', 'No definido')}")
    print(f"     Moneda: {tc.get('moneda', 'No definida')}")
    print(f"     Forma de pago: {tc.get('forma_pago', 'No definida')}")
    print(f"     Plazo de pago: {tc.get('plazo_pago', 'No definido')}")
    print(f"     Duración: {tc.get('duracion', 'No definida')}")

    if datos.get("condiciones_mencionadas"):
        print(f"\n  📌 CONDICIONES DISCUTIDAS")
        for c in datos["condiciones_mencionadas"]:
            print(f"     • {c['tema']} (propuesto por {c['origen']})")
            print(f"       {c['detalle']}")

    if datos.get("puntos_pendientes"):
        print(f"\n  ⚠️  PUNTOS PENDIENTES (sin cerrar)")
        for p in datos["puntos_pendientes"]:
            print(f"     • {p}")

    print(f"\n  🎭 TONO: {datos.get('tono_negociacion', 'N/A')}")

    print(f"\n{'─' * 60}")
    print(f"  📄 BORRADOR DE CONTRATO GENERADO")
    print(f"{'─' * 60}")

    print(f"\n  {contrato['titulo']}")
    print(f"\n  {contrato['preambulo']}")

    for cl in contrato["clausulas"]:
        origen_emoji = {
            "EXTRAÍDO DEL EMAIL": "📧",
            "SUGERIDO POR EL AGENTE": "🤖",
            "ESTÁNDAR LEGAL": "⚖️"
        }.get(cl["origen"], "📝")
        print(f"\n  CLÁUSULA {cl['numero']} — {cl['titulo']} {origen_emoji}")
        for linea in cl["texto"].split(". "):
            linea = linea.strip()
            if linea:
                if not linea.endswith("."):
                    linea += "."
                print(f"     {linea}")
        if cl.get("nota"):
            print(f"     💡 {cl['nota']}")

    if contrato.get("clausulas_sugeridas_no_mencionadas"):
        print(f"\n{'─' * 60}")
        print(f"  🤖 CLÁUSULAS SUGERIDAS (no mencionadas en emails)")
        print(f"{'─' * 60}")
        for cs in contrato["clausulas_sugeridas_no_mencionadas"]:
            print(f"\n  🆕 {cs['titulo']}")
            for linea in cs["texto"].split(". "):
                linea = linea.strip()
                if linea:
                    if not linea.endswith("."):
                        linea += "."
                    print(f"     {linea}")
            print(f"     💡 {cs['justificacion']}")

    print("\n" + "=" * 60)


def main():
    print("\n📧 LEGALFLOW — EMAIL A CONTRATO v0.1")
    print("   Extraé datos de emails y generá contratos automáticamente\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("⚠️  No se encontró ANTHROPIC_API_KEY.")
        api_key = input("Pegá tu API key (o Enter para demo): ").strip()

    if not api_key:
        print("\n📎 Modo demo — procesando negociación de ejemplo\n")
        print("   3 emails entre Laura (TechStart) y Carlos (DataFlow)")
        print("   Tema: Migración cloud a AWS\n")

        resultado_demo = {
            "datos_extraidos": {
                "partes": [
                    {
                        "nombre": "TechStart (Laura Méndez)",
                        "rol": "PRESTADOR",
                        "contacto": "laura@techstart.com.ar",
                        "datos_fiscales": None
                    },
                    {
                        "nombre": "DataFlow S.R.L. (Carlos Ruiz, CTO)",
                        "rol": "CLIENTE",
                        "contacto": "cruiz@dataflow.com.ar",
                        "datos_fiscales": None
                    }
                ],
                "objeto": "Migración de infraestructura on-premise a AWS (3 servidores EC2 + RDS), setup de CI/CD con GitHub Actions, capacitación de equipo IT, y soporte post-migración",
                "tipo_contrato_sugerido": "PRESTACIÓN DE SERVICIOS",
                "terminos_comerciales": {
                    "monto": "USD 18.000 total (facturado en pesos al TC oficial)",
                    "moneda": "USD (facturación en ARS)",
                    "forma_pago": "3 cuotas: 30% inicio, 40% post-migración, 30% fin de soporte",
                    "plazo_pago": "En disputa: Prestador pide 30 días, Cliente pide 45 días. Alternativa: 45 días con ajuste IPC",
                    "duracion": "8 semanas (migración) + 3 meses (soporte) = ~5 meses total"
                },
                "condiciones_mencionadas": [
                    {
                        "tema": "Confidencialidad",
                        "detalle": "NDA bilateral acordado. Prestador tendrá acceso a bases de producción.",
                        "origen": "Ambas partes — Laura propuso NDA, Carlos pidió que sea mutuo"
                    },
                    {
                        "tema": "Propiedad Intelectual",
                        "detalle": "Scripts y documentación específica → Cliente. Metodologías y frameworks genéricos → Prestador puede reutilizar.",
                        "origen": "Carlos pidió PI total, Laura negoció separar genérico de específico"
                    },
                    {
                        "tema": "Demoras y horas extra",
                        "detalle": "Demora por culpa del Prestador: sin costo extra. Demora por culpa del Cliente: USD 85/hora adicional.",
                        "origen": "Carlos preguntó, Laura propuso el esquema"
                    },
                    {
                        "tema": "Tipo de cambio",
                        "detalle": "Facturación en pesos al tipo de cambio oficial del día de facturación.",
                        "origen": "Carlos lo pidió como requisito, Laura aceptó"
                    },
                    {
                        "tema": "Ajuste por inflación",
                        "detalle": "Si el plazo de pago es 45 días, se aplicaría ajuste por IPC entre fecha de factura y fecha de pago.",
                        "origen": "Laura lo propuso como alternativa al plazo de 30 días"
                    }
                ],
                "puntos_pendientes": [
                    "Plazo de pago: sin definición final (30 vs 45 días con IPC)",
                    "PI de frameworks genéricos: Carlos no respondió si acepta la separación",
                    "Datos fiscales de ambas partes (CUIT) no mencionados",
                    "No se discutió garantía post-migración ni SLA de soporte",
                    "No se definió penalidad por rescisión anticipada"
                ],
                "tono_negociacion": "AMIGABLE"
            },
            "contrato_borrador": {
                "titulo": "CONTRATO DE PRESTACIÓN DE SERVICIOS DE MIGRACIÓN CLOUD",
                "preambulo": "Entre DataFlow S.R.L., CUIT [COMPLETAR], con domicilio en [COMPLETAR], representada por Carlos Ruiz en su carácter de CTO (en adelante 'el Cliente'), y TechStart [COMPLETAR TIPO SOCIETARIO], CUIT [COMPLETAR], con domicilio en [COMPLETAR], representada por Laura Méndez (en adelante 'el Prestador'), se celebra el presente contrato sujeto a las siguientes cláusulas:",
                "clausulas": [
                    {
                        "numero": 1,
                        "titulo": "OBJETO",
                        "texto": "El Prestador se compromete a realizar la migración de infraestructura tecnológica del Cliente desde servidores on-premise hacia Amazon Web Services (AWS), incluyendo: (a) migración de 3 servidores a instancias EC2 y base de datos RDS; (b) implementación de pipeline CI/CD mediante GitHub Actions; (c) capacitación al equipo de IT del Cliente consistente en 2 sesiones de 4 horas cada una; (d) soporte post-migración por un período de 3 meses desde la fecha de finalización de la migración.",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "Alcance tomado directamente del email 1 de Laura. Se recomienda adjuntar Anexo Técnico con detalle de servidores, versiones y criterios de aceptación."
                    },
                    {
                        "numero": 2,
                        "titulo": "PLAZO",
                        "texto": "El proyecto tendrá una duración estimada de 8 semanas para la fase de migración, contadas desde la firma del presente contrato y la entrega de accesos por parte del Cliente. El soporte post-migración se extenderá por 3 meses adicionales desde la finalización exitosa de la migración.",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "Se sugiere definir hitos con fechas concretas en un cronograma adjunto."
                    },
                    {
                        "numero": 3,
                        "titulo": "MONTO Y FORMA DE PAGO",
                        "texto": "El precio total del servicio es de USD 18.000 (dólares estadounidenses dieciocho mil), que serán facturados en pesos argentinos al tipo de cambio oficial publicado por el BCRA en la fecha de emisión de cada factura. El pago se realizará en 3 cuotas: (a) USD 5.400 (30%) a la firma del contrato; (b) USD 7.200 (40%) a la finalización de la migración, certificada por acta de aceptación del Cliente; (c) USD 5.400 (30%) al cumplimiento del período de soporte. [OPCIÓN A: Plazo de pago: 30 días de recibida la factura] [OPCIÓN B: Plazo de pago: 45 días de recibida la factura, con ajuste por IPC entre fecha de factura y fecha de efectivo pago].",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "⚠️ PUNTO PENDIENTE: Las partes no acordaron si el plazo es 30 o 45 días. Se presentan ambas opciones para definir antes de firmar."
                    },
                    {
                        "numero": 4,
                        "titulo": "DEMORAS Y HORAS ADICIONALES",
                        "texto": "Si la migración excediera el plazo de 8 semanas por causas atribuibles al Prestador, las horas adicionales no generarán costo extra para el Cliente. Si la demora fuera atribuible al Cliente (incluyendo demoras en entrega de accesos, credenciales o aprobaciones), las horas adicionales se facturarán a una tarifa de USD 85 por hora, facturadas en pesos al tipo de cambio oficial vigente.",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "Esquema propuesto por Laura en email 3. Carlos no objetó. Se recomienda definir un mecanismo de notificación formal de demoras."
                    },
                    {
                        "numero": 5,
                        "titulo": "CONFIDENCIALIDAD",
                        "texto": "Ambas partes se obligan a mantener estricta confidencialidad sobre toda información técnica, comercial y de negocio a la que accedan en virtud del presente contrato. Esta obligación incluye, sin limitación, bases de datos, código fuente, arquitectura de sistemas, datos de clientes y estrategias comerciales. La obligación de confidencialidad se extenderá por 2 años posteriores a la finalización del contrato por cualquier causa. Se exceptúa la información que: (a) sea de dominio público; (b) haya sido conocida previamente por la parte receptora; (c) sea requerida por autoridad judicial o administrativa competente.",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "Laura propuso NDA unilateral, Carlos pidió bilateral. Se redactó como cláusula bilateral dentro del contrato principal, lo cual es más eficiente que un NDA separado."
                    },
                    {
                        "numero": 6,
                        "titulo": "PROPIEDAD INTELECTUAL",
                        "texto": "Los scripts, documentación técnica y todo desarrollo específico realizado para el Cliente en el marco del presente contrato serán de propiedad exclusiva del Cliente una vez abonada la totalidad de los honorarios. El Prestador retiene el derecho de reutilizar metodologías, frameworks, herramientas genéricas y conocimiento técnico general que no contengan información confidencial del Cliente.",
                        "origen": "EXTRAÍDO DEL EMAIL",
                        "nota": "⚠️ PUNTO PENDIENTE: Laura propuso separar PI específica (del Cliente) de genérica (del Prestador). Carlos no confirmó. Definir antes de firmar."
                    },
                    {
                        "numero": 7,
                        "titulo": "JURISDICCIÓN",
                        "texto": "Para cualquier controversia derivada del presente contrato, las partes se someten a mediación prejudicial obligatoria. En caso de no alcanzar acuerdo, serán competentes los tribunales ordinarios de la Ciudad Autónoma de Buenos Aires.",
                        "origen": "ESTÁNDAR LEGAL",
                        "nota": "No se discutió en los emails. Se incluye mediación previa como práctica recomendada."
                    }
                ],
                "clausulas_sugeridas_no_mencionadas": [
                    {
                        "titulo": "RESCISIÓN ANTICIPADA",
                        "texto": "Cualquiera de las partes podrá rescindir el presente contrato con 15 días de preaviso fehaciente. En caso de rescisión sin causa por parte del Cliente, deberá abonar los servicios efectivamente prestados más un 20% del saldo pendiente en concepto de lucro cesante. En caso de rescisión por parte del Prestador, deberá completar la transferencia de conocimiento y documentación al Cliente o a quien este designe.",
                        "justificacion": "Ningún email menciona qué pasa si alguna parte quiere salir del contrato. Sin esta cláusula, una rescisión genera disputa automática."
                    },
                    {
                        "titulo": "GARANTÍA Y SLA DE SOPORTE",
                        "texto": "Durante el período de soporte post-migración, el Prestador garantiza un tiempo de respuesta máximo de 4 horas hábiles para incidentes críticos y 24 horas hábiles para incidentes no críticos. Se consideran incidentes críticos aquellos que impidan la operación normal del sistema migrado.",
                        "justificacion": "Se acordaron 3 meses de soporte pero sin definir qué nivel de servicio incluye. Sin SLA, el Cliente no tiene herramienta para exigir respuesta y el Prestador no tiene límites claros de su obligación."
                    },
                    {
                        "titulo": "FUERZA MAYOR",
                        "texto": "Ninguna de las partes será responsable por incumplimientos derivados de eventos de fuerza mayor o caso fortuito conforme Art. 1730 del CCyC. Si el evento impide la prestación por más de 30 días, cualquiera de las partes podrá rescindir sin indemnización, abonándose los servicios efectivamente prestados.",
                        "justificacion": "Relevante por la volatilidad regulatoria y cambiaria argentina. Protege a ambas partes ante escenarios imprevisibles."
                    },
                    {
                        "titulo": "MORA",
                        "texto": "En caso de mora en el pago, el Cliente abonará un interés equivalente a la tasa activa del Banco Nación + 3 puntos porcentuales por cada día de atraso. Si la mora supera los 15 días, el Prestador podrá suspender la prestación del servicio previa notificación fehaciente, sin que ello constituya incumplimiento contractual.",
                        "justificacion": "Se negoció el plazo de pago pero no las consecuencias de no cumplirlo. Sin cláusula de mora, el Prestador no tiene presión legal para cobrar a tiempo."
                    }
                ]
            }
        }

        mostrar_resultado(resultado_demo)
        output_path = "ultimo_email_contrato.json"
        with open(output_path, "w") as f:
            json.dump(resultado_demo, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Resultado guardado en: {output_path}")
        return

    print("Opciones:")
    print("  1. Usar emails de ejemplo (negociación de migración cloud)")
    print("  2. Pegar emails manualmente")
    opcion = input("\nElegí (1/2): ").strip()

    if opcion == "2":
        print("\nPegá los emails (separalos con líneas '==='. Terminá con línea vacía):")
        lineas = []
        while True:
            linea = input()
            if linea == "":
                break
            lineas.append(linea)
        emails = "\n".join(lineas)
    else:
        emails = EMAIL_DEMO
        print("\n📎 Usando emails de ejemplo...")

    print("\n⏳ Extrayendo datos y generando contrato con Claude...")
    resultado = extraer_y_generar(emails, api_key)
    mostrar_resultado(resultado)

    output_path = "ultimo_email_contrato.json"
    with open(output_path, "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Resultado guardado en: {output_path}")


if __name__ == "__main__":
    main()

"""
LegalFlow — Gmail Agent
Conecta a Gmail, busca emails de negociación, extrae datos y genera contrato.

Uso:
  python3 gmail_agente.py                  # Modo interactivo
  python3 gmail_agente.py "e-commerce"     # Busca directamente ese término
"""
import subprocess
import json
import sys
import os
import re

# ─── Colores para terminal ───
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_header(text):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"  {BOLD}{text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


def print_section(emoji, title, content):
    print(f"\n  {emoji} {BOLD}{title}{RESET}")
    if isinstance(content, str):
        print(f"     {content}")
    elif isinstance(content, list):
        for item in content:
            print(f"     • {item}")


def buscar_en_gmail(query, max_results=10):
    """Busca threads en Gmail usando claude CLI con MCP."""
    cmd = [
        "claude", "-p",
        f"""Usá la herramienta search_threads de Gmail para buscar emails con este query: {query}
        Limitá a {max_results} resultados.
        Devolvé SOLO un JSON con esta estructura exacta, sin texto adicional:
        {{"threads": [{{"id": "thread_id", "subject": "asunto", "sender": "email", "date": "fecha", "snippet": "preview"}}]}}"""
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        text = result.stdout.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"  {RED}Error buscando en Gmail: {e}{RESET}")
    return None


def obtener_thread(thread_id):
    """Obtiene el contenido completo de un thread de Gmail."""
    cmd = [
        "claude", "-p",
        f"""Usá la herramienta get_thread de Gmail con threadId "{thread_id}" y messageFormat "FULL_CONTENT".
        Devolvé SOLO un JSON con esta estructura exacta, sin texto adicional:
        {{"messages": [{{"sender": "email", "date": "fecha", "subject": "asunto", "body": "contenido completo del plaintextBody"}}]}}"""
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        text = result.stdout.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"  {RED}Error obteniendo thread: {e}{RESET}")
    return None


SYSTEM_PROMPT = """Sos un agente legal especializado en derecho argentino. Te dan emails de una negociación comercial.

Extraé TODOS los términos y generá un contrato borrador.

Respondé SOLO con JSON (sin texto adicional):
{
  "partes": [{"nombre": "...", "rol": "CLIENTE|PRESTADOR", "contacto": "...", "cuit": "..."}],
  "objeto": "descripción",
  "terminos": {"monto": "...", "moneda": "...", "forma_pago": "...", "plazo_pago": "...", "duracion": "..."},
  "condiciones_acordadas": [{"tema": "...", "detalle": "...", "estado": "ACORDADO|EN_DISPUTA|PENDIENTE"}],
  "puntos_sin_cerrar": ["..."],
  "contrato": {"titulo": "CONTRATO DE ...", "preambulo": "Entre ...", "clausulas": [{"numero": 1, "titulo": "...", "texto": "...", "origen": "EMAIL|SUGERIDA|ESTÁNDAR", "nota": "..."}]},
  "clausulas_sugeridas": [{"titulo": "...", "texto": "...", "justificacion": "..."}],
  "next_steps": [{"paso": "...", "responsable": "ABOGADO|CLIENTE|CONTRAPARTE", "urgencia": "INMEDIATO|ESTA_SEMANA|ANTES_DE_FIRMAR"}]
}"""


def analizar_con_claude(emails_text):
    """Envía los emails a Claude para extraer datos y generar contrato."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Analizá estos emails y generá el contrato:\n\n{emails_text}"}],
            )
            raw = message.content[0].text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            print(f"  {RED}Error con API: {e}{RESET}")
        return None

    # Sin API key: intentar con claude CLI usando archivo temporal
    import tempfile
    prompt = f"{SYSTEM_PROMPT}\n\nEMAILS:\n{emails_text}"
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(prompt)
            tmpfile = f.name
        result = subprocess.run(
            ["claude", "-p", f"Leé el archivo {tmpfile} y seguí las instrucciones. Respondé SOLO con JSON."],
            capture_output=True, text=True, timeout=180
        )
        os.unlink(tmpfile)
        text = result.stdout.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"  {YELLOW}Claude CLI no pudo procesar. Usando análisis demo.{RESET}")

    # Fallback: resultado demo basado en los emails del e-commerce
    return None


def mostrar_extraccion(datos):
    """Muestra los datos extraídos de forma visual."""

    print("\n" + "=" * 60)
    print(f"  {BOLD}LEGALFLOW — GMAIL → CONTRATO{RESET}")
    print("=" * 60)

    # Partes
    print_header("👥 PARTES IDENTIFICADAS")
    for p in datos.get("partes", []):
        cuit = f" | CUIT: {p['cuit']}" if p.get("cuit") else ""
        print(f"     • {BOLD}{p['nombre']}{RESET} — {p['rol']}")
        print(f"       Contacto: {p.get('contacto', 'N/A')}{cuit}")

    # Objeto y términos
    print_header("📋 OBJETO Y TÉRMINOS")
    print(f"     {datos.get('objeto', 'N/A')}")
    t = datos.get("terminos", {})
    print(f"\n     💰 Monto: {t.get('monto', 'N/A')}")
    print(f"     💱 Moneda: {t.get('moneda', 'N/A')}")
    print(f"     📅 Forma de pago: {t.get('forma_pago', 'N/A')}")
    print(f"     ⏰ Plazo de pago: {t.get('plazo_pago', 'N/A')}")
    print(f"     📆 Duración: {t.get('duracion', 'N/A')}")

    # Condiciones
    if datos.get("condiciones_acordadas"):
        print_header("📌 CONDICIONES NEGOCIADAS")
        for c in datos["condiciones_acordadas"]:
            estado = c.get("estado", "?")
            emoji = {"ACORDADO": f"{GREEN}✅", "EN_DISPUTA": f"{YELLOW}⚠️", "PENDIENTE": f"{RED}❓"}.get(estado, "❓")
            print(f"     {emoji} [{estado}]{RESET} {BOLD}{c['tema']}{RESET}")
            print(f"       {c['detalle']}")

    # Puntos sin cerrar
    if datos.get("puntos_sin_cerrar"):
        print_header("🚨 PUNTOS SIN CERRAR")
        for p in datos["puntos_sin_cerrar"]:
            print(f"     {RED}⚠️  {p}{RESET}")

    # Contrato
    contrato = datos.get("contrato", {})
    if contrato:
        print_header(f"📄 {contrato.get('titulo', 'BORRADOR DE CONTRATO')}")
        if contrato.get("preambulo"):
            print(f"\n     {contrato['preambulo']}")

        for cl in contrato.get("clausulas", []):
            origen_emoji = {"EMAIL": "📧", "SUGERIDA": "🤖", "ESTÁNDAR": "⚖️"}.get(cl.get("origen", ""), "📝")
            print(f"\n     {BOLD}CLÁUSULA {cl['numero']} — {cl['titulo']}{RESET} {origen_emoji}")
            texto = cl.get("texto", "")
            for linea in texto.split(". "):
                linea = linea.strip()
                if linea:
                    if not linea.endswith("."):
                        linea += "."
                    print(f"       {linea}")
            if cl.get("nota"):
                print(f"       {YELLOW}💡 {cl['nota']}{RESET}")

    # Cláusulas sugeridas
    if datos.get("clausulas_sugeridas"):
        print_header("🤖 CLÁUSULAS SUGERIDAS (no mencionadas en emails)")
        for cs in datos["clausulas_sugeridas"]:
            print(f"\n     {GREEN}🆕 {BOLD}{cs['titulo']}{RESET}")
            for linea in cs.get("texto", "").split(". "):
                linea = linea.strip()
                if linea:
                    if not linea.endswith("."):
                        linea += "."
                    print(f"       {linea}")
            print(f"       {YELLOW}💡 {cs.get('justificacion', '')}{RESET}")

    # Next steps
    if datos.get("next_steps"):
        print_header("📌 NEXT STEPS")
        for i, ns in enumerate(datos["next_steps"], 1):
            urg_emoji = {"INMEDIATO": f"{RED}🔴", "ESTA_SEMANA": f"{YELLOW}🟡", "ANTES_DE_FIRMAR": f"{GREEN}🟢"}.get(ns.get("urgencia", ""), "⚪")
            print(f"     {i}. {urg_emoji} [{ns.get('urgencia', '?')}]{RESET} {ns['paso']}")
            print(f"        Responsable: {ns.get('responsable', 'N/A')}")

    print("\n" + "=" * 60)


def demo_resultado():
    return {
        "partes": [
            {"nombre": "Palatini Group S.A.", "rol": "CLIENTE", "contacto": "teopalatini@gmail.com", "cuit": "30-71999222-7"},
            {"nombre": "DigitalWave S.R.L.", "rol": "PRESTADOR", "contacto": "mariana@digitalwave.com.ar", "cuit": "30-71555888-4"}
        ],
        "objeto": "Desarrollo de plataforma e-commerce: tienda online 500+ productos, integración MercadoPago/Stripe, panel admin, app mobile React Native, integración AFIP",
        "terminos": {
            "monto": "En disputa: Prestador pide USD 40.000 (scope completo) o USD 38.000 (sin app mobile). Cliente ofreció USD 38.000.",
            "moneda": "USD facturado en ARS al tipo de cambio MEP del día de emisión",
            "forma_pago": "4 cuotas mensuales (propuesta original). Pendiente ajustar si cambia el monto total.",
            "plazo_pago": "45 días acordado. Con interés del 2% mensual por mora y derecho a pausar desarrollo.",
            "duracion": "16 semanas desarrollo + 4 semanas QA + 6 meses soporte = ~8 meses total"
        },
        "condiciones_acordadas": [
            {"tema": "Facturación", "detalle": "Factura A en pesos argentinos al dólar MEP del día de emisión", "estado": "ACORDADO"},
            {"tema": "Plazo de pago", "detalle": "45 días con interés del 2% mensual por mora y derecho a pausar desarrollo", "estado": "ACORDADO"},
            {"tema": "NDA Bilateral", "detalle": "Confidencialidad mutua. Ambas partes manejan información sensible de la otra.", "estado": "ACORDADO"},
            {"tema": "Bugs en soporte", "detalle": "Corrección de bugs ilimitada durante los 6 meses de soporte post-lanzamiento", "estado": "ACORDADO"},
            {"tema": "Monto", "detalle": "Prestador ofrece USD 40.000 (scope completo) o USD 38.000 (sin app). Cliente pidió USD 38.000 con scope completo.", "estado": "EN_DISPUTA"},
            {"tema": "Propiedad Intelectual", "detalle": "Código específico → Cliente. Librerías y frameworks genéricos → Prestador los reutiliza. Cliente pidió 100% sin distinción.", "estado": "EN_DISPUTA"},
            {"tema": "Penalidad por demora", "detalle": "Prestador acepta 3%/semana (tope 15%). Cliente pidió 5%/semana (tope 20%). Prestador pide reciprocidad si Cliente demora feedback.", "estado": "EN_DISPUTA"},
            {"tema": "Horas de mejoras mensuales", "detalle": "Prestador ofrece 8hs/mes incluidas + USD 75/hora extra. Cliente pidió 20hs/mes.", "estado": "EN_DISPUTA"},
            {"tema": "No competencia", "detalle": "Prestador acepta 6 meses limitada al mismo tipo de producto. Cliente pidió 12 meses para todo competidor.", "estado": "EN_DISPUTA"}
        ],
        "puntos_sin_cerrar": [
            "Monto final: USD 40K con app o USD 38K sin app — Teo no respondió",
            "PI de librerías genéricas: Mariana la separó de la PI específica, Teo no confirmó",
            "Penalidad: 3% vs 5% por semana, y la reciprocidad por demoras del Cliente",
            "Horas de mejoras: 8hs vs 20hs mensuales",
            "No competencia: 6 vs 12 meses, y alcance (mismo producto vs todo competidor)",
            "No se discutió qué pasa con la app mobile si se hace como Fase 2",
            "No se definió SLA de soporte (tiempos de respuesta para incidentes)",
            "No hay cláusula de rescisión anticipada"
        ],
        "contrato": {
            "titulo": "CONTRATO DE DESARROLLO DE PLATAFORMA E-COMMERCE",
            "preambulo": "Entre Palatini Group S.A., CUIT 30-71999222-7, representada por Teo Palatini en su carácter de Director (en adelante 'el Cliente'), y DigitalWave S.R.L., CUIT 30-71555888-4, con domicilio en Av. del Libertador 6250, Piso 3, CABA, representada por Mariana Torres en su carácter de CEO (en adelante 'el Prestador'):",
            "clausulas": [
                {
                    "numero": 1, "titulo": "OBJETO",
                    "texto": "El Prestador se compromete a desarrollar una plataforma de comercio electrónico para el Cliente que incluye: (a) tienda online con catálogo de 500+ productos; (b) integración con MercadoPago y Stripe; (c) panel de administración con gestión de inventario; (d) aplicación mobile para iOS y Android en React Native; (e) integración con sistema de facturación AFIP. El alcance detallado se especifica en el Anexo Técnico adjunto.",
                    "origen": "EMAIL",
                    "nota": "Alcance del email 1. La app mobile puede quedar fuera si se cierra en USD 38K — definir antes de firmar."
                },
                {
                    "numero": 2, "titulo": "PLAZO",
                    "texto": "El desarrollo tendrá una duración de 16 semanas, seguido de 4 semanas de testing y QA, contados desde la firma del contrato y entrega de accesos por parte del Cliente. El soporte post-lanzamiento se extenderá por 6 meses desde la aceptación final de la plataforma.",
                    "origen": "EMAIL",
                    "nota": "Plazos del email 1. Se recomienda adjuntar cronograma con hitos y criterios de aceptación."
                },
                {
                    "numero": 3, "titulo": "MONTO Y FORMA DE PAGO",
                    "texto": "[OPCIÓN A] El precio total es de USD 40.000, pagaderos en 4 cuotas mensuales de USD 10.000. [OPCIÓN B] El precio total es de USD 38.000, excluyendo la app mobile que se presupuestará como Fase 2. Las facturas se emitirán en pesos argentinos al tipo de cambio dólar MEP publicado por el BCRA en la fecha de emisión. Factura tipo A.",
                    "origen": "EMAIL",
                    "nota": "⚠️ PUNTO ABIERTO: Las partes no cerraron si es USD 40K con app o USD 38K sin app."
                },
                {
                    "numero": 4, "titulo": "PLAZO Y MORA EN EL PAGO",
                    "texto": "El Cliente abonará cada factura dentro de los 45 días corridos de recibida. En caso de mora, se aplicará un interés del 2% mensual sobre el monto impago. Si la mora supera los 45 días, el Prestador podrá suspender el desarrollo previa notificación fehaciente, sin que ello constituya incumplimiento contractual. Los trabajos se reanudarán dentro de los 5 días hábiles de regularizado el pago.",
                    "origen": "EMAIL",
                    "nota": "Acordado en email 3. El plazo de 45 días y la mora del 2% fueron aceptados por ambas partes."
                },
                {
                    "numero": 5, "titulo": "PROPIEDAD INTELECTUAL",
                    "texto": "Todo código fuente, diseños, documentación y assets desarrollados específicamente para el proyecto serán propiedad exclusiva del Cliente una vez abonada la totalidad de los honorarios. El Prestador retiene el derecho de utilizar y reutilizar librerías, componentes genéricos, frameworks y herramientas que: (a) hayan sido desarrollados con anterioridad al proyecto, o (b) constituyan herramientas de uso interno del Prestador que no contengan información confidencial ni lógica de negocio del Cliente.",
                    "origen": "EMAIL",
                    "nota": "⚠️ PUNTO ABIERTO: Mariana separó PI específica de genérica. Teo pidió 100% sin distinción. Negociar antes de firmar."
                },
                {
                    "numero": 6, "titulo": "PENALIDAD POR DEMORA",
                    "texto": "Si el proyecto excede los plazos establecidos por causas atribuibles al Prestador, el Cliente tendrá derecho a un descuento del [3% | 5%] del monto total por cada semana completa de demora, con un tope máximo del [15% | 20%]. Recíprocamente, si el Cliente demora en entregar feedback, aprobaciones, contenido o accesos por más de 5 días hábiles desde la solicitud formal, el cronograma se extenderá automáticamente por igual cantidad de días sin que ello constituya demora del Prestador.",
                    "origen": "EMAIL",
                    "nota": "⚠️ PUNTO ABIERTO: Porcentaje (3% vs 5%) y tope (15% vs 20%) sin cerrar. Reciprocidad propuesta por Mariana."
                },
                {
                    "numero": 7, "titulo": "GARANTÍA Y SOPORTE POST-LANZAMIENTO",
                    "texto": "Durante los 6 meses de soporte post-lanzamiento, el Prestador garantiza: (a) corrección ilimitada de bugs y errores de funcionamiento; (b) [8 | 20] horas mensuales de mejoras menores incluidas; (c) horas adicionales de mejoras a una tarifa de USD 75 por hora. Se consideran bugs los defectos que impidan el funcionamiento conforme a las especificaciones del Anexo Técnico.",
                    "origen": "EMAIL",
                    "nota": "⚠️ PUNTO ABIERTO: Horas de mejoras mensuales sin cerrar (8hs vs 20hs). Bugs ilimitados acordado."
                },
                {
                    "numero": 8, "titulo": "CONFIDENCIALIDAD",
                    "texto": "Ambas partes se obligan a mantener estricta confidencialidad sobre toda información técnica, comercial, financiera y estratégica a la que accedan en virtud del presente contrato. Esta obligación se extiende por 2 años posteriores a la finalización del contrato. Se exceptúa la información que sea de dominio público o requerida por autoridad competente.",
                    "origen": "EMAIL",
                    "nota": "NDA bilateral acordado. Se recomienda definir información confidencial en Anexo."
                },
                {
                    "numero": 9, "titulo": "NO COMPETENCIA",
                    "texto": "El Prestador se compromete a no prestar servicios de desarrollo de plataformas de e-commerce a empresas que comercialicen [exactamente el mismo tipo de producto que el Cliente | productos del mismo sector] en Argentina, durante la vigencia del contrato y por un período de [6 | 12] meses posteriores a su finalización.",
                    "origen": "EMAIL",
                    "nota": "⚠️ PUNTO ABIERTO: Plazo (6 vs 12 meses) y alcance (mismo producto vs sector completo) sin cerrar."
                },
                {
                    "numero": 10, "titulo": "EQUIPO DE TRABAJO",
                    "texto": "El Prestador asignará al proyecto el siguiente equipo mínimo: 1 Tech Lead senior, 2 desarrolladores full-stack, 1 diseñador UX/UI y 1 QA engineer. Cualquier cambio en el equipo asignado deberá ser notificado al Cliente con 5 días hábiles de anticipación, manteniendo un nivel de seniority equivalente.",
                    "origen": "EMAIL",
                    "nota": "Equipo detallado en email 1. Se agrega obligación de notificación ante cambios."
                },
                {
                    "numero": 11, "titulo": "JURISDICCIÓN",
                    "texto": "Para toda controversia derivada del presente contrato, las partes se someten a mediación prejudicial obligatoria. De no alcanzarse acuerdo, serán competentes los tribunales ordinarios de la Ciudad Autónoma de Buenos Aires.",
                    "origen": "ESTÁNDAR",
                    "nota": "No se discutió en emails. Se incluye mediación previa como práctica recomendada."
                }
            ]
        },
        "clausulas_sugeridas": [
            {
                "titulo": "RESCISIÓN ANTICIPADA",
                "texto": "Cualquiera de las partes podrá rescindir el contrato con 15 días de preaviso fehaciente. En caso de rescisión sin causa por parte del Cliente, deberá abonar los trabajos efectivamente realizados más un 20% del saldo pendiente como lucro cesante. En caso de rescisión por parte del Prestador, deberá completar la transferencia del código y documentación al Cliente o a quien este designe.",
                "justificacion": "Ningún email menciona rescisión. Sin esta cláusula, una salida genera disputa automática. Especialmente relevante en un proyecto de 8+ meses."
            },
            {
                "titulo": "SLA DE SOPORTE",
                "texto": "Durante el soporte, el Prestador garantiza respuesta en 4 horas hábiles para incidentes críticos (plataforma caída o imposibilidad de procesar pagos) y 24 horas hábiles para incidentes no críticos.",
                "justificacion": "Se acordaron 6 meses de soporte pero sin definir nivel de servicio. Sin SLA, 'soporte' puede significar cualquier cosa."
            },
            {
                "titulo": "FUERZA MAYOR",
                "texto": "Ninguna parte será responsable por incumplimientos derivados de fuerza mayor (Art. 1730 CCyC). Si el evento supera 30 días, cualquier parte puede rescindir sin indemnización, abonándose trabajos realizados.",
                "justificacion": "Proyecto de 8 meses en Argentina. Crisis cambiaria, regulatoria o tecnológica pueden impactar. Protege a ambas partes."
            },
            {
                "titulo": "ACEPTACIÓN Y TESTING",
                "texto": "El Cliente dispondrá de 10 días hábiles para aceptar o rechazar cada entregable. El rechazo debe ser fundado por escrito con detalle de los defectos. Si el Cliente no responde en plazo, el entregable se considerará aceptado.",
                "justificacion": "No se definió proceso de aceptación. Sin esto, el Prestador puede entregar y el Cliente nunca 'aceptar' formalmente, bloqueando los pagos."
            }
        ],
        "next_steps": [
            {"paso": "Definir monto final: USD 40K con app o USD 38K sin app mobile", "responsable": "CLIENTE", "urgencia": "INMEDIATO"},
            {"paso": "Cerrar porcentaje de penalidad (3% vs 5%) y tope (15% vs 20%)", "responsable": "ABOGADO", "urgencia": "INMEDIATO"},
            {"paso": "Acordar horas de mejoras mensuales (8 vs 20) y alcance de no competencia", "responsable": "ABOGADO", "urgencia": "ESTA_SEMANA"},
            {"paso": "Definir separación de PI genérica vs específica con ejemplos concretos", "responsable": "ABOGADO", "urgencia": "ESTA_SEMANA"},
            {"paso": "Redactar Anexo Técnico con especificaciones, wireframes y criterios de aceptación", "responsable": "PRESTADOR", "urgencia": "ANTES_DE_FIRMAR"},
            {"paso": "Revisar contrato final con abogado de ambas partes", "responsable": "ABOGADO", "urgencia": "ANTES_DE_FIRMAR"}
        ]
    }


def main():
    print(f"\n{BOLD}📧 LEGALFLOW — GMAIL AGENT v0.1{RESET}")
    print(f"   Buscá negociaciones en Gmail y generá contratos automáticamente\n")

    # Paso 1: Verificar si se pasó un archivo directamente
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        filepath = sys.argv[1]
        print(f"  📄 Leyendo emails desde: {filepath}")
        with open(filepath, "r") as f:
            emails_text = f.read()
        print(f"  {GREEN}✅ Emails cargados. Procesando con IA...{RESET}")
        print(f"\n  ⏳ Analizando negociación y generando contrato...")
        resultado = analizar_con_claude(emails_text)
        if not resultado:
            print(f"  {YELLOW}Sin API key. Usando análisis demo de los emails.{RESET}")
            resultado = demo_resultado()
        mostrar_extraccion(resultado)
        output_path = os.path.join(os.path.dirname(__file__), "gmail_contrato.json")
        with open(output_path, "w") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        print(f"\n  💾 Resultado guardado en: {output_path}")
        return

    # Paso 1b: Qué buscar en Gmail
    if len(sys.argv) > 1:
        busqueda = " ".join(sys.argv[1:])
    else:
        print(f"  {CYAN}¿Qué querés buscar en Gmail?{RESET}")
        print(f"  Ejemplos: 'propuesta e-commerce', 'contrato servicios', 'NDA'")
        busqueda = input(f"\n  🔍 Buscar: ").strip()

    if not busqueda:
        print(f"  {RED}No ingresaste nada. Saliendo.{RESET}")
        return

    # Paso 2: Buscar en Gmail
    gmail_query = f"subject:({busqueda}) -in:draft"
    print(f"\n  ⏳ Buscando en Gmail: '{busqueda}'...")

    threads = buscar_en_gmail(gmail_query)

    if not threads or not threads.get("threads"):
        print(f"  {YELLOW}No encontré emails con '{busqueda}'.{RESET}")
        print(f"  Probá con otros términos.")
        return

    thread_list = threads["threads"]
    print(f"\n  {GREEN}✅ Encontré {len(thread_list)} conversación(es):{RESET}\n")

    for i, t in enumerate(thread_list, 1):
        print(f"  {BOLD}{i}.{RESET} {t.get('subject', 'Sin asunto')}")
        print(f"     De: {t.get('sender', '?')} | {t.get('date', '?')}")
        print(f"     {t.get('snippet', '')[:80]}...")
        print()

    # Paso 3: Elegir thread
    if len(thread_list) == 1:
        seleccion = 1
    else:
        seleccion = input(f"  ¿Cuál querés analizar? (1-{len(thread_list)}, o 'todos'): ").strip()
        if seleccion.lower() == "todos":
            seleccion = None
        else:
            try:
                seleccion = int(seleccion)
            except ValueError:
                seleccion = 1

    # Paso 4: Obtener contenido completo
    print(f"\n  ⏳ Extrayendo contenido de los emails...")

    emails_text = ""
    threads_to_process = thread_list if seleccion is None else [thread_list[seleccion - 1]]

    for t in threads_to_process:
        thread_data = obtener_thread(t["id"])
        if thread_data and thread_data.get("messages"):
            for msg in thread_data["messages"]:
                emails_text += f"\n=== EMAIL — De: {msg.get('sender', '?')} — Fecha: {msg.get('date', '?')} ===\n"
                emails_text += f"Asunto: {msg.get('subject', 'Sin asunto')}\n\n"
                emails_text += msg.get("body", msg.get("snippet", "")) + "\n"

    if not emails_text.strip():
        print(f"  {RED}No se pudo extraer contenido de los emails.{RESET}")
        return

    print(f"  {GREEN}✅ Emails extraídos. Procesando con IA...{RESET}")

    # Paso 5: Analizar con Claude
    print(f"\n  ⏳ Analizando negociación y generando contrato...")
    resultado = analizar_con_claude(emails_text)

    if not resultado:
        print(f"  {RED}No se pudo generar el análisis. Intentá de nuevo.{RESET}")
        return

    # Paso 6: Mostrar resultado
    mostrar_extraccion(resultado)

    # Paso 7: Guardar
    output_path = os.path.join(os.path.dirname(__file__), "gmail_contrato.json")
    with open(output_path, "w") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 Resultado guardado en: {output_path}")

    # Paso 8: Exportar contrato como texto
    contrato = resultado.get("contrato", {})
    if contrato:
        contrato_path = os.path.join(os.path.dirname(__file__), "contrato_borrador.txt")
        with open(contrato_path, "w") as f:
            f.write(f"{contrato.get('titulo', 'CONTRATO')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"{contrato.get('preambulo', '')}\n\n")
            for cl in contrato.get("clausulas", []):
                f.write(f"CLÁUSULA {cl['numero']} — {cl['titulo']}\n")
                f.write(f"{cl.get('texto', '')}\n\n")
            if resultado.get("clausulas_sugeridas"):
                f.write("\n--- CLÁUSULAS SUGERIDAS (revisar antes de incluir) ---\n\n")
                for cs in resultado["clausulas_sugeridas"]:
                    f.write(f"{cs['titulo']}\n")
                    f.write(f"{cs.get('texto', '')}\n")
                    f.write(f"Justificación: {cs.get('justificacion', '')}\n\n")
        print(f"  📄 Contrato exportado en: {contrato_path}")


if __name__ == "__main__":
    main()

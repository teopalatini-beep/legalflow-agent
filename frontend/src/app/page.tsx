import Link from "next/link";
import Navbar from "@/components/ui/Navbar";
import Footer from "@/components/ui/Footer";

const features = [
  {
    title: "Ingreso de contratos desde email o carga manual",
    description:
      "Conecta Gmail u Outlook para buscar contratos recibidos, o sube PDF/DOCX en segundos.",
  },
  {
    title: "Revision por capas para decidir rapido",
    description:
      "Primero ves lo critico, despues las partes y datos clave, y finalmente el analisis completo.",
  },
  {
    title: "Human-in-the-loop con trazabilidad",
    description:
      "El abogado mantiene control final, valida sugerencias y despacha con historial auditable.",
  },
];

const benchmarkKpis = [
  {
    metric: "92 min -> 26 seg",
    description: "Benchmark NDA: tiempo promedio humano vs IA en issue spotting.",
    source: "LawGeex Benchmark Study (2018)",
  },
  {
    metric: "94% vs 85%",
    description: "Benchmark NDA: precision promedio IA vs abogados participantes.",
    source: "LawGeex Benchmark Study (2018)",
  },
  {
    metric: "11.6 - 13.7 semanas",
    description: "Tiempo medio reportado para contratos de complejidad media.",
    source: "WorldCC data 2023 (publicado 2025)",
  },
  {
    metric: "19 dias -> 3 dias",
    description: "Brecha de turnaround entre equipos manuales y mas automatizados.",
    source: "SpotDraft Efficiency Benchmark 2025",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen">
      <Navbar />

      <section className="relative overflow-hidden border-b border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 text-white">
        <div className="mx-auto w-full max-w-7xl px-6 py-24">
          <div className="max-w-3xl">
            <span className="inline-flex rounded-full border border-blue-300/30 bg-blue-400/10 px-3 py-1 text-xs font-semibold text-blue-200">
              Legal ops con evidencia de mercado
            </span>

            <h1 className="mt-6 text-4xl font-bold leading-tight md:text-6xl">
              Reduce el tiempo de revision contractual,
              <span className="text-blue-300"> sin perder criterio legal humano</span>.
            </h1>

            <p className="mt-6 max-w-2xl text-lg text-slate-300">
              Tu equipo entra desde email o carga manual, analiza riesgos por prioridad y decide
              con un flujo operativo claro para abogados.
            </p>

            <div className="mt-10 flex flex-wrap gap-4">
              <Link
                href="/dashboard"
                className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-900/30 hover:bg-blue-700"
              >
                Abrir pagina operativa
              </Link>
              <Link
                href="/demo"
                className="rounded-xl border border-white/30 px-6 py-3 font-semibold text-white hover:bg-white/10"
              >
                Ver flujo demo
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-6 py-16">
        <div className="max-w-3xl">
          <h2 className="text-3xl font-bold text-slate-900 md:text-4xl">
            KPIs reales para justificar la mejora
          </h2>
          <p className="mt-4 text-slate-600">
            Estos indicadores son benchmarks externos y deben leerse como referencia de mercado.
          </p>
        </div>
        <div className="mt-10 grid gap-6 md:grid-cols-2">
          {benchmarkKpis.map((kpi) => (
            <article
              key={`${kpi.metric}-${kpi.source}`}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <p className="text-3xl font-bold text-slate-900">{kpi.metric}</p>
              <p className="mt-3 text-sm leading-6 text-slate-700">{kpi.description}</p>
              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-blue-700">
                Fuente: {kpi.source}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section id="features" className="mx-auto w-full max-w-7xl px-6 py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-bold text-slate-900 md:text-4xl">
            Landing orientada a conversion + producto orientado a ejecucion
          </h2>
          <p className="mt-4 text-slate-600">
            El mensaje comercial y el flujo operativo estan alineados con como trabaja un abogado
            in-house en el dia a dia.
          </p>
        </div>

        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {features.map((f) => (
            <article
              key={f.title}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
            >
              <h3 className="text-lg font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-3 text-sm leading-6 text-slate-600">{f.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="how" className="border-y border-slate-200 bg-white">
        <div className="mx-auto w-full max-w-7xl px-6 py-20">
          <h2 className="text-3xl font-bold text-slate-900">Flujo operativo del abogado</h2>
          <p className="mt-3 text-slate-600">
            Diseñado para pasar de "me llego un contrato" a "tengo decision y plan de accion".
          </p>

          <div className="mt-10 grid gap-4 md:grid-cols-5">
            {[
              "Entrada: Gmail/Outlook o Upload",
              "Analisis y extraccion",
              "Vista 1: Lo importante",
              "Vista 2: Partes y datos clave",
              "Vista 3: Descripcion completa",
            ].map((step, i) => (
              <div
                key={step}
                className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center"
              >
                <div className="mx-auto mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                  {i + 1}
                </div>
                <p className="text-sm font-semibold text-slate-800">{step}</p>
              </div>
            ))}
          </div>

          <div className="mt-8">
            <Link
              href="/dashboard"
              className="inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Probar pagina operativa
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-6 py-20">
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-8 md:p-10">
          <h3 className="text-2xl font-bold text-slate-900">
            Nota metodologica para la landing
          </h3>
          <p className="mt-3 text-slate-600">
            Recomiendo mantener claims de benchmark con la fuente visible y aclarar que los
            resultados propios dependen de tipo de contrato, calidad documental y proceso interno.
          </p>
          <div className="mt-6 space-y-2 text-sm text-slate-700">
            <p>
              1) LawGeex Benchmark Study (2018): 92 min vs 26 seg, 94% vs 85%.
            </p>
            <p>
              2) WorldCC (data 2023, publicacion 2025): 11.6 y 13.7 semanas en complejidad media.
            </p>
            <p>
              3) SpotDraft Benchmark (2025): diferencia de velocidad entre equipos manuales y con
              mayor automatizacion.
            </p>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}

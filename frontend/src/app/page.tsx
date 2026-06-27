import Link from "next/link";
import Navbar from "@/components/ui/Navbar";
import Footer from "@/components/ui/Footer";

const features = [
  {
    title: "Analisis contractual con IA",
    description:
      "Extrae clausulas, identifica riesgos y sugiere redlines con evidencia para revision legal.",
  },
  {
    title: "Human-in-the-Loop real",
    description:
      "El abogado valida, corrige y aprueba manualmente con trazabilidad de usuario y timestamp.",
  },
  {
    title: "Enrutamiento inteligente",
    description:
      "Clasificacion por tipo y riesgo con reglas fijas y validacion final antes del despacho.",
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
              MVP End-to-End para estudios juridicos
            </span>

            <h1 className="mt-6 text-4xl font-bold leading-tight md:text-6xl">
              Automatiza el flujo legal con IA,
              <span className="text-blue-300"> sin perder control humano</span>.
            </h1>

            <p className="mt-6 max-w-2xl text-lg text-slate-300">
              Desde la ingesta de contratos hasta el despacho final: analisis, validacion del
              abogado y enrutamiento inteligente en una sola plataforma.
            </p>

            <div className="mt-10 flex flex-wrap gap-4">
              <Link
                href="/demo"
                className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-900/30 hover:bg-blue-700"
              >
                Ver Workflow Demo
              </Link>
              <Link
                href="/dashboard"
                className="rounded-xl border border-white/30 px-6 py-3 font-semibold text-white hover:bg-white/10"
              >
                Ir al Dashboard
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto w-full max-w-7xl px-6 py-20">
        <div className="max-w-2xl">
          <h2 className="text-3xl font-bold text-slate-900 md:text-4xl">
            Propuesta de valor LegalFlow
          </h2>
          <p className="mt-4 text-slate-600">
            Reduce tiempos de revision, mejora consistencia legal y acelera decisiones con
            trazabilidad completa.
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
          <h2 className="text-3xl font-bold text-slate-900">Flujo End-to-End</h2>
          <p className="mt-3 text-slate-600">
            Pipeline visual orientado a operacion legal real.
          </p>

          <div className="mt-10 grid gap-4 md:grid-cols-5">
            {["Carga", "Analisis IA", "Enriquecimiento", "Validacion", "Despacho"].map(
              (step, i) => (
                <div
                  key={step}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-center"
                >
                  <div className="mx-auto mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
                    {i + 1}
                  </div>
                  <p className="text-sm font-semibold text-slate-800">{step}</p>
                </div>
              )
            )}
          </div>

          <div className="mt-8">
            <Link
              href="/demo"
              className="inline-flex rounded-lg bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Abrir Demo Interactiva
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-6 py-20">
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-8 md:p-10">
          <h3 className="text-2xl font-bold text-slate-900">
            Listo para pasar de prototipo a operacion legal real?
          </h3>
          <p className="mt-3 text-slate-600">
            Empieza por el workflow demo y luego valida en el dashboard del abogado.
          </p>
          <div className="mt-6 flex gap-3">
            <Link
              href="/demo"
              className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Workflow Demo
            </Link>
            <Link
              href="/dashboard"
              className="rounded-lg border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Dashboard
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}

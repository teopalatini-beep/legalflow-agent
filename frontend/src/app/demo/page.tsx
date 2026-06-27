"use client";

import { useState } from "react";
import Link from "next/link";
import { getHealth } from "@/lib/api";

export default function DemoPage() {
  const [healthState, setHealthState] = useState<string>("Sin verificar.");

  async function handleHealthCheck() {
    setHealthState("Verificando backend...");
    try {
      const health = await getHealth();
      setHealthState(`OK · ${health.service} · ${health.timestamp}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setHealthState(`Error: ${message}`);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-5xl">
        <h1 className="text-3xl font-bold text-slate-900">Workflow Demo</h1>
        <p className="mt-2 text-slate-600">
          Aqui ira el pipeline visual en tiempo real: Carga -&gt; Analisis -&gt; Enriquecimiento
          -&gt; Validacion -&gt; Despacho.
        </p>

        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6">
          <p className="text-sm text-slate-500">
            Placeholder inicial para demo visual. Este modulo ya puede verificar conexion con el
            backend Python.
          </p>
          <button
            type="button"
            onClick={handleHealthCheck}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
          >
            Probar conexion backend
          </button>
          <p className="mt-3 text-sm text-slate-700">{healthState}</p>
        </div>

        <Link href="/" className="mt-6 inline-block text-sm font-semibold text-blue-600">
          &larr; Volver a Landing
        </Link>
      </div>
    </main>
  );
}

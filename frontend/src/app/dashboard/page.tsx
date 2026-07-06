"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  analyzeContractFile,
  connectInbox,
  createESignEnvelope,
  createMatter,
  createRecipientView,
  dispatchRouting,
  getRoutingQueue,
  searchInbox,
  simulateSignedWebhook,
} from "@/lib/api";
import type {
  AnalyzeContractUploadAnalysis,
  InboxProvider,
  RoutingQueueItem,
} from "@/types/contract";

type HitlFormState = {
  contractType: string;
  partiesInvolved: string;
  riskLevel: string;
  keyClauses: string;
  summary: string;
  recommendedAction: string;
  qualityScore: string;
  riskItemsJson: string;
  reviewerComment: string;
};

type ResultViewTab = "important" | "parties" | "full";

function parseLines(value: string): string[] {
  return value
    .split(/\n|,/g)
    .map((x) => x.trim())
    .filter(Boolean);
}

function parseRiskItems(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

export default function DashboardPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [status, setStatus] = useState("Listo para analizar.");
  const [analysis, setAnalysis] = useState<AnalyzeContractUploadAnalysis | null>(null);
  const [matterId, setMatterId] = useState("");
  const [envelopeId, setEnvelopeId] = useState("");
  const [recipientId, setRecipientId] = useState("");
  const [approvalPayload, setApprovalPayload] = useState<Record<string, unknown> | null>(null);
  const [dispatchResult, setDispatchResult] = useState<Record<string, unknown> | null>(null);
  const [isDispatching, setIsDispatching] = useState(false);
  const [queueTab, setQueueTab] = useState<"pending" | "dispatched">("pending");
  const [pendingQueue, setPendingQueue] = useState<RoutingQueueItem[]>([]);
  const [dispatchedQueue, setDispatchedQueue] = useState<RoutingQueueItem[]>([]);
  const [queueRiskFilter, setQueueRiskFilter] = useState("all");
  const [queueDestinationFilter, setQueueDestinationFilter] = useState("all");
  const [queueCounts, setQueueCounts] = useState({
    pending_review: 0,
    dispatched_history: 0,
    total: 0,
  });
  const [hitlForm, setHitlForm] = useState<HitlFormState>({
    contractType: "",
    partiesInvolved: "",
    riskLevel: "",
    keyClauses: "",
    summary: "",
    recommendedAction: "",
    qualityScore: "0",
    riskItemsJson: "[]",
    reviewerComment: "",
  });
  const [inboxProvider, setInboxProvider] = useState<InboxProvider>("gmail");
  const [isInboxConnected, setIsInboxConnected] = useState(false);
  const [mailSearch, setMailSearch] = useState("contrato OR acuerdo OR NDA");
  const [mailResults, setMailResults] = useState<string[]>([]);
  const [isInboxLoading, setIsInboxLoading] = useState(false);
  const [resultViewTab, setResultViewTab] = useState<ResultViewTab>("important");

  const riskCount = useMemo(() => analysis?.risk_items?.length || 0, [analysis]);
  const isPdfFile = selectedFile ? selectedFile.name.toLowerCase().endsWith(".pdf") : false;
  const activeQueueItems = useMemo(
    () => (queueTab === "pending" ? pendingQueue : dispatchedQueue),
    [queueTab, pendingQueue, dispatchedQueue]
  );
  const queueRiskOptions = useMemo(() => {
    const values = new Set<string>();
    activeQueueItems.forEach((item) => values.add((item.risk_level || "unknown").toLowerCase()));
    return Array.from(values).sort();
  }, [activeQueueItems]);
  const queueDestinationOptions = useMemo(() => {
    const values = new Set<string>();
    activeQueueItems.forEach((item) => values.add((item.destination || "sin_destino").toLowerCase()));
    return Array.from(values).sort();
  }, [activeQueueItems]);
  const filteredQueueItems = useMemo(() => {
    return activeQueueItems.filter((item) => {
      const riskMatch =
        queueRiskFilter === "all" ||
        (item.risk_level || "unknown").toLowerCase() === queueRiskFilter;
      const destinationMatch =
        queueDestinationFilter === "all" ||
        (item.destination || "sin_destino").toLowerCase() === queueDestinationFilter;
      return riskMatch && destinationMatch;
    });
  }, [activeQueueItems, queueRiskFilter, queueDestinationFilter]);
  const topRiskItems = useMemo(() => analysis?.risk_items?.slice(0, 3) || [], [analysis]);
  const parsedQualityScore = Number(hitlForm.qualityScore) || 0;
  const parsedParties = useMemo(() => parseLines(hitlForm.partiesInvolved), [hitlForm.partiesInvolved]);
  const parsedKeyClauses = useMemo(() => parseLines(hitlForm.keyClauses), [hitlForm.keyClauses]);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [selectedFile]);

  useEffect(() => {
    void refreshQueue();
  }, []);

  useEffect(() => {
    setQueueRiskFilter("all");
    setQueueDestinationFilter("all");
  }, [queueTab]);

  useEffect(() => {
    if (!analysis) return;
    setHitlForm({
      contractType: analysis.contract_type || "",
      partiesInvolved: (analysis.parties_involved || []).join("\n"),
      riskLevel: analysis.risk_level || "",
      keyClauses: (analysis.key_clauses || []).join("\n"),
      summary: analysis.summary || "",
      recommendedAction: analysis.recommended_action || "",
      qualityScore: String(analysis.quality_score ?? 0),
      riskItemsJson: JSON.stringify(analysis.risk_items || [], null, 2),
      reviewerComment: "",
    });
  }, [analysis]);

  function isSupportedFile(file: File): boolean {
    const lower = file.name.toLowerCase();
    return lower.endsWith(".pdf") || lower.endsWith(".docx");
  }

  function handleSelectFile(file: File | null) {
    if (!file) return;
    if (!isSupportedFile(file)) {
      setStatus("Formato no soportado. Sube un archivo .pdf o .docx.");
      return;
    }
    setSelectedFile(file);
    setStatus(`Archivo seleccionado: ${file.name}`);
  }

  function handleDrop(event: React.DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0] || null;
    handleSelectFile(file);
  }

  async function handleAnalyzeFile() {
    if (!selectedFile) {
      setStatus("Primero selecciona un archivo PDF o DOCX.");
      return;
    }
    setStatus("Analizando archivo con IA...");
    try {
      const response = await analyzeContractFile(selectedFile, {
        mode: "local",
        model: "composer-2.5",
        clientId: "default",
        analysisMode: "strict_playbook",
      });
      setAnalysis(response.analysis);
      setApprovalPayload(null);
      try {
        const created = await createMatter({
          cliente_id: "default",
          title: `Matter ${selectedFile.name}`,
          analysis_result: response.analysis as unknown as Record<string, unknown>,
          obligations: [],
        });
        setMatterId(created.matter.matter_id);
        setStatus(
          `Analisis completado y enviado a Pendientes de Revision. Matter: ${created.matter.matter_id}`
        );
      } catch (createErr) {
        const createMessage =
          createErr instanceof Error ? createErr.message : "Error creando matter";
        setStatus(`Analisis completado, pero no se pudo crear matter: ${createMessage}`);
      }
      await refreshQueue();
      setQueueTab("pending");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error analizando archivo: ${message}`);
    }
  }

  async function handleConnectInbox() {
    setIsInboxLoading(true);
    try {
      const response = await connectInbox(inboxProvider);
      setIsInboxConnected(true);
      setStatus(
        `${inboxProvider === "gmail" ? "Gmail" : "Outlook"} conectado en modo ${
          response.integration.mode
        }. Ya puedes buscar contratos por email.`
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error conectando inbox: ${message}`);
    } finally {
      setIsInboxLoading(false);
    }
  }

  async function handleSearchInbox() {
    if (!isInboxConnected) {
      setStatus("Primero conecta Gmail u Outlook para buscar contratos.");
      return;
    }
    setIsInboxLoading(true);
    try {
      const response = await searchInbox(inboxProvider, mailSearch);
      const results = response.integration.results || [];
      setMailResults(
        results.map(
          (item) =>
            `${item.subject}${item.has_contract_attachment_hint ? " · adjunto detectado" : ""}`
        )
      );
      const providerLabel = inboxProvider === "gmail" ? "Gmail" : "Outlook";
      setStatus(
        `Busqueda completada en ${providerLabel} (${response.integration.mode}) con ${results.length} resultados.`
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error buscando en inbox: ${message}`);
    } finally {
      setIsInboxLoading(false);
    }
  }

  function updateHitlField<K extends keyof HitlFormState>(key: K, value: HitlFormState[K]) {
    setHitlForm((prev) => ({ ...prev, [key]: value }));
  }

  async function refreshQueue() {
    try {
      const queue = await getRoutingQueue();
      setPendingQueue(queue.pending_review || []);
      setDispatchedQueue(queue.dispatched_history || []);
      setQueueCounts(queue.counts || { pending_review: 0, dispatched_history: 0, total: 0 });
    } catch {
      // Evita bloquear el dashboard si falla solo la carga de bandeja.
    }
  }

  function pickQueueItem(item: RoutingQueueItem) {
    setMatterId(item.matter_id || "");
    setStatus(`Seleccionado en bandeja: ${item.matter_id} (${item.status})`);
  }

  async function handleApproveForRouting() {
    if (!analysis) {
      setStatus("No hay analisis para aprobar.");
      return;
    }
    if (!matterId) {
      setStatus("Primero crea matter para poder despachar.");
      return;
    }
    const payload = {
      approved_at: new Date().toISOString(),
      approved_by: "lawyer@demo.local",
      source_file: selectedFile?.name || null,
      run_id: analysis.run_id || null,
      matter_id: matterId,
      analysis_reviewed: {
        contract_type: hitlForm.contractType,
        parties_involved: parseLines(hitlForm.partiesInvolved),
        risk_level: hitlForm.riskLevel,
        key_clauses: parseLines(hitlForm.keyClauses),
        summary: hitlForm.summary,
        recommended_action: hitlForm.recommendedAction,
        quality_score: Number(hitlForm.qualityScore) || 0,
        reviewer_comment: hitlForm.reviewerComment,
        risk_items: parseRiskItems(hitlForm.riskItemsJson),
      },
      routing: {
        status: "pending_routing_validation",
        suggested_destination:
          hitlForm.riskLevel.toLowerCase() === "alto" || hitlForm.riskLevel.toLowerCase() === "high"
            ? "senior_reviewer"
            : "legal_ops",
      },
    };
    setApprovalPayload(payload);
    setIsDispatching(true);
    setDispatchResult(null);
    setStatus("Aprobando y despachando...");
    try {
      const response = await dispatchRouting(payload);
      setDispatchResult(response.dispatch as unknown as Record<string, unknown>);
      setStatus(
        `Despacho completado. Estado: ${response.dispatch.status} -> ${response.dispatch.destination}`
      );
      await refreshQueue();
      setQueueTab("dispatched");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error en despacho: ${message}`);
    } finally {
      setIsDispatching(false);
    }
  }

  async function handleCreateMatter() {
    if (!analysis) {
      setStatus("Primero ejecuta el analisis del archivo.");
      return;
    }
    setStatus("Creando matter...");
    try {
      const response = await createMatter({
        cliente_id: "default",
        title: "Matter creado desde dashboard Next",
        analysis_result: analysis as unknown as Record<string, unknown>,
        obligations: [],
      });
      setMatterId(response.matter.matter_id);
      setStatus(`Matter creado: ${response.matter.matter_id}`);
      await refreshQueue();
      setQueueTab("pending");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error creando matter: ${message}`);
    }
  }

  async function handleStartSigning() {
    if (!matterId) {
      setStatus("Primero crea matter.");
      return;
    }
    setStatus("Iniciando firma...");
    try {
      const response = await createESignEnvelope(matterId, "legal@acme.com");
      setEnvelopeId(response.integration.envelope_id || "");
      setRecipientId(response.integration.recipient_id || "");
      setStatus(
        `Firma iniciada (${response.integration.mode}). envelope_id: ${
          response.integration.envelope_id || "-"
        }`
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error iniciando firma: ${message}`);
    }
  }

  async function handleRecipientView() {
    if (!matterId) {
      setStatus("Primero crea matter.");
      return;
    }
    setStatus("Generando recipient view...");
    try {
      const response = await createRecipientView(matterId);
      const url = response.integration.signing_url || "";
      setStatus(url ? "Recipient view generada." : "Recipient view sin URL.");
      if (url) window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error recipient view: ${message}`);
    }
  }

  async function handleMarkSigned() {
    if (!matterId || !envelopeId) {
      setStatus("Necesitas matter_id y envelope_id antes de marcar firmado.");
      return;
    }
    setStatus("Simulando webhook signed...");
    try {
      const response = await simulateSignedWebhook(matterId, envelopeId, recipientId);
      setStatus(`Webhook OK. Estado: ${response.status}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Error desconocido";
      setStatus(`Error webhook: ${message}`);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 p-8">
      <div className="mx-auto max-w-7xl">
        <h1 className="text-3xl font-bold text-slate-900">Dashboard del Abogado</h1>
        <p className="mt-2 text-slate-600">
          Flujo operativo: entrada por Gmail/Outlook o upload manual, analisis IA y validacion
          legal por vistas priorizadas.
        </p>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">Entrada desde correo corporativo</h2>
          <p className="mt-1 text-sm text-slate-600">
            Simula conexion OAuth para que el abogado busque contratos recibidos por email antes de
            subir manualmente.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <label className="text-xs font-semibold text-slate-700">
              Proveedor
              <select
                value={inboxProvider}
                onChange={(e) => setInboxProvider(e.target.value as InboxProvider)}
                className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal text-slate-800"
              >
                <option value="gmail">Gmail</option>
                <option value="outlook">Outlook</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700 md:col-span-2">
              Query de busqueda
              <input
                value={mailSearch}
                onChange={(e) => setMailSearch(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal outline-none focus:border-blue-500"
                placeholder="ej: contrato OR acuerdo OR NDA"
              />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleConnectInbox}
              disabled={isInboxLoading}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              {isInboxLoading
                ? "Conectando..."
                : isInboxConnected
                  ? "Conectado"
                  : `Conectar ${inboxProvider === "gmail" ? "Gmail" : "Outlook"}`}
            </button>
            <button
              type="button"
              onClick={handleSearchInbox}
              disabled={isInboxLoading || !isInboxConnected}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              {isInboxLoading ? "Buscando..." : "Buscar contratos en email"}
            </button>
          </div>
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
              Resultados de correo (demo)
            </p>
            {mailResults.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">
                Sin resultados aun. Conecta proveedor y ejecuta una busqueda.
              </p>
            ) : (
              <ul className="mt-2 space-y-2">
                {mailResults.map((item) => (
                  <li key={item} className="rounded-md border border-slate-200 bg-white p-2 text-sm text-slate-700">
                    {item}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">Carga de contrato</h2>
          <p className="mt-1 text-sm text-slate-600">
            Alternativa manual para casos donde no quieres ingresar por correo.
          </p>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              setDragActive(false);
            }}
            onDrop={handleDrop}
            className={`mt-3 rounded-lg border-2 border-dashed p-6 text-center transition ${
              dragActive ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50"
            }`}
          >
            <p className="text-sm text-slate-700">
              Arrastra tu contrato aqui o selecciona un archivo.
            </p>
            <p className="mt-1 text-xs text-slate-500">Formatos soportados: .pdf, .docx</p>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-4 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Seleccionar archivo
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(e) => handleSelectFile(e.target.files?.[0] || null)}
            />
            <p className="mt-3 text-xs text-slate-600">
              {selectedFile ? `Archivo: ${selectedFile.name}` : "Ningun archivo seleccionado."}
            </p>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleAnalyzeFile}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Analizar archivo
            </button>
            <button
              type="button"
              onClick={handleCreateMatter}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
            >
              Crear matter
            </button>
            <button
              type="button"
              onClick={handleStartSigning}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700"
            >
              Iniciar firma
            </button>
            <button
              type="button"
              onClick={handleRecipientView}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Abrir firma
            </button>
            <button
              type="button"
              onClick={handleMarkSigned}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              Marcar signed
            </button>
          </div>
          <p className="mt-3 text-sm text-slate-600">{status}</p>
        </section>

        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">Bandeja del Abogado</h2>
            <button
              type="button"
              onClick={() => void refreshQueue()}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100"
            >
              Refrescar
            </button>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setQueueTab("pending")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                queueTab === "pending"
                  ? "bg-blue-600 text-white"
                  : "border border-slate-300 bg-white text-slate-800"
              }`}
            >
              Pendientes de Revision ({queueCounts.pending_review})
            </button>
            <button
              type="button"
              onClick={() => setQueueTab("dispatched")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                queueTab === "dispatched"
                  ? "bg-emerald-600 text-white"
                  : "border border-slate-300 bg-white text-slate-800"
              }`}
            >
              Despachados / Historial ({queueCounts.dispatched_history})
            </button>
          </div>

          <div className="mt-3 grid gap-2 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-700">
              Riesgo
              <select
                value={queueRiskFilter}
                onChange={(e) => setQueueRiskFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm font-normal text-slate-800"
              >
                <option value="all">Todos</option>
                {queueRiskOptions.map((risk) => (
                  <option key={risk} value={risk}>
                    {risk}
                  </option>
                ))}
              </select>
            </label>

            <label className="flex flex-col gap-1 text-xs font-semibold text-slate-700">
              Destino
              <select
                value={queueDestinationFilter}
                onChange={(e) => setQueueDestinationFilter(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm font-normal text-slate-800"
              >
                <option value="all">Todos</option>
                {queueDestinationOptions.map((destination) => (
                  <option key={destination} value={destination}>
                    {destination}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end">
              <button
                type="button"
                onClick={() => {
                  setQueueRiskFilter("all");
                  setQueueDestinationFilter("all");
                }}
                className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100"
              >
                Limpiar filtros
              </button>
            </div>
          </div>

          <div className="mt-4 max-h-64 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
            {filteredQueueItems.length === 0 && (
              <p className="text-sm text-slate-500">
                {queueTab === "pending"
                  ? "Sin contratos pendientes para ese filtro."
                  : "Sin contratos despachados en historial para ese filtro."}
              </p>
            )}
            {filteredQueueItems.map((item) => (
              <button
                key={`${item.matter_id}-${item.updated_at || item.created_at || "x"}`}
                type="button"
                onClick={() => pickQueueItem(item)}
                className="mb-2 w-full rounded-lg border border-slate-200 bg-white p-3 text-left hover:bg-slate-100"
              >
                <p className="text-sm font-semibold text-slate-900">{item.title || item.matter_id}</p>
                <p className="text-xs text-slate-600">
                  matter_id: {item.matter_id} · status: {item.status}
                </p>
                <p className="text-xs text-slate-500">
                  riesgo: {item.risk_level || "-"} · destino: {item.destination || "-"}
                </p>
              </button>
            ))}
          </div>
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-slate-900">Contrato original (visor)</h2>
            <div className="mt-3 h-[740px] rounded-lg border border-slate-200 bg-slate-50 p-3">
              {!selectedFile && (
                <div className="flex h-full items-center justify-center text-sm text-slate-500">
                  Sube un archivo para visualizarlo aqui.
                </div>
              )}
              {selectedFile && isPdfFile && previewUrl && (
                <iframe
                  src={previewUrl}
                  title="PDF preview"
                  className="h-full w-full rounded border border-slate-300 bg-white"
                />
              )}
              {selectedFile && !isPdfFile && (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-slate-600">
                  <p className="font-semibold">{selectedFile.name}</p>
                  <p>
                    Preview visual para DOCX no habilitado en navegador. El archivo si se analiza
                    por backend.
                  </p>
                </div>
              )}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-lg font-semibold text-slate-900">
              Resultado estructurado + validacion HITL
            </h2>
            <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              <p>
                <strong>run_id:</strong> {analysis?.run_id || "-"}
              </p>
              <p>
                <strong>matter_id:</strong> {matterId || "-"}
              </p>
              <p>
                <strong>riesgos detectados:</strong> {riskCount}
              </p>
              <p>
                <strong>envelope_id:</strong> {envelopeId || "-"}
              </p>
            </div>

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setResultViewTab("important")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                  resultViewTab === "important"
                    ? "bg-rose-600 text-white"
                    : "border border-slate-300 bg-white text-slate-800"
                }`}
              >
                1) Lo importante
              </button>
              <button
                type="button"
                onClick={() => setResultViewTab("parties")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                  resultViewTab === "parties"
                    ? "bg-blue-600 text-white"
                    : "border border-slate-300 bg-white text-slate-800"
                }`}
              >
                2) Partes y datos clave
              </button>
              <button
                type="button"
                onClick={() => setResultViewTab("full")}
                className={`rounded-lg px-4 py-2 text-sm font-semibold ${
                  resultViewTab === "full"
                    ? "bg-slate-900 text-white"
                    : "border border-slate-300 bg-white text-slate-800"
                }`}
              >
                3) Descripcion completa
              </button>
            </div>

            {resultViewTab === "important" && (
              <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-slate-800">
                <p className="font-semibold text-rose-900">Resumen ejecutivo para decision rapida</p>
                <div className="mt-2 grid gap-2 md:grid-cols-3">
                  <p>
                    <strong>Riesgo:</strong> {hitlForm.riskLevel || "-"}
                  </p>
                  <p>
                    <strong>Accion sugerida:</strong> {hitlForm.recommendedAction || "-"}
                  </p>
                  <p>
                    <strong>Quality score:</strong> {parsedQualityScore}
                  </p>
                </div>
                <p className="mt-3 text-slate-700">{hitlForm.summary || "Sin resumen aun."}</p>
                <div className="mt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-rose-800">
                    Top riesgos detectados
                  </p>
                  {topRiskItems.length === 0 ? (
                    <p className="mt-1 text-sm text-slate-600">Sin riesgos cargados aun.</p>
                  ) : (
                    <ul className="mt-2 space-y-2">
                      {topRiskItems.map((item, idx) => (
                        <li
                          key={`${item.riesgo}-${idx}`}
                          className="rounded-md border border-rose-200 bg-white p-2"
                        >
                          <p className="font-semibold text-slate-900">
                            {item.riesgo} · {item.nivel}
                          </p>
                          <p className="text-slate-700">{item.recomendacion}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}

            {resultViewTab === "parties" && (
              <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-slate-800">
                <p className="font-semibold text-blue-900">Partes y puntos clave del contrato</p>
                <div className="mt-3 grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">
                      Partes
                    </p>
                    {parsedParties.length === 0 ? (
                      <p className="mt-1 text-slate-600">Sin partes cargadas.</p>
                    ) : (
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {parsedParties.map((party) => (
                          <li key={party}>{party}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">
                      Clausulas clave
                    </p>
                    {parsedKeyClauses.length === 0 ? (
                      <p className="mt-1 text-slate-600">Sin clausulas cargadas.</p>
                    ) : (
                      <ul className="mt-2 list-disc space-y-1 pl-5">
                        {parsedKeyClauses.map((clause) => (
                          <li key={clause}>{clause}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            )}

            {resultViewTab === "full" && (
              <div className="mt-4 rounded-lg border border-slate-300 bg-slate-50 p-4 text-sm text-slate-800">
                <p className="font-semibold text-slate-900">Descripcion completa</p>
                <p className="mt-2">
                  Esta vista consolida resumen, clausulas, riesgos y recomendacion para auditoria y
                  trazabilidad.
                </p>
                <pre className="mt-3 max-h-64 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                  {analysis ? JSON.stringify(analysis, null, 2) : "Sin resultado todavia."}
                </pre>
              </div>
            )}

            <div className="mt-4 grid gap-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Formulario editable para aprobacion legal final
              </p>
              <label className="text-xs font-semibold text-slate-700">Tipo de contrato</label>
              <input
                value={hitlForm.contractType}
                onChange={(e) => updateHitlField("contractType", e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">
                Partes involucradas (una por linea)
              </label>
              <textarea
                value={hitlForm.partiesInvolved}
                onChange={(e) => updateHitlField("partiesInvolved", e.target.value)}
                className="h-20 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Nivel de riesgo</label>
              <input
                value={hitlForm.riskLevel}
                onChange={(e) => updateHitlField("riskLevel", e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">
                Clausulas clave (una por linea)
              </label>
              <textarea
                value={hitlForm.keyClauses}
                onChange={(e) => updateHitlField("keyClauses", e.target.value)}
                className="h-24 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Resumen</label>
              <textarea
                value={hitlForm.summary}
                onChange={(e) => updateHitlField("summary", e.target.value)}
                className="h-24 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Accion recomendada</label>
              <textarea
                value={hitlForm.recommendedAction}
                onChange={(e) => updateHitlField("recommendedAction", e.target.value)}
                className="h-20 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Quality score</label>
              <input
                value={hitlForm.qualityScore}
                onChange={(e) => updateHitlField("qualityScore", e.target.value)}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Risk items (JSON)</label>
              <textarea
                value={hitlForm.riskItemsJson}
                onChange={(e) => updateHitlField("riskItemsJson", e.target.value)}
                className="h-40 rounded-lg border border-slate-300 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500"
              />

              <label className="text-xs font-semibold text-slate-700">Comentario del abogado</label>
              <textarea
                value={hitlForm.reviewerComment}
                onChange={(e) => updateHitlField("reviewerComment", e.target.value)}
                className="h-24 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500"
                placeholder="Explica ajustes o criterios de aprobacion..."
              />
            </div>

            <div className="mt-5">
              <button
                type="button"
                onClick={handleApproveForRouting}
                className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={!analysis || !matterId || isDispatching}
              >
                {isDispatching ? "Despachando..." : "Aprobar"}
              </button>
              <p className="mt-2 text-xs text-slate-500">
                Este boton deja listo el payload validado para el siguiente paso de enrutamiento.
              </p>
            </div>

            <pre className="mt-4 max-h-56 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
              {approvalPayload
                ? JSON.stringify(approvalPayload, null, 2)
                : "Payload de aprobacion aun no generado."}
            </pre>

            <pre className="mt-4 max-h-40 overflow-auto rounded-lg bg-emerald-950 p-3 text-xs text-emerald-100">
              {dispatchResult
                ? JSON.stringify(dispatchResult, null, 2)
                : "Resultado de despacho aun no disponible."}
            </pre>

            <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              <p>
                <strong>Snapshot tecnico del analisis (debug):</strong>
              </p>
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
                {analysis ? JSON.stringify(analysis, null, 2) : "Sin resultado todavia."}
              </pre>
            </div>
          </section>
        </div>

        <Link href="/" className="mt-6 inline-block text-sm font-semibold text-blue-600">
          &larr; Volver a Landing
        </Link>
      </div>
    </main>
  );
}

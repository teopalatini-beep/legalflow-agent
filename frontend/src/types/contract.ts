export type WorkflowMode = "local" | "sdk";
export type AnalysisMode =
  | "general"
  | "strict_playbook"
  | "counterparty_negotiation";

export interface ApiErrorResponse {
  ok: false;
  error: string;
  code?: string;
}

export interface HealthResponse {
  ok: true;
  service: string;
  timestamp: string;
}

export interface RiskItem {
  riesgo: string;
  nivel: string;
  recomendacion: string;
  confianza: number;
  clausula_relacionada?: string;
}

export interface RedlineItem {
  clausula: string;
  texto_sugerido: string;
  motivo: string;
}

export interface WorkflowMetrics {
  [key: string]: number | string | boolean | null | undefined;
}

export interface AnalyzeWorkflowResult {
  run_id?: string;
  resumen_final?: string;
  accion_recomendada?: string;
  clausulas_detectadas?: string[];
  obligaciones_principales?: string[];
  clausula_evidencias?: Record<string, string>;
  riesgos_detectados?: RiskItem[];
  redlines_sugeridos?: RedlineItem[];
  quality_score?: number;
  quality_warnings?: string[];
  metrics?: WorkflowMetrics;
}

export interface AnalyzeResponse {
  ok: true;
  resultado: AnalyzeWorkflowResult;
  comparacion?: {
    riesgos_version_a: number;
    riesgos_version_b: number;
    delta_riesgos: number;
    quality_a: number;
    quality_b: number;
  };
  resultado_b?: AnalyzeWorkflowResult;
}

export interface AnalyzeContractUploadAnalysis {
  run_id?: string;
  contract_type: string;
  parties_involved: string[];
  risk_level: string;
  key_clauses: string[];
  risk_items: RiskItem[];
  summary: string;
  recommended_action: string;
  quality_score: number;
}

export interface AnalyzeContractUploadResponse {
  ok: true;
  analysis: AnalyzeContractUploadAnalysis;
  metadata: {
    filename: string;
    mode: WorkflowMode;
    analysis_mode: AnalysisMode;
    duration_ms: number;
  };
}

export interface AnalyzeRequest {
  contrato: string;
  contrato_b?: string;
  modo?: WorkflowMode;
  modelo?: string;
  cliente_id?: string;
  modo_analisis?: AnalysisMode;
}

export interface Matter {
  matter_id: string;
  status: string;
  title?: string;
  cliente_id?: string;
  created_at?: string;
  updated_at?: string;
  analysis_result?: AnalyzeWorkflowResult;
  obligations?: Array<Record<string, unknown>>;
  events?: Array<Record<string, unknown>>;
  esign?: Record<string, unknown>;
}

export interface CreateMatterRequest {
  cliente_id: string;
  title: string;
  analysis_result?: AnalyzeWorkflowResult | Record<string, unknown>;
  obligations?: Array<Record<string, unknown>>;
}

export interface CreateMatterResponse {
  ok: true;
  matter: Matter;
}

export interface ESignIntegration {
  provider: string;
  mode: string;
  status?: string;
  envelope_id?: string;
  recipient_id?: string;
  signing_url?: string;
}

export interface IntegrationResponse {
  ok: true;
  integration: ESignIntegration;
}

export interface RoutingDispatchRequest {
  matter_id: string;
  approved_at: string;
  approved_by?: string;
  analysis_reviewed: Record<string, unknown>;
  routing?: {
    suggested_destination?: string;
  };
}

export interface RoutingDispatchResponse {
  ok: true;
  dispatch: {
    matter_id: string;
    destination: string;
    approved_by: string;
    approved_at: string;
    status: string;
  };
  matter: Matter;
}

export interface RoutingQueueItem {
  matter_id: string;
  title: string;
  cliente_id: string;
  status: string;
  contract_type: string;
  risk_level: string;
  destination?: string;
  routing_status?: string;
  updated_at?: string;
  created_at?: string;
}

export interface RoutingQueueResponse {
  ok: true;
  pending_review: RoutingQueueItem[];
  dispatched_history: RoutingQueueItem[];
  counts: {
    pending_review: number;
    dispatched_history: number;
    total: number;
  };
}

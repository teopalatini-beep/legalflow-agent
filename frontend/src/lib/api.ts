import { API_BASE_URL } from "@/lib/constants";
import type {
  AnalyzeRequest,
  AnalyzeContractUploadResponse,
  AnalyzeResponse,
  AnalysisMode,
  ApiErrorResponse,
  CreateMatterRequest,
  CreateMatterResponse,
  HealthResponse,
  IntegrationResponse,
  InboxIntegrationResponse,
  InboxProvider,
  RoutingDispatchRequest,
  RoutingDispatchResponse,
  RoutingQueueResponse,
  WorkflowMode,
} from "@/types/contract";

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface SsoOptions {
  token?: string;
  user?: string;
  email?: string;
  groups?: string;
}

function buildUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function toSsoHeaders(options?: SsoOptions): Record<string, string> {
  const cfg = options || {};
  const headers: Record<string, string> = {
    "X-SSO-User": cfg.user || "frontend-user",
    "X-SSO-Email": cfg.email || "frontend@legalflow.test",
    "X-SSO-Groups": cfg.groups || "legal_admin,legal_ops,approver,legal_viewer",
  };
  const token = (cfg.token || "").trim();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const data = (await response.json()) as T | ApiErrorResponse;
  if (!response.ok || (data as ApiErrorResponse).ok === false) {
    const err = data as ApiErrorResponse;
    const code = err.code ? ` [${err.code}]` : "";
    throw new Error((err.error || "Request failed") + code);
  }
  return data as T;
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  body?: JsonValue
): Promise<T> {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init.headers || {}),
  };
  const response = await fetch(buildUrl(path), {
    ...init,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  return parseResponse<T>(response);
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(buildUrl("/api/health"), { method: "GET" });
  return parseResponse<HealthResponse>(response);
}

export async function analyzeContract(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  const formData = new FormData();
  formData.set("contrato", payload.contrato);
  if (payload.contrato_b) {
    formData.set("contrato_b", payload.contrato_b);
    formData.set("compare", "true");
  }
  formData.set("modo", payload.modo || "local");
  formData.set("modelo", payload.modelo || "composer-2.5");
  formData.set("cliente_id", payload.cliente_id || "default");
  formData.set("modo_analisis", payload.modo_analisis || "general");

  const response = await fetch(buildUrl("/api/analizar"), {
    method: "POST",
    body: formData,
  });
  return parseResponse<AnalyzeResponse>(response);
}

export interface AnalyzeContractFileOptions {
  mode?: WorkflowMode;
  model?: string;
  clientId?: string;
  analysisMode?: AnalysisMode;
}

export async function analyzeContractFile(
  file: File,
  options: AnalyzeContractFileOptions = {}
): Promise<AnalyzeContractUploadResponse> {
  const formData = new FormData();
  formData.set("file", file);
  formData.set("mode", options.mode || "local");
  formData.set("model", options.model || "composer-2.5");
  formData.set("client_id", options.clientId || "default");
  formData.set("analysis_mode", options.analysisMode || "strict_playbook");

  const response = await fetch(buildUrl("/api/analyze-contract"), {
    method: "POST",
    body: formData,
  });
  return parseResponse<AnalyzeContractUploadResponse>(response);
}

export async function createMatter(
  payload: CreateMatterRequest,
  sso?: SsoOptions
): Promise<CreateMatterResponse> {
  return requestJson<CreateMatterResponse>(
    "/api/matters",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    payload as unknown as JsonValue
  );
}

export async function createESignEnvelope(
  matterId: string,
  signerEmail: string,
  sso?: SsoOptions
): Promise<IntegrationResponse> {
  return requestJson<IntegrationResponse>(
    "/api/integrations/esign/create-envelope",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    {
      matter_id: matterId,
      signer_email: signerEmail,
    } as unknown as JsonValue
  );
}

export async function createRecipientView(
  matterId: string,
  sso?: SsoOptions
): Promise<IntegrationResponse> {
  return requestJson<IntegrationResponse>(
    "/api/integrations/esign/recipient-view",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    {
      matter_id: matterId,
    } as unknown as JsonValue
  );
}

export async function simulateSignedWebhook(
  matterId: string,
  envelopeId: string,
  recipientId?: string
): Promise<{ ok: boolean; status: string; event_id?: string }> {
  return requestJson<{ ok: boolean; status: string; event_id?: string }>(
    "/api/integrations/esign/webhook",
    { method: "POST" },
    {
      event_id: `evt_frontend_${Date.now()}`,
      matter_id: matterId,
      envelope_id: envelopeId,
      recipient_id: recipientId || "",
      status: "completed",
    } as unknown as JsonValue
  );
}

export async function dispatchRouting(
  payload: RoutingDispatchRequest,
  sso?: SsoOptions
): Promise<RoutingDispatchResponse> {
  return requestJson<RoutingDispatchResponse>(
    "/api/routing/dispatch",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    payload as unknown as JsonValue
  );
}

export async function getRoutingQueue(): Promise<RoutingQueueResponse> {
  const response = await fetch(buildUrl("/api/routing/queue"), { method: "GET" });
  return parseResponse<RoutingQueueResponse>(response);
}

export async function connectInbox(
  provider: InboxProvider,
  sso?: SsoOptions
): Promise<InboxIntegrationResponse> {
  return requestJson<InboxIntegrationResponse>(
    "/api/integrations/inbox/connect",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    { provider } as unknown as JsonValue
  );
}

export async function searchInbox(
  provider: InboxProvider,
  query: string,
  sso?: SsoOptions
): Promise<InboxIntegrationResponse> {
  return requestJson<InboxIntegrationResponse>(
    "/api/integrations/inbox/search",
    {
      method: "POST",
      headers: toSsoHeaders(sso),
    },
    { provider, query } as unknown as JsonValue
  );
}

export async function trackLandingEvent(event: string, source = "frontend_landing"): Promise<void> {
  await requestJson<{ ok: true; tracked: string }>(
    "/api/analytics/track",
    { method: "POST" },
    { event, source } as unknown as JsonValue
  );
}

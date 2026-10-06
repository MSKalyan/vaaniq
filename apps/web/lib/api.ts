const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const ACCESS_KEY = "nenu_access_token";
const REFRESH_KEY = "nenu_refresh_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Storage access is guarded on `localStorage` rather than `window`: the client also
 * runs during SSR and in the node test environment, where `window` is absent but the
 * token helpers must stay callable.
 */
function storage(): Storage | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    // Safari private mode and similar throw on access rather than returning null.
    return null;
  }
}

export function getAccessToken(): string | null {
  return storage()?.getItem(ACCESS_KEY) ?? null;
}

export function getRefreshToken(): string | null {
  return storage()?.getItem(REFRESH_KEY) ?? null;
}

export function setTokens(access: string, refresh: string): void {
  const store = storage();
  store?.setItem(ACCESS_KEY, access);
  store?.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  const store = storage();
  store?.removeItem(ACCESS_KEY);
  store?.removeItem(REFRESH_KEY);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let res = await fetch(`${API_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401 && path !== "/auth/refresh") {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      const ok = await refreshSession(refreshToken);
      if (ok) {
        res = await fetch(`${API_URL}${path}`, {
          method: options.method ?? "GET",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${getAccessToken()}`,
          },
          body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
      }
    }
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function refreshSession(refreshToken: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      clearTokens();
      return false;
    }
    const data = (await res.json()) as { access_token: string; refresh_token: string };
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  // Several endpoints (analyze, end call) act on the path alone and take no body.
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export type OverviewMetrics = {
  total_leads: number;
  total_calls: number;
  completed_calls: number;
  failed_calls: number;
  interested: number;
  not_interested: number;
  callback_requested: number;
  average_call_duration_seconds: number;
  average_call_latency_ms: number;
  do_not_call: number;
  in_progress_calls: number;
  connection_rate: number;
  interest_rate: number;
  callback_rate: number;
};

export type AnalyticsDashboard = {
  overview: OverviewMetrics;
  campaigns: CampaignMetric[];
  outcomes: CallOutcomeCount[];
  languages: LanguageCount[];
  daily_volume: DailyVolume[];
};

export type CampaignMetric = {
  campaign_id: string;
  name: string;
  status: string;
  total_leads: number;
  calls_attempted: number;
  calls_connected: number;
  completed: number;
  interested: number;
  callback_requested: number;
  connection_rate: number;
  completion_rate: number;
};

export type CallOutcomeCount = { outcome: string; count: number };
export type LanguageCount = { language: string; count: number };
export type DailyVolume = { day: string | null; total: number; connected: number };

export type CallSummary = {
  id: string;
  lead_id: string;
  agent_id: string | null;
  campaign_id: string | null;
  provider_call_id: string | null;
  state: string;
  outcome: string | null;
  status: string;
  direction: string;
  phone_number: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  latency_ms: Record<string, number>;
  error_message: string | null;
  created_at: string;
  lead_name: string | null;
  agent_name: string | null;
};

export type CallsPage = {
  items: CallSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type TranscriptTurn = {
  id: string;
  speaker: string;
  text: string;
  language: string | null;
  timestamp: string;
  sequence_number: number;
};

export type Recording = {
  id: string;
  call_id: string;
  recording_url: string | null;
  storage_key: string | null;
  duration: number | null;
  status: string;
  started_at: string | null;
  ended_at: string | null;
};

export type CallAnalysis = {
  id: string;
  call_id: string;
  summary: string | null;
  sentiment: string | null;
  intent: string | null;
  interest_level: string | null;
  key_points: unknown[];
  extracted_data: Record<string, unknown>;
  objections: unknown[];
  next_action: string | null;
  callback_required: boolean;
  callback_time: string | null;
  hllm_version: string | null;
  created_at: string;
};

export type CallDetail = CallSummary & {
  transcript: TranscriptTurn[];
  recording: Recording | null;
  analysis: CallAnalysis | null;
};

export type KnowledgeBase = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeDocument = {
  id: string;
  knowledge_base_id: string;
  title: string;
  source_type: string;
  doc_metadata: Record<string, unknown>;
  created_at: string;
};

export type KnowledgeSearchHit = {
  chunk_id: string;
  content: string;
  chunk_index: number;
  title: string | null;
  score: number;
};

export type ProviderStatus = {
  capability: string;
  provider: string;
  configured: boolean;
  model: string | null;
  detail: string | null;
};

export type SettingsPayload = {
  app_name: string;
  app_env: string;
  frontend_url: string;
  default_max_call_duration_seconds: number;
  default_silence_timeout_seconds: number;
  providers: ProviderStatus[];
};

export type Voice = {
  id: string;
  provider: string | null;
  voice_name: string;
  language: string;
  metadata: Record<string, unknown> | null;
};

export type TokenPair = { access_token: string; refresh_token: string };
export type CurrentUser = { id: string; email: string; name: string };